from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Q, Avg
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from datetime import datetime, timedelta
from urllib.parse import urlencode
from .models import ClassTeacher, Student, SchoolClass, Term, User
from .models_daily_attendance import DailyAttendanceSession, DailyAttendanceRecord, TermAttendanceSummary
from .models_parent_device import ParentDevice
import csv
from .staffing import active_students


def _attendance_terms():
    return Term.objects.all().order_by('-session', '-start_date', 'name')


def _academic_sessions_from_terms(terms):
    return sorted({term.session for term in terms if term.session}, reverse=True)


def _selected_term_context(request, term_id=None):
    terms = _attendance_terms()
    requested_term_id = term_id or request.POST.get('term_id') or request.GET.get('term_id')
    requested_session = request.POST.get('academic_session') or request.GET.get('academic_session')
    selected_term = None

    if requested_term_id:
        try:
            selected_term = terms.filter(id=int(requested_term_id)).first()
        except (TypeError, ValueError):
            selected_term = None

    if selected_term and requested_session and selected_term.session != requested_session:
        selected_term = None

    if not selected_term and requested_session:
        selected_term = (
            terms.filter(session=requested_session, is_active=True).first()
            or terms.filter(session=requested_session).first()
        )

    if not selected_term:
        selected_term = terms.filter(is_active=True).first() or terms.first()

    selected_session = selected_term.session if selected_term else requested_session
    return {
        'term': selected_term,
        'terms': terms,
        'academic_sessions': _academic_sessions_from_terms(terms),
        'selected_academic_session': selected_session,
    }


def _default_attendance_date(term):
    today = timezone.localdate()
    if term and term.end_date and term.end_date < today:
        return term.end_date
    if term and term.start_date and term.start_date > today:
        return term.start_date
    return today


def _selected_attendance_date(request, term):
    raw_date = (
        request.POST.get('attendance_date')
        or request.POST.get('date')
        or request.GET.get('date')
        or request.GET.get('attendance_date')
    )
    selected_date = parse_date(raw_date) if raw_date else None

    if not selected_date:
        selected_date = _default_attendance_date(term)

    today = timezone.localdate()
    if selected_date > today:
        messages.warning(request, 'Future attendance dates are not available. Showing today instead.')
        selected_date = today

    return selected_date


def _attendance_query_string(term, selected_date=None, extra=None):
    params = {}
    if selected_date:
        params['date'] = selected_date.isoformat()
    if term:
        params['term_id'] = term.id
        params['academic_session'] = term.session
    if extra:
        params.update({key: value for key, value in extra.items() if value not in [None, '']})
    return urlencode(params)


def _attendance_classes_for_user(user):
    if hasattr(user, 'teacher'):
        class_ids = ClassTeacher.objects.filter(
            teacher=user.teacher
        ).values_list('school_class_id', flat=True)
        return SchoolClass.objects.filter(id__in=class_ids).order_by('name', 'stream')
    return SchoolClass.objects.all().order_by('name', 'stream')


def send_parent_notification(student, action, timestamp):
    """
    Send push notification to parent's mobile app when student checks in/out
    """
    notification_data = {
        'type': 'attendance',
        'student_id': student.id,
        'student_name': student.user.get_full_name(),
        'student_number': student.student_id,
        'class': student.school_class.name if student.school_class else '',
        'action': action,
        'timestamp': timestamp.isoformat(),
        'time_formatted': timestamp.strftime('%I:%M %p'),
        'date': timestamp.strftime('%B %d, %Y'),
        'message': f"{student.user.get_full_name()} checked {'in' if action == 'check_in' else 'out'} at {timestamp.strftime('%I:%M %p')}"
    }
    
    # Send to all active parent devices for this student
    try:
        from firebase_admin import messaging
        import firebase_admin
        
        # Initialize Firebase if not already done
        if not firebase_admin._apps:
            import os
            cred_path = os.path.join(os.path.dirname(__file__), '..', 'firebase-credentials.json')
            if os.path.exists(cred_path):
                cred = firebase_admin.credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
        
        # Get all active parent devices for this student
        devices = ParentDevice.objects.filter(student=student, is_active=True)
        
        for device in devices:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title='🎓 Student Attendance Alert',
                        body=notification_data['message']
                    ),
                    data=notification_data,
                    token=device.device_token
                )
                messaging.send(message)
                device.last_used = timezone.now()
                device.save(update_fields=['last_used'])
            except Exception as e:
                # If token is invalid, mark device as inactive
                if 'invalid' in str(e).lower() or 'not-found' in str(e).lower():
                    device.is_active = False
                    device.save(update_fields=['is_active'])
    except ImportError:
        # Firebase not installed, skip notification
        pass
    except Exception as e:
        # Log error but don't break the flow
        print(f"Notification error: {e}")
    
    return notification_data


