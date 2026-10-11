from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Avg, Count, Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
from .models import *
from .staffing import active_memberships, active_staff, active_students

@login_required
def reports_dashboard(request):
    """Main reports dashboard"""
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    
    return render(request, 'reports/dashboard.html')

@login_required
def academic_performance_report(request):
    """Generate academic performance report"""
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    
    # Get filter parameters
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    term_id = request.GET.get('term_id')
    export_format = request.GET.get('export')
    
    # Base queryset
    school = getattr(request, 'school', None)
    results = Result.objects.filter(
        student_id__in=active_students(school).values_list('pk', flat=True),
    ).select_related('student__user', 'subject', 'term', 'student__school_class')
    
    # Apply filters
    if class_id:
        results = results.filter(student__school_class_id=class_id)
    if subject_id:
        results = results.filter(subject_id=subject_id)
    if term_id:
        results = results.filter(term_id=term_id)
    else:
        # Default to active term
        active_term = Term.objects.filter(is_active=True).first()
        if active_term:
            results = results.filter(term=active_term)
    
    # Calculate statistics
    total_students = results.values('student').distinct().count()
    avg_score = results.aggregate(avg=Avg('total_score'))['avg'] or 0
    pass_rate = (results.filter(total_score__gte=50).count() / results.count() * 100) if results.count() > 0 else 0
    
    # Grade distribution
    grade_stats = {}
    for grade in ['A+', 'A', 'B', 'C', 'D', 'F']:
        count = results.filter(grade=grade).count()
        grade_stats[grade] = {
            'count': count,
            'percentage': (count / results.count() * 100) if results.count() > 0 else 0
        }
    
    # Subject performance
    subject_performance = []
    if not subject_id:
        subjects = Subject.objects.all()
        for subject in subjects:
            subject_results = results.filter(subject=subject)
            if subject_results.exists():
                subject_performance.append({
                    'subject': subject,
                    'avg_score': subject_results.aggregate(avg=Avg('total_score'))['avg'],
                    'pass_rate': (subject_results.filter(total_score__gte=50).count() / subject_results.count() * 100),
                    'total_students': subject_results.count()
                })
    
    # Class performance
    class_performance = []
    if not class_id:
        classes = SchoolClass.objects.all()
        for school_class in classes:
            class_results = results.filter(student__school_class=school_class)
            if class_results.exists():
                class_performance.append({
                    'class': school_class,
                    'avg_score': class_results.aggregate(avg=Avg('total_score'))['avg'],
                    'pass_rate': (class_results.filter(total_score__gte=50).count() / class_results.count() * 100),
                    'total_students': class_results.values('student').distinct().count()
                })
    
    context = {
        'total_students': total_students,
        'avg_score': round(avg_score, 2),
        'pass_rate': round(pass_rate, 2),
        'grade_stats': grade_stats,
        'subject_performance': subject_performance,
        'class_performance': class_performance,
        'classes': SchoolClass.objects.all(),
        'subjects': Subject.objects.all(),
        'terms': Term.objects.all(),
        'selected_class': class_id,
        'selected_subject': subject_id,
        'selected_term': term_id,
    }
    
    # Export functionality
    if export_format == 'csv':
        return export_academic_performance_csv(results, context)
    elif export_format == 'json':
        return export_academic_performance_json(context)
    
    return render(request, 'reports/academic_performance.html', context)

