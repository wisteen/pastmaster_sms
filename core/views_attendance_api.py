import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import SchoolTenant
from .models_attendance import AttendanceRecord, AttendanceSession
from .services_attendance_clock import AttendanceClockError, clock_attendance
from .services_attendance_notifications import send_attendance_notifications
from .services_id_cards import resolve_id_card
from .staffing import active_staff, active_students
from django.db.models import Q


def _api_authorized(request):
    configured_key = getattr(settings, 'ATTENDANCE_API_KEY', '')
    if not configured_key:
        return True
    supplied_key = request.headers.get('X-Attendance-Key', '')
    return hmac.compare_digest(supplied_key, configured_key)


def _request_data(request):
    if request.content_type == 'application/json':
        return json.loads(request.body or b'{}')
    return request.POST


def _request_school(request, data=None):
    school = getattr(request, 'school', None)
    requested_slug = (
        (data or {}).get('school')
        or request.GET.get('school')
        or ''
    ).strip()
    if school:
        if requested_slug and requested_slug != school.slug:
            return None
        return school
    if not requested_slug:
        return None
    return SchoolTenant.objects.filter(slug=requested_slug, is_active=True).first()


@csrf_exempt
@require_http_methods(['POST'])
def mark_attendance(request):
    """Clock an ID-card holder in or out using an explicit or automatic action."""
    if not _api_authorized(request):
        return JsonResponse({'success': False, 'message': 'Invalid attendance API key.'}, status=401)

    try:
        data = _request_data(request)
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'message': 'Invalid request data.'}, status=400)

    scanned_identifier = (data.get('student_id') or data.get('barcode') or '').strip()
    session_id = data.get('session_id')
    requested_action = (data.get('action') or 'auto').strip().lower()
    requested_action = {'check_in': 'in', 'check_out': 'out'}.get(requested_action, requested_action)
    if not scanned_identifier or not session_id:
        return JsonResponse({'success': False, 'message': 'An ID card code and session_id are required.'}, status=400)
    if requested_action not in {'auto', 'in', 'out'}:
        return JsonResponse({'success': False, 'message': 'Action must be auto, in, or out.'}, status=400)

    school = _request_school(request, data)
    if not school:
        return JsonResponse({
            'success': False,
            'message': 'A valid school context is required.',
        }, status=400)
    sessions = AttendanceSession.all_objects.filter(pk=session_id, school=school)
    session = sessions.select_related('school', 'created_by').first()
    if not session:
        return JsonResponse({'success': False, 'message': 'Attendance session not found.'}, status=404)

    id_card = resolve_id_card(
        scanned_identifier,
        school=school,
        allow_student_number=True,
        allow_teacher_number=True,
    )
    if not id_card:
        inactive_card = resolve_id_card(
            scanned_identifier,
            school=school,
            allow_student_number=True,
            allow_teacher_number=True,
            active_only=False,
        )
        message = 'This ID card is inactive.' if inactive_card else 'Invalid ID card for this school.'
        return JsonResponse({'success': False, 'message': message}, status=404)
    student = id_card.student
    teacher = id_card.teacher
    holder = student or teacher
    if session.is_closed:
        return JsonResponse({'success': False, 'message': 'This attendance session is closed.'}, status=409)
    if session.date != timezone.localdate():
        return JsonResponse({'success': False, 'message': "Only today's active session can be used."}, status=409)

    event_time = timezone.now()
    try:
        result = clock_attendance(
            session=session,
            id_card=id_card,
            actor=session.created_by,
            requested_action=requested_action,
            event_time=event_time,
            source='mobile',
        )
    except AttendanceClockError as exc:
        return JsonResponse({
            'success': False,
            'message': str(exc),
            'code': exc.code,
            'retry_after_seconds': exc.retry_after_seconds,
        }, status=409)

    record = result.record
    notification_action = 'check_in' if result.action == 'in' else 'check_out'

    notifications = {}
    if student:
        notifications = send_attendance_notifications(
            student,
            notification_action,
            event_time,
            actor=session.created_by,
        )
    verb = 'in' if notification_action == 'check_in' else 'out'
    return JsonResponse({
        'success': True,
        'message': f'{holder.user.get_full_name() or holder.user.username} checked {verb} successfully.',
        'action': notification_action,
        'record_id': record.id,
        'holder_type': 'student' if student else 'teacher',
        'holder_role': id_card.get_holder_role(),
        'holder_id': id_card.get_holder_id(),
        'time': event_time.isoformat(),
        'notifications': notifications,
    })


@require_http_methods(['GET'])
def get_active_session(request):
    if not _api_authorized(request):
        return JsonResponse({'success': False, 'message': 'Invalid attendance API key.'}, status=401)
    school = _request_school(request)
    if not school:
        return JsonResponse({
            'success': False,
            'message': 'A valid school context is required.',
        }, status=400)
    sessions = AttendanceSession.all_objects.filter(
        school=school,
        date=timezone.localdate(),
        is_closed=False,
    )
    session = sessions.order_by('session_type', 'created_at').first()
    if not session:
        return JsonResponse({'success': False, 'message': 'No active session today.'}, status=404)
    return JsonResponse({
        'success': True,
        'session_id': session.id,
        'date': session.date.isoformat(),
        'session_type': session.session_type,
        'school': session.school.slug,
    })


@require_http_methods(['GET'])
def get_today_attendance(request, session_id):
    if not _api_authorized(request):
        return JsonResponse({'success': False, 'message': 'Invalid attendance API key.'}, status=401)
    school = _request_school(request)
    if not school:
        return JsonResponse({
            'success': False,
            'message': 'A valid school context is required.',
        }, status=400)
    sessions = AttendanceSession.all_objects.filter(pk=session_id, school=school)
    session = sessions.first()
    if not session:
        return JsonResponse({'success': False, 'message': 'Attendance session not found.'}, status=404)
    records = AttendanceRecord.objects.filter(session=session).filter(
        Q(student_id__in=active_students(school).values_list('pk', flat=True)) |
        Q(teacher_id__in=active_staff(school).values_list('pk', flat=True))
    ).select_related(
        'student__user', 'teacher__user',
    )
    data = []
    for record in records:
        holder = record.student or record.teacher
        if not holder:
            continue
        holder_name = holder.user.get_full_name() or holder.user.username
        holder_id = record.student.student_id if record.student else record.teacher.employee_id
        data.append({
            'id': record.id,
            'holder_name': holder_name,
            'holder_id': holder_id,
            'holder_type': 'student' if record.student else 'teacher',
            'holder_role': 'Student' if record.student else record.teacher.get_staff_title(),
            'student_name': holder_name if record.student else None,
            'student_id': holder_id if record.student else None,
            'check_in_time': timezone.localtime(record.check_in_time).strftime('%H:%M:%S'),
            'check_out_time': timezone.localtime(record.check_out_time).strftime('%H:%M:%S') if record.check_out_time else None,
            'status': record.status,
        })
    return JsonResponse({'success': True, 'records': data})
