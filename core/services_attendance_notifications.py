"""Attendance alerts shared by web, scanner, and daily attendance flows."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape

from .models import NotificationLog, SchoolMessage
from .models_biodata import Guardian
from .models_parent_device import ParentDevice


logger = logging.getLogger(__name__)


def _local_timestamp(timestamp):
    if timezone.is_aware(timestamp):
        return timezone.localtime(timestamp)
    return timestamp


def _attendance_copy(student, action, timestamp):
    local_time = _local_timestamp(timestamp)
    verb = 'checked in' if action == 'check_in' else 'checked out'
    name = student.user.get_full_name() or student.user.username
    school_name = getattr(student.school, 'name', 'School')
    subject = f'Attendance alert: {name} {verb}'
    message = (
        f'{name} {verb} at {local_time:%I:%M %p} on '
        f'{local_time:%A, %d %B %Y}.'
    )
    html = (
        f'<p>Hello,</p><p><strong>{escape(name)}</strong> {escape(verb)} at '
        f'<strong>{local_time:%I:%M %p}</strong> on {local_time:%A, %d %B %Y}.</p>'
        f'<p>Student ID: {escape(student.student_id)}<br>'
        f'Class: {escape(str(student.school_class))}</p>'
        f'<p>— {escape(school_name)}</p>'
    )
    return subject, message, html, local_time


def _recipient_users(student):
    users = [student.user]
    users.extend(
        guardian.user
        for guardian in Guardian.objects.filter(student=student).select_related('user')
        if guardian.user_id
    )
    unique = {}
    for user in users:
        if user and user.is_active:
            unique[user.pk] = user
    return list(unique.values())


def _recipient_emails(student, users):
    candidates = [user.email for user in users]
    try:
        candidates.append(student.bio_data.email)
    except Exception:
        pass
    for guardian in Guardian.objects.filter(student=student).select_related('user'):
        candidates.append(guardian.email)
        if guardian.user_id:
            candidates.append(guardian.user.email)

    unique = {}
    for email in candidates:
        normalized = (email or '').strip()
        if normalized:
            unique[normalized.casefold()] = normalized
    return list(unique.values())


def _create_in_app_alert(student, actor, recipients, subject, message):
    if not recipients or not student.school_id:
        return False
    sender = actor if getattr(actor, 'is_authenticated', False) else student.user
    if not sender or not sender.pk:
        return False
    alert = SchoolMessage.all_objects.create(
        school=student.school,
        sender=sender,
        audience='selected',
        subject=subject[:200],
        body=message,
    )
    alert.recipients.set(recipients)
    return True


def _send_email_alerts(student, recipients, subject, message, html):
    sent = 0
    failed = 0
    if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER:
        logger.warning('Attendance email skipped because SMTP is not configured.')
        return sent, len(recipients)

    for recipient in recipients:
        log = NotificationLog.all_objects.create(
            school=student.school,
            notification_type='attendance',
            recipient_email=recipient,
            recipient_name=recipient,
            subject=subject[:200],
            context_data={'student_id': student.id, 'student_number': student.student_id},
        )
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            )
            email.attach_alternative(html, 'text/html')
            email.send(fail_silently=False)
            log.status = 'sent'
            log.sent_at = timezone.now()
            log.save(update_fields=['status', 'sent_at'])
            sent += 1
        except Exception as exc:
            log.status = 'failed'
            log.error_message = str(exc)[:2000]
            log.save(update_fields=['status', 'error_message'])
            logger.exception('Attendance email could not be sent to %s', recipient)
            failed += 1
    return sent, failed


def _send_push_alerts(student, action, local_time, message):
    devices = ParentDevice.objects.filter(student=student, is_active=True)
    if not devices.exists():
        return 0
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            credential_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', '')
            if not credential_path:
                logger.info('Attendance push skipped because Firebase credentials are not configured.')
                return 0
            firebase_admin.initialize_app(credentials.Certificate(credential_path))

        sent = 0
        payload = {
            'type': 'attendance',
            'student_id': str(student.id),
            'student_number': str(student.student_id),
            'action': action,
            'timestamp': local_time.isoformat(),
        }
        for device in devices:
            try:
                messaging.send(messaging.Message(
                    notification=messaging.Notification(
                        title='Student attendance alert',
                        body=message,
                    ),
                    data=payload,
                    token=device.device_token,
                ))
                device.last_used = timezone.now()
                device.save(update_fields=['last_used'])
                sent += 1
            except Exception as exc:
                error_text = str(exc).lower()
                if 'invalid' in error_text or 'not-found' in error_text or 'unregistered' in error_text:
                    device.is_active = False
                    device.save(update_fields=['is_active'])
                logger.warning('Attendance push failed for device %s: %s', device.pk, exc)
        return sent
    except ImportError:
        logger.info('Attendance push skipped because firebase-admin is not installed.')
    except Exception:
        logger.exception('Attendance push notification setup failed.')
    return 0


def send_attendance_notifications(student, action, timestamp=None, actor=None):
    """Send one attendance event through in-app, email, and push channels."""
    if action not in {'check_in', 'check_out'}:
        raise ValueError('Unsupported attendance action.')

    timestamp = timestamp or timezone.now()
    subject, message, html, local_time = _attendance_copy(student, action, timestamp)
    users = _recipient_users(student)
    emails = _recipient_emails(student, users)

    result = {
        'in_app': False,
        'email_sent': 0,
        'email_failed': 0,
        'push_sent': 0,
        'recipient_count': len(users),
    }
    try:
        result['in_app'] = _create_in_app_alert(student, actor, users, subject, message)
    except Exception:
        logger.exception('Attendance in-app alert could not be created.')

    result['email_sent'], result['email_failed'] = _send_email_alerts(
        student, emails, subject, message, html,
    )
    result['push_sent'] = _send_push_alerts(student, action, local_time, message)
    return result


