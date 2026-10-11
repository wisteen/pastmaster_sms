from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from django.db import transaction
from django.utils import timezone

from .models_attendance import AttendanceMovement, AttendanceRecord


MINIMUM_STAY = timedelta(minutes=10)


class AttendanceClockError(Exception):
    def __init__(self, message, *, code, retry_after_seconds=0):
        super().__init__(message)
        self.code = code
        self.retry_after_seconds = max(0, int(retry_after_seconds))


@dataclass(frozen=True)
class AttendanceClockResult:
    record: AttendanceRecord
    action: str
    event_time: object
    movement: AttendanceMovement


def _current_state(record):
    latest = record.movements.order_by('-event_time', '-id').first()
    if latest:
        return latest.action, latest.event_time
    if record.check_out_time:
        return 'out', record.check_out_time
    return 'in', record.check_in_time


def _minimum_stay_message(retry_after_seconds):
    minutes = max(1, ceil(retry_after_seconds / 60))
    unit = 'minute' if minutes == 1 else 'minutes'
    return (
        'Clock-out is only allowed 10 minutes after clock-in. '
        f'Please wait about {minutes} more {unit}.'
    )


def clock_attendance(
    *, session, id_card, actor=None, requested_action='auto',
    event_time=None, source='scanner',
):
    """Apply one gate movement while retaining the day's first in/final out."""
    event_time = event_time or timezone.now()
    student = id_card.student
    teacher = id_card.teacher

    with transaction.atomic():
        # Morning and afternoon sessions are UI buckets, not separate visits.
        # Reuse the holder's record for the same school day so web and mobile
        # scanners both preserve one first-arrival/final-departure timeline.
        record = AttendanceRecord.objects.select_for_update().filter(
            session__school_id=session.school_id,
            session__date=session.date,
            id_card=id_card,
        ).order_by('check_in_time', 'id').first()

        state = state_time = None
        if record:
            state, state_time = _current_state(record)

        action = requested_action
        if action == 'auto':
            action = 'out' if state == 'in' else 'in'

        if action == 'in':
            if state == 'in':
                raise AttendanceClockError(
                    'This ID card holder is already clocked in.',
                    code='already_in',
                )
            if record is None:
                record = AttendanceRecord.objects.create(
                    session=session,
                    id_card=id_card,
                    student=student,
                    teacher=teacher,
                    check_in_time=event_time,
                    status='present',
                    marked_by=actor,
                )
                if record.check_in_time != event_time:
                    record.check_in_time = event_time
                    record.save(update_fields=['check_in_time'])
            else:
                record.check_out_time = None
                record.save(update_fields=['check_out_time'])
        else:
            if record is None:
                raise AttendanceClockError(
                    'This ID card holder must clock in before clocking out.',
                    code='not_checked_in',
                )
            if state == 'out':
                raise AttendanceClockError(
                    'This ID card holder is already clocked out. Scan again only when they return.',
                    code='already_out',
                )
            elapsed = event_time - state_time
            if elapsed < MINIMUM_STAY:
                retry_after = (MINIMUM_STAY - elapsed).total_seconds()
                raise AttendanceClockError(
                    _minimum_stay_message(retry_after),
                    code='minimum_stay',
                    retry_after_seconds=retry_after,
                )
            record.check_out_time = event_time
            record.save(update_fields=['check_out_time'])

        movement = AttendanceMovement.objects.create(
            record=record,
            action=action,
            event_time=event_time,
            recorded_by=actor,
            source=source,
        )

    return AttendanceClockResult(record, action, event_time, movement)