@login_required
def daily_attendance_dashboard(request):
    """Dashboard for daily attendance"""
    term_context = _selected_term_context(request)
    selected_term = term_context['term']
    selected_date = _selected_attendance_date(request, selected_term)
    
    if not selected_term:
        messages.error(request, "No term found.")
        return redirect('core:dashboard')
    
    # Get user's assigned classes if class teacher
    user_classes = _attendance_classes_for_user(request.user)
    user_class = user_classes.first()
    
    # Get sessions for the selected date and term
    sessions = DailyAttendanceSession.objects.filter(
        date=selected_date,
        term=selected_term
    )
    
    if user_classes.exists():
        sessions = sessions.filter(school_class__in=user_classes)
    
    context = {
        'today': timezone.localdate(),
        'selected_date': selected_date,
        'active_term': selected_term,
        'selected_term': selected_term,
        'sessions': sessions,
        'user_class': user_class,
        'user_classes': user_classes,
        'dashboard_query': _attendance_query_string(selected_term, selected_date),
        **term_context,
    }
    
    return render(request, 'daily_attendance/dashboard.html', context)

@login_required
def mark_daily_attendance(request, class_id=None):
    """Mark daily attendance for a class"""
    term_context = _selected_term_context(request)
    selected_term = term_context['term']
    selected_date = _selected_attendance_date(request, selected_term)
    
    if not selected_term:
        messages.error(request, "No term found.")
        return redirect('core:dashboard')

    available_classes = _attendance_classes_for_user(request.user)
    requested_class_id = class_id or request.POST.get('class_id') or request.GET.get('class_id')
    
    # Get class
    if requested_class_id:
        school_class = get_object_or_404(SchoolClass, id=requested_class_id)
        if hasattr(request.user, 'teacher') and not available_classes.filter(id=school_class.id).exists():
            messages.error(request, "You are not assigned to that class.")
            return redirect('daily_attendance_dashboard')
    elif available_classes.exists():
        school_class = available_classes.first()
        if not school_class:
            messages.error(request, "No class assigned.")
            return redirect('daily_attendance_dashboard')
    else:
        messages.error(request, "No class assigned.")
        return redirect('daily_attendance_dashboard')
    
    # Get or create the attendance session for the selected date and term
    session, created = DailyAttendanceSession.objects.get_or_create(
        date=selected_date,
        school_class=school_class,
        term=selected_term,
        defaults={'marked_by': request.user}
    )
    
    # Get all students in class
    students = active_students(school_class.school).filter(school_class=school_class).order_by('user__first_name', 'user__last_name')
    
    # Get existing records
    existing_records_dict = {}
    for record in DailyAttendanceRecord.objects.filter(session=session):
        existing_records_dict[record.student_id] = {
            'morning_status': record.morning_status,
            'afternoon_status': record.afternoon_status,
            'absence_reason': record.absence_reason or '',
            'absence_details': record.absence_details or '',
            'remarks': record.remarks or '',
        }
    
    import json
    existing_records_json = json.dumps(existing_records_dict)
    
    if request.method == 'POST':
        attendance_time = timezone.localtime().time()
        should_notify_parents = selected_date == timezone.localdate()

        for student in students:
            morning_status = request.POST.get(f'morning_{student.id}', 'present')
            afternoon_status = request.POST.get(f'afternoon_{student.id}', 'present')
            absence_reason = request.POST.get(f'reason_{student.id}', '')
            absence_details = request.POST.get(f'details_{student.id}', '')
            remarks = request.POST.get(f'remarks_{student.id}', '')
            
            # Get or create record
            record, created = DailyAttendanceRecord.objects.get_or_create(
                session=session,
                student=student,
                defaults={
                    'morning_status': morning_status,
                    'afternoon_status': afternoon_status,
                }
            )
            
            # Update record
            record.morning_status = morning_status
            record.afternoon_status = afternoon_status
            record.absence_reason = absence_reason
            record.absence_details = absence_details
            record.remarks = remarks
            
            # Set times
            if morning_status == 'present' or morning_status == 'late':
                record.morning_time = attendance_time
            else:
                record.morning_time = None
            if afternoon_status == 'present' or afternoon_status == 'left_early':
                record.afternoon_time = attendance_time
            else:
                record.afternoon_time = None
            
            record.save()
            
            # Send parent notification when student checks in/out
            if should_notify_parents and morning_status in ['present', 'late'] and record.morning_time:
                send_parent_notification(student, 'check_in', timezone.now())
            if should_notify_parents and afternoon_status in ['present', 'left_early'] and record.afternoon_time:
                send_parent_notification(student, 'check_out', timezone.now())
        
        # Update term summaries
        update_term_summaries(school_class, selected_term)
        
        messages.success(request, f"Attendance marked successfully for {school_class.name} on {selected_date:%B %d, %Y}")
        query = _attendance_query_string(selected_term, selected_date)
        return redirect(f"{reverse('daily_attendance_dashboard')}?{query}")
    
    context = {
        'session': session,
        'school_class': school_class,
        'available_classes': available_classes,
        'students': students,
        'existing_records': existing_records_dict,
        'existing_records_json': existing_records_json,
        'active_term': selected_term,
        'selected_term': selected_term,
        'selected_date': selected_date,
        'today': timezone.localdate(),
        'dashboard_query': _attendance_query_string(selected_term, selected_date),
        **term_context,
    }
    
    return render(request, 'daily_attendance/mark_attendance.html', context)

