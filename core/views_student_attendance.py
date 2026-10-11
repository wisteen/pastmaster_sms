import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Student, Term
from .models_daily_attendance import DailyAttendanceRecord, DailyAttendanceSession
from .services_attendance_notifications import send_attendance_notifications


def _attendance_state(record):
    if not record or not record.morning_time:
        return 'not_checked_in', 'in'
    if not record.afternoon_time:
        return 'checked_in', 'out'
    return 'checked_out', None


@login_required
@require_http_methods(['GET', 'POST'])
def student_check_in_out(request):
    """Return today's clock state or atomically clock the signed-in student in/out."""
    student = Student.objects.filter(user=request.user).select_related(
        'user', 'school', 'school_class'
    ).first()
    if not student:
        return JsonResponse({'success': False, 'message': 'Student profile not found.'}, status=404)

    today = timezone.localdate()
    current_record = DailyAttendanceRecord.objects.filter(
        student=student,
        session__date=today,
    ).select_related('session').first()

    if request.method == 'GET':
        state, next_action = _attendance_state(current_record)
        return JsonResponse({
            'success': True,
            'state': state,
            'next_action': next_action,
            'check_in_time': current_record.morning_time.isoformat() if current_record and current_record.morning_time else None,
            'check_out_time': current_record.afternoon_time.isoformat() if current_record and current_record.afternoon_time else None,
        })

    try:
        data = json.loads(request.body or b'{}') if request.content_type == 'application/json' else request.POST
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'message': 'Invalid request data.'}, status=400)

    action = (data.get('action') or '').strip().lower()
    action = {'check_in': 'in', 'check_out': 'out'}.get(action, action)
    if action not in {'in', 'out'}:
        return JsonResponse({'success': False, 'message': 'Action must be in or out.'}, status=400)

    active_term = Term.objects.filter(school=student.school, is_active=True).first()
    if not active_term:
        return JsonResponse({'success': False, 'message': 'No active term found.'}, status=409)

    current_time = timezone.now()
    with transaction.atomic():
        session, _ = DailyAttendanceSession.objects.get_or_create(
            date=today,
            school_class=student.school_class,
            term=active_term,
            defaults={'marked_by': request.user},
        )
        attendance, _ = DailyAttendanceRecord.objects.select_for_update().get_or_create(
            session=session,
            student=student,
            defaults={'morning_status': 'absent', 'afternoon_status': 'absent'},
        )

        if action == 'in':
            if attendance.morning_time:
                return JsonResponse({
                    'success': False,
                    'message': f'Already checked in at {attendance.morning_time:%I:%M %p}.',
                    'state': _attendance_state(attendance)[0],
                }, status=409)
            attendance.morning_time = timezone.localtime(current_time).time()
            attendance.morning_status = 'present'
            attendance.save(update_fields=['morning_time', 'morning_status', 'is_absent', 'updated_at'])
            notification_action = 'check_in'
        else:
            if not attendance.morning_time:
                return JsonResponse({'success': False, 'message': 'Please check in before checking out.'}, status=409)
            if attendance.afternoon_time:
                return JsonResponse({
                    'success': False,
                    'message': f'Already checked out at {attendance.afternoon_time:%I:%M %p}.',
                    'state': 'checked_out',
                }, status=409)
            attendance.afternoon_time = timezone.localtime(current_time).time()
            attendance.afternoon_status = 'present'
            attendance.save(update_fields=['afternoon_time', 'afternoon_status', 'is_absent', 'updated_at'])
            notification_action = 'check_out'

    notifications = send_attendance_notifications(
        student,
        notification_action,
        current_time,
        actor=request.user,
    )
    state, next_action = _attendance_state(attendance)
    verb = 'Checked in' if action == 'in' else 'Checked out'
    return JsonResponse({
        'success': True,
        'message': f'{verb} successfully at {timezone.localtime(current_time):%I:%M %p}.',
        'action': notification_action,
        'state': state,
        'next_action': next_action,
        'time': current_time.isoformat(),
        'notifications': notifications,
    })