@login_required
def attendance_report(request):
    """Generate attendance report"""
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    
    # Get filter parameters
    class_id = request.GET.get('class_id')
    term_id = request.GET.get('term_id')
    export_format = request.GET.get('export')
    
    # Base queryset
    school = getattr(request, 'school', None)
    attendance_records = Attendance.objects.filter(
        student_id__in=active_students(school).values_list('pk', flat=True),
    ).select_related('student__user', 'student__school_class', 'term')
    
    # Apply filters
    if class_id:
        attendance_records = attendance_records.filter(student__school_class_id=class_id)
    if term_id:
        attendance_records = attendance_records.filter(term_id=term_id)
    else:
        # Default to active term
        active_term = Term.objects.filter(is_active=True).first()
        if active_term:
            attendance_records = attendance_records.filter(term=active_term)
    
    # Calculate statistics
    total_students = attendance_records.count()
    avg_attendance = attendance_records.aggregate(
        avg_percentage=Avg('days_present') * 100 / Avg('total_days')
    )['avg_percentage'] or 0
    
    # Attendance ranges
    excellent_attendance = attendance_records.filter(days_present__gte=F('total_days') * 0.9).count()
    good_attendance = attendance_records.filter(
        days_present__gte=F('total_days') * 0.8,
        days_present__lt=F('total_days') * 0.9
    ).count()
    poor_attendance = attendance_records.filter(days_present__lt=F('total_days') * 0.8).count()
    
    # Class-wise attendance
    class_attendance = []
    if not class_id:
        classes = SchoolClass.objects.all()
        for school_class in classes:
            class_records = attendance_records.filter(student__school_class=school_class)
            if class_records.exists():
                total_present = class_records.aggregate(sum=Sum('days_present'))['sum'] or 0
                total_days = class_records.aggregate(sum=Sum('total_days'))['sum'] or 1
                class_attendance.append({
                    'class': school_class,
                    'attendance_rate': (total_present / total_days * 100) if total_days > 0 else 0,
                    'total_students': class_records.count()
                })
    
    # Teacher attendance (mock data - extend as needed)
    teacher_attendance = []
    teachers = active_staff(school)[:5]  # Limit for demo
    for teacher in teachers:
        teacher_attendance.append({
            'teacher': teacher,
            'attendance_rate': 95.0,  # Mock data
            'days_present': 19,
            'total_days': 20
        })
    
    context = {
        'total_students': total_students,
        'avg_attendance': round(avg_attendance, 2),
        'excellent_attendance': excellent_attendance,
        'good_attendance': good_attendance,
        'poor_attendance': poor_attendance,
        'class_attendance': class_attendance,
        'teacher_attendance': teacher_attendance,
        'attendance_records': attendance_records[:20],  # Limit for display
        'classes': SchoolClass.objects.all(),
        'terms': Term.objects.all(),
        'selected_class': class_id,
        'selected_term': term_id,
    }
    
    # Export functionality
    if export_format == 'csv':
        return export_attendance_csv(attendance_records, context)
    elif export_format == 'json':
        return export_attendance_json(context)
    
    return render(request, 'reports/attendance.html', context)

@login_required
def system_usage_report(request):
    """Generate system usage report"""
    if not request.user.has_role('super_admin'):
        return redirect('core:dashboard')
    
    # Get date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    export_format = request.GET.get('export')
    
    # User activity
    school = getattr(request, 'school', None)
    memberships = active_memberships(school) if school else SchoolMembership.objects.filter(
        school__is_active=True, is_active=True, user__is_active=True,
    )
    active_user_ids = memberships.values_list('user_id', flat=True)
    people = User.objects.filter(pk__in=active_user_ids, is_active=True).distinct()
    total_users = people.count()
    active_users = people.filter(last_login__gte=start_date).count()
    
    # Role distribution
    role_stats = {}
    for role, _ in User.ROLE_CHOICES:
        count = people.filter(role=role).count()
        role_stats[role] = {
            'count': count,
            'percentage': (count / total_users * 100) if total_users > 0 else 0
        }
    
    # Quiz activity
    quiz_stats = {
        'total_quizzes': Quiz.objects.count(),
        'active_quizzes': Quiz.objects.filter(status='live').count(),
        'completed_attempts': QuizAttempt.objects.filter(is_submitted=True).count(),
        'recent_attempts': QuizAttempt.objects.filter(
            start_time__gte=start_date,
            is_submitted=True
        ).count()
    }
    
    # Result management
    result_stats = {
        'total_results': Result.objects.count(),
        'recent_results': Result.objects.filter(updated_at__gte=start_date).count(),
        'pending_results': Result.objects.filter(total_score=0).count()
    }
    
    # System resources
    system_stats = {
        'total_students': active_students(school).count(),
        'total_teachers': active_staff(school).count(),
        'total_classes': SchoolClass.objects.count(),
        'total_subjects': Subject.objects.count(),
        'database_size': 'N/A',  # Would need actual DB query
        'storage_used': 'N/A'    # Would need file system check
    }
    
    # Daily activity (last 7 days)
    daily_activity = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        logins = people.filter(last_login__date=date).count()
        quiz_attempts = QuizAttempt.objects.filter(start_time__date=date).count()
        daily_activity.append({
            'date': date,
            'logins': logins,
            'quiz_attempts': quiz_attempts
        })
    daily_activity.reverse()
    
    # Most active users
    active_users_list = people.filter(
        last_login__gte=start_date
    ).order_by('-last_login')[:10]
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'role_stats': role_stats,
        'quiz_stats': quiz_stats,
        'result_stats': result_stats,
        'system_stats': system_stats,
        'daily_activity': daily_activity,
        'active_users_list': active_users_list,
        'days_range': days,
    }
    
    # Export functionality
    if export_format == 'csv':
        return export_system_usage_csv(context)
    elif export_format == 'json':
        return export_system_usage_json(context)
    
    return render(request, 'reports/system_usage.html', context)