@login_required
def view_daily_attendance(request, session_id):
    """View attendance for a specific session"""
    session = get_object_or_404(DailyAttendanceSession, id=session_id)
    records = DailyAttendanceRecord.objects.filter(
        session=session,
        student_id__in=active_students(session.school_class.school).values_list('pk', flat=True),
    ).select_related('student__user')
    
    # Statistics
    total_students = records.count()
    morning_present = records.filter(Q(morning_status='present') | Q(morning_status='late')).count()
    afternoon_present = records.filter(Q(afternoon_status='present') | Q(afternoon_status='left_early')).count()
    full_day_absent = records.filter(morning_status='absent', afternoon_status='absent').count()
    
    context = {
        'session': session,
        'records': records,
        'total_students': total_students,
        'morning_present': morning_present,
        'afternoon_present': afternoon_present,
        'full_day_absent': full_day_absent,
    }
    
    return render(request, 'daily_attendance/view_attendance.html', context)

@login_required
def term_attendance_analysis(request, term_id=None):
    """Comprehensive term attendance analysis"""
    term_context = _selected_term_context(request, term_id)
    term = term_context['term']
    
    if not term:
        messages.error(request, "No term found.")
        return redirect('core:dashboard')
    
    # Get class filter
    class_id = request.GET.get('class')
    school = getattr(request, 'school', None)
    summaries = TermAttendanceSummary.objects.filter(
        term=term,
        student_id__in=active_students(school).values_list('pk', flat=True),
    ).select_related('student__user', 'student__school_class')
    
    if class_id:
        summaries = summaries.filter(student__school_class_id=class_id)
    
    # Calculate overall statistics
    total_students = summaries.count()
    avg_attendance = summaries.aggregate(Avg('attendance_percentage'))['attendance_percentage__avg'] or 0
    
    excellent_count = summaries.filter(attendance_percentage__gte=95).count()
    good_count = summaries.filter(attendance_percentage__gte=85, attendance_percentage__lt=95).count()
    fair_count = summaries.filter(attendance_percentage__gte=75, attendance_percentage__lt=85).count()
    poor_count = summaries.filter(attendance_percentage__lt=75).count()
    
    # Get all classes for filter
    classes = SchoolClass.objects.all()
    
    context = {
        'term': term,
        'summaries': summaries,
        'total_students': total_students,
        'avg_attendance': round(avg_attendance, 2),
        'excellent_count': excellent_count,
        'good_count': good_count,
        'fair_count': fair_count,
        'poor_count': poor_count,
        'classes': classes,
        'selected_class': class_id,
        **term_context,
    }
    
    return render(request, 'daily_attendance/term_analysis.html', context)

@login_required
def student_attendance_detail(request, student_id, term_id=None):
    """Detailed attendance view for a student"""
    student = get_object_or_404(Student, id=student_id)
    
    if term_id:
        term = get_object_or_404(Term, id=term_id)
    else:
        term = Term.objects.filter(is_active=True).first()
    
    if not term:
        messages.error(request, "No term found.")
        return redirect('core:dashboard')
    
    # Get or create summary
    summary, created = TermAttendanceSummary.objects.get_or_create(
        student=student,
        term=term
    )
    
    if created or request.GET.get('refresh'):
        summary.calculate_summary()
    
    # Get all daily records
    records = DailyAttendanceRecord.objects.filter(
        student=student,
        session__term=term
    ).select_related('session').order_by('-session__date')
    
    context = {
        'student': student,
        'term': term,
        'summary': summary,
        'records': records,
    }
    
    return render(request, 'daily_attendance/student_detail.html', context)

@login_required
def class_attendance_report(request, class_id, term_id=None):
    """Generate class attendance report"""
    school_class = get_object_or_404(SchoolClass, id=class_id)
    term_context = _selected_term_context(request, term_id)
    term = term_context['term']
    
    if not term:
        messages.error(request, "No term found.")
        return redirect('core:dashboard')
    
    # Get all sessions for this class and term
    sessions = DailyAttendanceSession.objects.filter(
        school_class=school_class,
        term=term
    ).order_by('date')
    
    # Get all students
    students = active_students(school_class.school).filter(school_class=school_class).order_by('user__first_name')
    
    # Build attendance matrix
    attendance_data = []
    for student in students:
        summary, created = TermAttendanceSummary.objects.get_or_create(
            student=student,
            term=term
        )
        if created:
            summary.calculate_summary()
        
        records = DailyAttendanceRecord.objects.filter(
            student=student,
            session__in=sessions
        ).select_related('session')
        
        record_dict = {record.session.date: record for record in records}
        
        attendance_data.append({
            'student': student,
            'summary': summary,
            'records': record_dict,
        })
    
    context = {
        'school_class': school_class,
        'term': term,
        'sessions': sessions,
        'attendance_data': attendance_data,
        **term_context,
    }
    
    return render(request, 'daily_attendance/class_report.html', context)

@login_required
def export_attendance_csv(request, class_id, term_id):
    """Export attendance to CSV"""
    school_class = get_object_or_404(SchoolClass, id=class_id)
    term = get_object_or_404(Term, id=term_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{school_class.name}_{term.name}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Total Days', 'Days Present', 'Days Absent', 
                     'Days Late', 'Attendance %', 'Sick Days', 'Unauthorized Days'])
    
    summaries = TermAttendanceSummary.objects.filter(
        student__school_class=school_class,
        student_id__in=active_students(school_class.school).values_list('pk', flat=True),
        term=term
    ).select_related('student__user')
    
    for summary in summaries:
        writer.writerow([
            summary.student.student_id,
            summary.student.user.get_full_name(),
            summary.total_school_days,
            summary.days_present,
            summary.days_absent,
            summary.days_late,
            f"{summary.attendance_percentage:.2f}%",
            summary.sick_days,
            summary.unauthorized_days,
        ])
    
    return response

def update_term_summaries(school_class, term):
    """Update term summaries for all students in a class"""
    students = active_students(school_class.school).filter(school_class=school_class)
    
    for student in students:
        summary, created = TermAttendanceSummary.objects.get_or_create(
            student=student,
            term=term
        )
        summary.calculate_summary()