# Export functions
def export_academic_performance_csv(results, context):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="academic_performance_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Academic Performance Report'])
    writer.writerow(['Generated on:', timezone.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow([])
    
    # Summary
    writer.writerow(['Summary'])
    writer.writerow(['Total Students', context['total_students']])
    writer.writerow(['Average Score', context['avg_score']])
    writer.writerow(['Pass Rate (%)', context['pass_rate']])
    writer.writerow([])
    
    # Grade distribution
    writer.writerow(['Grade Distribution'])
    writer.writerow(['Grade', 'Count', 'Percentage'])
    for grade, stats in context['grade_stats'].items():
        writer.writerow([grade, stats['count'], f"{stats['percentage']:.1f}%"])
    
    return response

def export_attendance_csv(attendance_records, context):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Attendance Report'])
    writer.writerow(['Generated on:', timezone.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow([])
    
    # Summary
    writer.writerow(['Summary'])
    writer.writerow(['Total Students', context['total_students']])
    writer.writerow(['Average Attendance (%)', context['avg_attendance']])
    writer.writerow([])
    
    # Individual records
    writer.writerow(['Student Records'])
    writer.writerow(['Student ID', 'Student Name', 'Class', 'Days Present', 'Total Days', 'Attendance %'])
    for record in attendance_records:
        writer.writerow([
            record.student.student_id,
            record.student.user.get_full_name(),
            record.student.school_class.name,
            record.days_present,
            record.total_days,
            f"{record.percentage():.1f}%"
        ])
    
    return response

def export_system_usage_csv(context):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="system_usage_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['System Usage Report'])
    writer.writerow(['Generated on:', timezone.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow([])
    
    # User statistics
    writer.writerow(['User Statistics'])
    writer.writerow(['Total Users', context['total_users']])
    writer.writerow(['Active Users', context['active_users']])
    writer.writerow([])
    
    # Role distribution
    writer.writerow(['Role Distribution'])
    writer.writerow(['Role', 'Count', 'Percentage'])
    for role, stats in context['role_stats'].items():
        writer.writerow([role.title(), stats['count'], f"{stats['percentage']:.1f}%"])
    
    return response

def export_academic_performance_json(context):
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="academic_performance_report.json"'
    
    # Convert context to JSON-serializable format
    json_data = {
        'report_type': 'Academic Performance',
        'generated_at': timezone.now().isoformat(),
        'summary': {
            'total_students': context['total_students'],
            'average_score': context['avg_score'],
            'pass_rate': context['pass_rate']
        },
        'grade_distribution': context['grade_stats'],
        'subject_performance': [
            {
                'subject': perf['subject'].name,
                'average_score': float(perf['avg_score']),
                'pass_rate': perf['pass_rate'],
                'total_students': perf['total_students']
            } for perf in context['subject_performance']
        ],
        'class_performance': [
            {
                'class': perf['class'].name,
                'average_score': float(perf['avg_score']),
                'pass_rate': perf['pass_rate'],
                'total_students': perf['total_students']
            } for perf in context['class_performance']
        ]
    }
    
    return JsonResponse(json_data, json_dumps_params={'indent': 2})

def export_attendance_json(context):
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.json"'
    
    json_data = {
        'report_type': 'Attendance Report',
        'generated_at': timezone.now().isoformat(),
        'summary': {
            'total_students': context['total_students'],
            'average_attendance': context['avg_attendance'],
            'excellent_attendance': context['excellent_attendance'],
            'good_attendance': context['good_attendance'],
            'poor_attendance': context['poor_attendance']
        },
        'class_attendance': [
            {
                'class': att['class'].name,
                'attendance_rate': att['attendance_rate'],
                'total_students': att['total_students']
            } for att in context['class_attendance']
        ]
    }
    
    return JsonResponse(json_data, json_dumps_params={'indent': 2})

def export_system_usage_json(context):
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="system_usage_report.json"'
    
    json_data = {
        'report_type': 'System Usage Report',
        'generated_at': timezone.now().isoformat(),
        'user_statistics': {
            'total_users': context['total_users'],
            'active_users': context['active_users'],
            'role_distribution': context['role_stats']
        },
        'quiz_statistics': context['quiz_stats'],
        'result_statistics': context['result_stats'],
        'system_statistics': context['system_stats'],
        'daily_activity': [
            {
                'date': activity['date'].isoformat(),
                'logins': activity['logins'],
                'quiz_attempts': activity['quiz_attempts']
            } for activity in context['daily_activity']
        ]
    }
    
    return JsonResponse(json_data, json_dumps_params={'indent': 2})
