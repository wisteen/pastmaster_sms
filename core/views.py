from functools import lru_cache
from datetime import timedelta
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import connection, transaction
from django.db.models import Avg, Count, Q, Sum
from django.core.paginator import Paginator
import secrets
import os
from .models import *
from .models_biodata import Guardian
from .access_control import (
    student_has_result_access,
    user_has_portal_access,
    user_has_result_access,
)
from .decorators_features import feature_required
from .services_activity import get_recent_system_activity, get_teacher_activity
from .services_report_cards import report_component_rows
from .services_term_placements import (
    capture_before_promotion, capture_term_placement, placement_for_term,
    report_class_for_term, results_for_class, students_for_term,
)
from .services_portal_delivery import DeliverySummary, TenantPortalDeliveryService, delivery_channels_from_post
from .tenant_permissions import grant_school_admin_permissions
from .staffing import GENERIC_STAFF_ROLES, STAFF_ROLES, active_staff, active_students


ROLE_DISPLAY_MAP = {
    'student': 'Student',
    'parent': 'Parent',
    'subject_teacher': 'Subject Teacher',
    'class_teacher': 'Class Teacher',
    'librarian': 'Librarian',
    'accountant': 'Accountant',
    'bursar': 'Bursar',
    'security': 'Security',
    'cleaner': 'Cleaner',
    'clerk': 'Clerk',
    'driver': 'Driver',
    'nurse': 'Nurse',
    'maintenance': 'Maintenance Staff',
    'administrator': 'Administrator',
    'staff': 'Other / Non-teaching Staff',
    'super_admin': 'Administrator'
}


def role_selection_view(request):
    """Display role selection page"""
    return render(request, 'auth/role_selection.html')


def _role_profile_is_available(user, role):
    if role == 'student':
        return Student.objects.filter(user=user, status='active').exists()
    if role == 'super_admin' and user.is_superuser:
        return True
    if role in STAFF_ROLES:
        return active_staff().filter(user=user).exists()
    return True


def _dedupe_users(users):
    seen = set()
    unique_users = []
    for user in users:
        if not user or user.pk in seen:
            continue
        seen.add(user.pk)
        unique_users.append(user)
    return unique_users


def _tenant_user_queryset(school=None):
    queryset = User.objects.all()
    if school:
        queryset = queryset.filter(
            Q(is_superuser=True) |
            Q(
                school_memberships__school=school,
                school_memberships__is_active=True,
            )
        )
    return queryset.distinct()


def _credential_candidates(identifier, school=None):
    identifier = (identifier or '').strip()
    if not identifier:
        return []

    base_users = _tenant_user_queryset(school)
    candidates = []
    for lookup in [
        Q(username__iexact=identifier),
        Q(student__student_id__iexact=identifier),
        Q(teacher__employee_id__iexact=identifier),
        Q(email__iexact=identifier),
    ]:
        candidates.extend(base_users.filter(lookup).select_related('student', 'teacher'))
    return _dedupe_users(candidates)


def _user_matches_reset_role(user, role):
    if not role:
        return True
    return user.has_role(role) and _role_profile_is_available(user, role)


def _authenticate_portal_user(request, username, password):
    username = (username or '').strip()
    if not username:
        return None, None

    school = getattr(request, 'school', None)
    candidates = _credential_candidates(username, school)
    if not candidates:
        fallback_username = User.objects.filter(username__iexact=username).values_list('username', flat=True).first()
        candidates = _credential_candidates(fallback_username, school) if fallback_username else []

    for candidate in candidates:
        if candidate.check_password(password) and not candidate.is_active:
            return None, 'disabled'
        user = authenticate(request, username=candidate.username, password=password)
        if user:
            return user, None

    return None, None


def _resolve_password_reset_user(request, identifier, role=None):
    school = getattr(request, 'school', None)
    candidates = [
        user for user in _credential_candidates(identifier, school)
        if user.is_active and user_has_portal_access(user, school) and _user_matches_reset_role(user, role)
    ]
    email_candidates = [user for user in candidates if (user.email or '').strip()]
    if len(email_candidates) == 1:
        return email_candidates[0], None
    if len(email_candidates) > 1:
        return None, 'multiple'
    if candidates:
        return None, 'missing_email'
    return None, 'not_found'


def _password_reset_session_key():
    return 'portal_password_reset'


def _store_password_reset_session(request, user, code, role=None):
    expires_at = timezone.now() + timedelta(minutes=10)
    request.session[_password_reset_session_key()] = {
        'user_id': user.id,
        'school_id': getattr(getattr(request, 'school', None), 'id', None),
        'code_hash': make_password(code),
        'expires_at': expires_at.isoformat(),
        'role': role or '',
    }
    request.session.modified = True
    return expires_at


def _get_password_reset_session(request):
    data = request.session.get(_password_reset_session_key()) or {}
    try:
        expires_at = timezone.datetime.fromisoformat(data.get('expires_at'))
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return None, None
    if timezone.now() > expires_at:
        request.session.pop(_password_reset_session_key(), None)
        return None, None
    return data, expires_at


def _clear_password_reset_session(request):
    request.session.pop(_password_reset_session_key(), None)
    request.session.modified = True


def _mask_email(email):
    local, _, domain = (email or '').partition('@')
    if not local or not domain:
        return ''
    visible = local[:2] if len(local) > 2 else local[:1]
    return f'{visible}***@{domain}'


def _get_teacher_assessment_scope(teacher):
    """Return classes and subjects a teacher can use for assessment work."""
    assigned_class_ids = ClassTeacher.objects.filter(
        teacher=teacher,
        school_class__school=teacher.school,
    ).values_list('school_class_id', flat=True)
    classes = SchoolClass.all_objects.filter(
        school=teacher.school,
    ).filter(
        Q(id__in=teacher.classes.values_list('id', flat=True)) |
        Q(id__in=assigned_class_ids)
    ).distinct()
    subjects = teacher.subjects.filter(
        school=teacher.school,
        subject_type='academic',
    ).distinct()

    if teacher.user.has_role('class_teacher'):
        subjects = Subject.all_objects.filter(
            school=teacher.school,
            subject_type='academic',
        ).filter(
            Q(id__in=subjects.values_list('id', flat=True)) |
            Q(resultcomponent__school_class_id__in=assigned_class_ids)
        ).distinct()

    if not subjects.exists():
        subjects = Subject.all_objects.filter(
            school=teacher.school,
            subject_type='academic',
            resultcomponent__school_class__in=classes,
        ).distinct()

    if not subjects.exists():
        subjects = Subject.all_objects.filter(
            school=teacher.school,
            subject_type='academic',
            timetable__school_class__in=classes,
        ).distinct()

    return classes, subjects


def _get_teacher_dashboard_subjects(teacher, fallback_subjects=None):
    """Keep the dashboard count tied to the teacher's explicit assignment."""
    explicit_subjects = teacher.subjects.filter(
        school=teacher.school,
        subject_type='academic',
    ).distinct()
    if explicit_subjects.exists():
        return explicit_subjects
    if fallback_subjects is not None:
        return fallback_subjects
    return _get_teacher_assessment_scope(teacher)[1]


def _is_school_admin_user(user):
    if getattr(user, 'is_superuser', False):
        return True
    has_role = getattr(user, 'has_role', None)
    return bool(has_role and user.has_role('super_admin'))


def _teacher_result_adjustments_locked(user, term):
    return bool(term and term.result_published and not _is_school_admin_user(user))


def _request_user_has_result_access(request):
    school = getattr(request, 'school', None)
    if not school:
        return True
    return user_has_result_access(request.user, school)


def _deny_result_access_message(request):
    messages.error(request, 'Your result access for this school is disabled. Please contact the school administrator.')


def _get_class_teacher_assignments(teacher):
    return ClassTeacher.objects.filter(teacher=teacher).select_related('school_class').order_by(
        'school_class__name',
        'school_class__stream',
    )


def _get_class_teacher_assignment(teacher, class_id=None):
    assignments = _get_class_teacher_assignments(teacher)
    if class_id:
        return assignments.filter(school_class_id=class_id).first()
    return assignments.first()


def _class_teacher_assignments_for_user(user, school=None):
    assignments = ClassTeacher.all_objects.filter(
        teacher__user=user,
        teacher__status='active',
    ).select_related('teacher', 'school_class')
    if school:
        assignments = assignments.filter(
            teacher__school=school,
            school_class__school=school,
        )
    return assignments


def _class_teacher_class_ids_for_user(user, school=None):
    return list(
        _class_teacher_assignments_for_user(user, school).values_list('school_class_id', flat=True)
    )


def _teacher_report_class_ids(user, school=None, role=None):
    teacher_queryset = Teacher.all_objects.filter(user=user, status='active')
    if school:
        teacher_queryset = teacher_queryset.filter(school=school)
    teacher = teacher_queryset.first()
    if not teacher:
        return []

    role = role or getattr(user, 'role', None)
    if user.has_role('class_teacher'):
        class_ids = set(
            _class_teacher_assignments_for_user(user, school).values_list('school_class_id', flat=True)
        )
    else:
        class_ids = set(teacher.classes.values_list('id', flat=True))

    if school:
        class_ids = set(
            SchoolClass.all_objects.filter(school=school, id__in=class_ids).values_list('id', flat=True)
        )
    return list(class_ids)


def _user_can_print_or_download_class_records(request, school_class):
    school = getattr(request, 'school', None)
    if not school or not school_class or school_class.school_id != school.id:
        return False

    if request.user.has_role('super_admin'):
        return True

    if not request.user.has_role('class_teacher'):
        return False

    return _class_teacher_assignments_for_user(request.user, school).filter(
        school_class=school_class,
        can_print_download_results=True,
    ).exists()


def _user_can_view_student_report(request, student, term=None):
    school = getattr(request, 'school', None)
    if not school or student.school_id != school.id:
        return False

    if request.user.has_role('super_admin'):
        return True

    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return False

    report_class = report_class_for_term(student, term) if term else student.school_class
    return report_class is not None and report_class.id in _teacher_report_class_ids(
        request.user,
        student.school,
        role=request.session.get('selected_role') or getattr(request.user, 'role', None),
    )


def _teacher_can_manage_component_results(user, teacher, class_id, subject_id):
    """Check whether a teacher can manage a specific class/subject assessment."""
    if user.has_role('subject_teacher'):
        if teacher.classes.filter(id=class_id).exists() and teacher.subjects.filter(id=subject_id).exists():
            return True

    if user.has_role('class_teacher'):
        return (
            teacher.classes.filter(id=class_id).exists()
            or ClassTeacher.objects.filter(teacher=teacher, school_class_id=class_id).exists()
        )

    return False


def _teacher_can_manage_component_instance(user, teacher, student, component, term=None):
    """Check whether a teacher can update a specific component result."""
    report_class = report_class_for_term(student, term) if term else student.school_class
    if report_class is None or component.school_class_id != report_class.id:
        return False

    return _teacher_can_manage_component_results(
        user,
        teacher,
        report_class.id,
        component.subject_id
    )


def _teacher_quiz_scope(teacher):
    return _get_teacher_assessment_scope(teacher)


def _require_teacher_quiz_access(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        messages.error(request, 'You do not have permission to manage quizzes.')
        return None
    return Teacher.objects.filter(user=request.user).first()


def _tenant_terms_queryset(school):
    if not school:
        return Term.all_objects.none()
    return Term.all_objects.filter(school=school).order_by('-start_date', '-id')


def _selected_tenant_term(request, school):
    terms = _tenant_terms_queryset(school)
    term_id = request.GET.get('term_id') or request.POST.get('term_id')
    selected_term = terms.filter(id=term_id).first() if term_id else None
    if not selected_term:
        selected_term = terms.filter(is_active=True).first() or terms.first()
    return terms, selected_term


def _broadsheet_class_scope(request):
    school = getattr(request, 'school', None)
    empty_classes = SchoolClass.all_objects.none()
    empty_assignments = ClassTeacher.all_objects.none()
    if not school:
        return empty_classes, empty_assignments, None, False

    if request.user.has_role('super_admin'):
        return (
            SchoolClass.all_objects.filter(school=school).order_by('name', 'stream'),
            empty_assignments,
            None,
            True,
        )

    if not request.user.has_role('class_teacher'):
        return empty_classes, empty_assignments, None, False

    teacher = Teacher.all_objects.filter(user=request.user, school=school, status='active').first()
    if not teacher:
        return empty_classes, empty_assignments, None, False

    assignments = ClassTeacher.all_objects.filter(
        teacher=teacher,
        school_class__school=school,
    ).select_related('school_class').order_by('school_class__name', 'school_class__stream')
    classes = SchoolClass.all_objects.filter(
        school=school,
        id__in=assignments.values_list('school_class_id', flat=True),
    ).order_by('name', 'stream')
    return classes, assignments, teacher, False


def _selected_broadsheet_scope(request):
    class_options, assignments, teacher, is_admin_broadsheet = _broadsheet_class_scope(request)
    class_id = request.GET.get('class_id') or request.POST.get('class_id')
    selected_class = class_options.filter(id=class_id).first() if class_id else None
    if not selected_class:
        selected_class = class_options.first()
    selected_assignment = (
        assignments.filter(school_class=selected_class).first()
        if selected_class and assignments.exists()
        else None
    )
    return {
        'class_options': class_options,
        'class_teacher_assignments': assignments,
        'teacher': teacher,
        'selected_class': selected_class,
        'class_teacher': selected_assignment,
        'is_admin_broadsheet': is_admin_broadsheet,
    }


def _broadsheet_subjects(school, school_class, term):
    if not school or not school_class:
        return Subject.all_objects.none()

    return Subject.all_objects.filter(
        school=school,
        subject_type='academic',
        resultcomponent__school_class=school_class,
        resultcomponent__school_class__school=school,
    ).distinct().order_by('name', 'code')


def _build_broadsheet_context(request):
    school = getattr(request, 'school', None)
    terms, selected_term = _selected_tenant_term(request, school)
    scope = _selected_broadsheet_scope(request)
    selected_class = scope['selected_class']

    students = list(
        students_for_term(school, selected_class, selected_term).select_related(
            'user', 'school_class',
        ).order_by('user__first_name', 'user__last_name', 'student_id')
    ) if school and selected_class else []

    subjects = list(_broadsheet_subjects(school, selected_class, selected_term))
    subject_scores = {subject.code: [] for subject in subjects}
    broadsheet_data = []

    results = {}
    comments = {}
    if students and selected_term:
        student_ids = [student.id for student in students]
        subject_ids = [subject.id for subject in subjects]
        results = {
            (result.student_id, result.subject_id): result
            for result in Result.all_objects.filter(
                student_id__in=student_ids,
                subject_id__in=subject_ids,
                subject__school=school,
                term=selected_term,
            ).select_related('subject', 'student')
        }
        comments = {
            comment.student_id: comment
            for comment in Comment.all_objects.filter(
                student_id__in=student_ids,
                term=selected_term,
            )
        }

    for student in students:
        student_results = {}
        total_score = 0
        subject_count = 0

        for subject in subjects:
            result = results.get((student.id, subject.id))
            if result:
                score = float(result.total_score)
                student_results[subject.code] = {
                    'total': score,
                    'grade': result.grade,
                }
                total_score += score
                subject_count += 1
                subject_scores[subject.code].append({'student': student, 'score': score})
            else:
                student_results[subject.code] = {'total': '-', 'grade': '-'}

        average = total_score / subject_count if subject_count > 0 else 0
        comment = comments.get(student.id)

        broadsheet_data.append({
            'student': student,
            'results': student_results,
            'total_score': total_score,
            'average': round(average, 2),
            'teacher_comment': comment.teacher_comment if comment else '',
            'ht_comment': comment.proprietor_comment if comment else '',
            'ht_comment_mode': 'manual',
            'subject_positions': {},
        })

    broadsheet_data.sort(key=lambda x: (x['average'], x['total_score']), reverse=True)
    for idx, data in enumerate(broadsheet_data, 1):
        data['class_position'] = idx

    for subject_code, scores in subject_scores.items():
        scores.sort(key=lambda x: x['score'], reverse=True)
        for idx, score_data in enumerate(scores, 1):
            for data in broadsheet_data:
                if data['student'] == score_data['student']:
                    data['subject_positions'][subject_code] = idx
                    break

    best_per_subject = {}
    subject_averages = {}
    for subject_code, scores in subject_scores.items():
        if scores:
            best = max(scores, key=lambda x: x['score'])
            best_per_subject[subject_code] = {
                'score': best['score'],
                'student': best['student'].user.get_full_name(),
            }
            subject_averages[subject_code] = sum(s['score'] for s in scores) / len(scores)
        else:
            subject_averages[subject_code] = 0

    grand_total = sum(data['total_score'] for data in broadsheet_data)
    grand_average = sum(data['average'] for data in broadsheet_data) / len(broadsheet_data) if broadsheet_data else 0
    results_locked = bool(selected_term and selected_term.result_published)
    is_admin_broadsheet = scope['is_admin_broadsheet']

    context = {
        'broadsheet_data': broadsheet_data,
        'subjects': subjects,
        'terms': terms,
        'term': selected_term,
        'selected_class': selected_class,
        'class_options': scope['class_options'],
        'class_name': str(selected_class) if selected_class else '',
        'class_teacher': scope['class_teacher'],
        'class_teacher_assignments': scope['class_teacher_assignments'],
        'is_admin_broadsheet': is_admin_broadsheet,
        'results_locked': results_locked,
        'can_save_teacher_comments': (
            bool(selected_term and selected_class)
            and not is_admin_broadsheet
            and request.user.has_role('class_teacher')
            and not results_locked
        ),
        'can_save_admin_comments': bool(selected_term and selected_class and is_admin_broadsheet),
        'can_print_download': _user_can_print_or_download_class_records(request, selected_class),
        'best_per_subject': best_per_subject,
        'subject_averages': subject_averages,
        'grand_total': grand_total,
        'grand_average': grand_average,
        'total_students': len(students),
    }
    return context


@ensure_csrf_cookie
def login_view(request):
    # Get selected role from query parameter or POST data
    selected_role = request.GET.get('role') or request.POST.get('role')
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role')
        
        # Authenticate user
        user, auth_error = _authenticate_portal_user(request, username, password)
        
        if user:
            school = getattr(request, 'school', None)
            if school and not user_has_portal_access(user, school):
                messages.error(request, 'Your portal access for this school is disabled. Please contact the school administrator.')
                return render(request, 'auth/login.html', {
                    'selected_role': role,
                    'selected_role_display': ROLE_DISPLAY_MAP.get(role, role),
                    'next_url': next_url,
                })

            # Verify that user's role matches the selected role
            available_roles = user.get_all_roles()
            generic_staff_login = role == 'staff' and bool(set(available_roles).intersection(GENERIC_STAFF_ROLES))
            administrator_login = role == 'super_admin' and 'administrator' in available_roles
            if role and not user.has_role(role) and not generic_staff_login and not administrator_login:
                messages.error(request, f'Invalid credentials. This account is not registered as a {ROLE_DISPLAY_MAP.get(role, role)}.')
                return render(request, 'auth/login.html', {
                    'selected_role': role,
                    'selected_role_display': ROLE_DISPLAY_MAP.get(role, role),
                    'next_url': next_url,
                })

            if role and not _role_profile_is_available(user, role):
                messages.error(request, f'This account has {ROLE_DISPLAY_MAP.get(role, role)} access, but the required profile is not linked yet.')
                return render(request, 'auth/login.html', {
                    'selected_role': role,
                    'selected_role_display': ROLE_DISPLAY_MAP.get(role, role),
                    'next_url': next_url,
                })
            
            # Login successful
            login(request, user)
            if user.has_role('super_admin'):
                grant_school_admin_permissions(user)
                if not user.is_superuser and user.is_staff:
                    user.is_staff = False
                    user.save(update_fields=['is_staff'])
            selected_login_role = role or (available_roles[0] if available_roles else None)
            if generic_staff_login and role not in available_roles:
                selected_login_role = next(
                    (item for item in available_roles if item in GENERIC_STAFF_ROLES),
                    selected_login_role,
                )
            if administrator_login:
                selected_login_role = 'administrator'
            if selected_login_role:
                request.session['selected_role'] = selected_login_role
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            if role in ['accountant', 'bursar']:
                return redirect('financial:financial_dashboard')
            if role == 'librarian':
                return redirect('library_dashboard')
            return redirect('core:dashboard')
        else:
            if auth_error == 'disabled':
                messages.error(request, 'This account is disabled. Please contact the school administrator.')
            else:
                messages.error(request, 'Invalid username or password')
            return render(request, 'auth/login.html', {
                'selected_role': role,
                'selected_role_display': ROLE_DISPLAY_MAP.get(role, role),
                'next_url': next_url,
            })
    
    # GET request - show login form
    return render(request, 'auth/login.html', {
        'selected_role': selected_role,
        'selected_role_display': ROLE_DISPLAY_MAP.get(selected_role, '') if selected_role else None,
        'next_url': next_url,
    })


@ensure_csrf_cookie
def password_reset_view(request):
    selected_role = request.GET.get('role') or request.POST.get('role') or ''
    step = request.POST.get('step') or request.GET.get('step') or 'request'
    if request.method == 'GET' and request.GET.get('new') == '1':
        _clear_password_reset_session(request)
        step = 'request'
    context = {
        'selected_role': selected_role,
        'selected_role_display': ROLE_DISPLAY_MAP.get(selected_role, selected_role),
        'step': step,
    }

    reset_data, expires_at = _get_password_reset_session(request)
    if reset_data:
        context.update({
            'step': 'confirm',
            'masked_email': reset_data.get('masked_email', ''),
            'expires_at': expires_at,
            'selected_role': reset_data.get('role') or selected_role,
            'selected_role_display': ROLE_DISPLAY_MAP.get(reset_data.get('role') or selected_role, selected_role),
        })

    if request.method != 'POST':
        return render(request, 'auth/password_reset.html', context)

    if step == 'request':
        identifier = request.POST.get('identifier', '').strip()
        user, error = _resolve_password_reset_user(request, identifier, selected_role)
        if user:
            code = f'{secrets.randbelow(1000000):06d}'
            expires_at = _store_password_reset_session(request, user, code, selected_role)
            request.session[_password_reset_session_key()]['masked_email'] = _mask_email(user.email)
            request.session.modified = True
            service = TenantPortalDeliveryService(getattr(request, 'school', None), request=request)
            summary = service.send_password_reset_code(user, code, expires_at)
            if summary.sent:
                messages.success(request, f'A reset code has been sent to {_mask_email(user.email)}.')
                return redirect(f"{reverse('core:password_reset')}?step=confirm")
            _clear_password_reset_session(request)
            messages.error(request, summary.as_message() or 'Unable to send reset email. Please contact the school administrator.')
        elif error == 'missing_email':
            messages.error(request, 'This account does not have an email address. Please contact the school administrator.')
        elif error == 'multiple':
            messages.error(request, 'More than one account matches that email. Use your username, student ID, or staff ID.')
        else:
            messages.error(request, 'No active portal account was found for those details.')

        context.update({'identifier': identifier, 'step': 'request'})
        return render(request, 'auth/password_reset.html', context)

    if step == 'confirm':
        reset_data, expires_at = _get_password_reset_session(request)
        if not reset_data:
            messages.error(request, 'The reset code has expired. Request a new code.')
            return redirect(f"{reverse('core:password_reset')}?role={selected_role}")

        code = request.POST.get('code', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        user = _tenant_user_queryset(getattr(request, 'school', None)).filter(id=reset_data.get('user_id')).first()

        if not user:
            _clear_password_reset_session(request)
            messages.error(request, 'This reset request is no longer valid.')
            return redirect(f"{reverse('core:password_reset')}?role={selected_role}")

        if not check_password(code, reset_data.get('code_hash', '')):
            messages.error(request, 'Invalid reset code.')
            context.update({'step': 'confirm', 'masked_email': reset_data.get('masked_email', ''), 'expires_at': expires_at})
            return render(request, 'auth/password_reset.html', context)

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            context.update({'step': 'confirm', 'masked_email': reset_data.get('masked_email', ''), 'expires_at': expires_at})
            return render(request, 'auth/password_reset.html', context)

        try:
            validate_password(new_password, user)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)
            context.update({'step': 'confirm', 'masked_email': reset_data.get('masked_email', ''), 'expires_at': expires_at})
            return render(request, 'auth/password_reset.html', context)

        user.set_password(new_password)
        user.save(update_fields=['password'])
        _clear_password_reset_session(request)
        messages.success(request, 'Password reset successful. Sign in with your new password.')
        login_url = reverse('core:login')
        role = reset_data.get('role')
        if role:
            login_url = f'{login_url}?role={role}'
        return redirect(login_url)

    messages.error(request, 'Invalid reset request.')
    return redirect(reverse('core:password_reset'))

def _render_security_dashboard(request, context, school):
    from .models_attendance import AttendanceRecord, Visitor

    today = timezone.localdate()
    today_records = AttendanceRecord.objects.filter(
        session__date=today,
    ).filter(
        Q(student_id__in=active_students(school).values_list('pk', flat=True)) |
        Q(teacher_id__in=active_staff(school).values_list('pk', flat=True))
    ).select_related('student__user', 'teacher__user', 'session', 'id_card')
    visitors = Visitor.all_objects.filter(check_in_time__date=today)
    if school:
        today_records = today_records.filter(session__school=school)
        visitors = visitors.filter(school=school)

    staff_count = today_records.filter(
        teacher__isnull=False,
    ).values('teacher_id').distinct().count()
    context.update({
        'today_total': today_records.values('id_card_id').distinct().count(),
        'today_students': today_records.filter(student__isnull=False).values('student_id').distinct().count(),
        'today_teachers': staff_count,
        'today_staff': staff_count,
        'on_premises': today_records.filter(check_out_time__isnull=True).values('id_card_id').distinct().count(),
        'fees_owing': today_records.filter(
            student__isnull=False,
            student__studentfee__status__in=['pending', 'partial', 'overdue'],
        ).values('student_id').distinct().count(),
        'recent_records': today_records.order_by('-check_in_time')[:10],
        'visitors_today': visitors.count(),
        'active_visitors': visitors.filter(check_out_time__isnull=True).count(),
    })
    return render(request, 'dashboards/security.html', context)


@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}
    selected_role = request.session.get('selected_role')
    school = getattr(request, 'school', None)

    student_profile = active_students(school).filter(user=user).select_related('school_class').first()
    teacher_profile = active_staff(school).filter(user=user).first()

    if selected_role == 'student' and not student_profile:
        messages.warning(request, 'This user is not linked to a student profile, so the student dashboard is unavailable.')
        request.session.pop('selected_role', None)
        selected_role = None

    if selected_role in ['subject_teacher', 'class_teacher'] and not teacher_profile:
        messages.warning(request, 'This user is not linked to a teacher profile, so the teacher dashboard is unavailable.')
        request.session.pop('selected_role', None)
        selected_role = None

    if selected_role in ['accountant', 'bursar'] and user.has_any_role(['accountant', 'bursar']):
        return redirect('financial:financial_dashboard')

    if selected_role == 'librarian' and user.has_role('librarian'):
        return redirect('library_dashboard')

    if selected_role == 'parent' and user.has_role('parent'):
        return parent_dashboard(request)

    if selected_role == 'administrator' and user.has_role('administrator') and school:
        return redirect('core:school_admin_dashboard')

    if selected_role == 'security' and user.has_role('security'):
        return _render_security_dashboard(request, context, school)
    
    if user.has_role('super_admin') and selected_role in [None, 'super_admin']:
        if school:
            total_students = active_students(school).count()
            total_teachers = active_staff(school).count()
            total_classes = SchoolClass.all_objects.filter(school=school).count()
            total_subjects = Subject.all_objects.filter(school=school).count()
        else:
            total_students = active_students().count()
            total_teachers = active_staff().count()
            total_classes = SchoolClass.objects.count()
            total_subjects = Subject.objects.count()
        context.update({
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_classes': total_classes,
            'total_subjects': total_subjects,
            'recent_system_activity': get_recent_system_activity(school=school),
            'can_open_school_admin': bool(school),
        })
        return render(request, 'dashboards/super_admin.html', context)

    if user.has_role('student') and student_profile and selected_role in [None, 'student']:
        student = student_profile
        now = timezone.now()
        live_quizzes = Quiz.objects.filter(
            school_class=student.school_class,
            status__in=['live', 'scheduled'],
            start_time__lte=now,
            end_time__gte=now,
        ).select_related('subject').order_by('end_time')
        recent_results = Result.objects.filter(
            student=student,
            term__result_published=True,
        ).select_related('subject', 'term').order_by('-updated_at')[:5]
        today_attendance = DailyAttendanceRecord.objects.filter(
            student=student,
            session__date=timezone.localdate(),
        ).select_related('session').first()
        context.update({
            'student': student,
            'live_quizzes': live_quizzes,
            'recent_results': recent_results,
            'today_attendance': today_attendance,
            'result_access_enabled': student_has_result_access(student),
        })
        return render(request, 'dashboards/student.html', context)

    if user.has_role('parent') and selected_role in [None, 'parent']:
        return parent_dashboard(request)
    
    elif selected_role not in ['security'] and user.has_any_role(['subject_teacher', 'class_teacher']) and teacher_profile:
        teacher = teacher_profile
        assessment_classes, assessment_subjects = _get_teacher_assessment_scope(teacher)
        dashboard_subjects = _get_teacher_dashboard_subjects(teacher, assessment_subjects)
        
        class_teacher_assignments = _get_class_teacher_assignments(teacher)
        class_teacher = class_teacher_assignments.first()
        is_class_teacher = class_teacher is not None

        context.update({
            'teacher': teacher,
            'is_class_teacher': is_class_teacher,
            'class_teacher': class_teacher,
            'class_teacher_assignments': class_teacher_assignments,
            'my_classes': assessment_classes,
            'my_subjects': dashboard_subjects,
            'recent_teacher_activity': get_teacher_activity(teacher),
            'pending_results': Result.objects.filter(
                student__school_class__in=assessment_classes,
                total_score=0
            ).count() if is_class_teacher else Result.objects.filter(
                subject__in=assessment_subjects,
                student__school_class__in=assessment_classes,
                total_score=0
            ).count()
        })
        return render(request, 'dashboards/unified_teacher.html', context)

    elif user.has_role('super_admin'):
        if school:
            total_students = active_students(school).count()
            total_teachers = active_staff(school).count()
            total_classes = SchoolClass.all_objects.filter(school=school).count()
            total_subjects = Subject.all_objects.filter(school=school).count()
        else:
            total_students = active_students().count()
            total_teachers = active_staff().count()
            total_classes = SchoolClass.objects.count()
            total_subjects = Subject.objects.count()
        context.update({
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_classes': total_classes,
            'total_subjects': total_subjects,
            'recent_system_activity': get_recent_system_activity(school=school),
            'can_open_school_admin': bool(school),
        })
        return render(request, 'dashboards/super_admin.html', context)
    
    elif user.has_role('librarian'):
        # Redirect librarian to library dashboard
        return redirect('library_dashboard')
    
    elif user.has_role('security'):
        return _render_security_dashboard(request, context, school)

    elif teacher_profile and set(user.get_all_roles()).intersection(STAFF_ROLES):
        context.update({
            'staff_profile': teacher_profile,
            'staff_title': teacher_profile.get_staff_title(),
            'id_card': getattr(teacher_profile, 'id_card', None),
        })
        return render(request, 'dashboards/staff.html', context)
    
    # Fallback for any other roles
    messages.warning(request, 'Your role does not have a specific dashboard. Please contact administrator.')
    return redirect('core:login')


@login_required
def switch_role(request, role):
    if not request.user.has_role(role):
        messages.error(request, 'You do not have access to that role.')
        return redirect('core:dashboard')

    if not _role_profile_is_available(request.user, role):
        messages.error(request, 'That dashboard is unavailable because this user is not linked to the required profile.')
        return redirect('core:dashboard')

    request.session['selected_role'] = role

    if role in ['accountant', 'bursar']:
        return redirect('financial:financial_dashboard')
    if role == 'librarian':
        return redirect('library_dashboard')
    if role == 'security':
        return redirect('core:dashboard')
    if role == 'administrator':
        return redirect('core:school_admin_dashboard')
    return redirect('core:dashboard')


@login_required
def switch_school(request, slug):
    school = get_object_or_404(SchoolTenant, slug=slug, is_active=True)
    membership = SchoolMembership.objects.filter(
        school=school,
        user=request.user,
        is_active=True,
        portal_access_enabled=True,
    ).first()

    if not membership and not request.user.is_superuser:
        messages.error(request, 'You do not have access to that school portal.')
        return redirect('core:dashboard')

    request.session['active_school_id'] = school.id
    if membership:
        request.session['selected_role'] = membership.primary_role
    else:
        request.session.pop('selected_role', None)

    messages.success(request, f'Switched to {school.name}.')
    return redirect('core:dashboard')


@login_required
def parent_dashboard(request):
    user = request.user
    if not user.has_role('parent'):
        messages.error(request, 'You do not have access to the parent dashboard.')
        return redirect('core:dashboard')

    school = getattr(request, 'school', None)
    parent_result_access_enabled = user_has_result_access(user, school) if school else True
    guardian_links = Guardian.objects.filter(user=user).select_related('student__user', 'student__school_class')
    if user.email:
        guardian_links = guardian_links | Guardian.objects.filter(
            user__isnull=True,
            email__iexact=user.email
        ).select_related('student__user', 'student__school_class')

    wards = Student.objects.filter(guardians__in=guardian_links).select_related('user', 'school_class').distinct()
    ward_cards = []

    for ward in wards:
        ward_result_access_enabled = parent_result_access_enabled and student_has_result_access(ward)
        published_results = Result.objects.filter(
            student=ward,
            term__result_published=True,
        ) if ward_result_access_enabled else Result.objects.none()
        recent_results = published_results.select_related('subject', 'term').order_by('-updated_at')[:5]
        average_score = published_results.aggregate(avg=Avg('total_score'))['avg'] or 0
        quiz_attempts = QuizAttempt.objects.filter(student=ward).select_related('quiz__subject').order_by('-end_time', '-start_time')[:5]
        latest_attendance = Attendance.objects.filter(student=ward).select_related('term').order_by('-term__start_date')[:1].first()
        fees = StudentFee.objects.filter(student=ward).select_related('fee_structure__term').order_by('-created_at')[:3]

        ward_cards.append({
            'student': ward,
            'recent_results': recent_results,
            'average_score': average_score,
            'quiz_attempts': quiz_attempts,
            'latest_attendance': latest_attendance,
            'fees': fees,
            'result_access_enabled': ward_result_access_enabled,
        })

    return render(request, 'dashboards/parent.html', {
        'ward_cards': ward_cards,
        'total_wards': wards.count(),
    })


@login_required
def activity_log(request):
    user = request.user
    school = getattr(request, 'school', None)

    if user.has_role('super_admin'):
        activities = get_recent_system_activity(limit=None, school=school)
        title = 'School Activity Log'
    elif user.has_any_role(['subject_teacher', 'class_teacher']):
        teacher = get_object_or_404(Teacher, user=user)
        activities = get_teacher_activity(teacher, limit=None)
        title = 'Teacher Activity Log'
    else:
        messages.error(request, 'You do not have permission to view the activity log.')
        return redirect('core:dashboard')

    paginator = Paginator(activities, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'activity_log.html', {
        'title': title,
        'page_obj': page_obj,
    })

@login_required
def get_students_by_class(request):
    """AJAX view to get students for a specific class"""
    class_id = request.GET.get('class_id')
    if class_id:
        students = Student.objects.filter(school_class_id=class_id).select_related('user')
        student_data = [
            {
                'id': student.id,
                'name': student.user.get_full_name(),
                'student_id': student.student_id
            }
            for student in students
        ]
        return JsonResponse({'students': student_data})
    return JsonResponse({'students': []})

@login_required
def get_recent_results(request):
    """AJAX view to get recent results for a class and subject"""
    if not _request_user_has_result_access(request):
        return JsonResponse({'error': 'Result access disabled'}, status=403)

    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if class_id and subject_id:
        teacher = Teacher.objects.get(user=request.user)
        
        # Verify teacher can access this data
        if not _teacher_can_manage_component_results(request.user, teacher, class_id, subject_id):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        school_class = get_object_or_404(SchoolClass.all_objects, pk=class_id, school=teacher.school)
        results = results_for_class(teacher.school, school_class).filter(
            subject_id=subject_id
        ).select_related('student__user', 'term').order_by('-updated_at')[:10]
        
        result_data = [
            {
                'student_name': result.student.user.get_full_name(),
                'student_id': result.student.student_id,
                'total_score': float(result.total_score),
                'grade': result.grade,
                'grade_point': float(result.grade_point),
                'remark': result.remark,
                'term': result.term.name,
                'updated_at': result.updated_at.strftime('%Y-%m-%d %H:%M')
            }
            for result in results
        ]
        return JsonResponse({'results': result_data})
    
    return JsonResponse({'results': []})

@login_required
def student_results(request):
    if not request.user.has_role('student'):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    student = Student.objects.get(user=request.user)
    results = Result.objects.filter(
        student=student,
        term__result_published=True,
    ).order_by('-term__start_date', 'subject__name')
    return render(request, 'student/results.html', {'results': results})

def student_cbt_dashboard(request):
    from .views_quiz import student_cbt_dashboard as handler
    return handler(request)


def take_quiz(request, quiz_id):
    from .views_quiz import take_quiz as handler
    return handler(request, quiz_id)

@login_required
@feature_required('reports_results')
def manage_results(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    
    if request.method == 'POST':
        messages.info(request, 'Please use the Component Results system for entering scores.')
        return redirect('core:component_results')
    
    classes, subjects = _get_teacher_assessment_scope(teacher)
    active_term = Term.objects.filter(is_active=True).first()
    
    return render(request, 'teacher/manage_results.html', {
        'classes': classes,
        'subjects': subjects,
        'active_term': active_term
    })

def create_quiz(request):
    from .views_quiz import create_quiz as handler
    return handler(request)

def quiz_management(request):
    from .views_quiz import quiz_management as handler
    return handler(request)

def edit_quiz(request, quiz_id):
    from .views_quiz import edit_quiz as handler
    return handler(request, quiz_id)

def quiz_results(request, quiz_id):
    from .views_quiz import quiz_results as handler
    return handler(request, quiz_id)

def grade_theory(request, quiz_id):
    from .views_quiz import grade_theory as handler
    return handler(request, quiz_id)

def delete_quiz(request, quiz_id):
    from .views_quiz import delete_quiz as handler
    return handler(request, quiz_id)

@login_required
def subscribe_ai(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    messages.info(request, 'AI question import is now free for all teachers.')
    return redirect('core:import_questions_ai')

@login_required
def verify_payment(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    messages.info(request, 'AI question import is now free; no payment verification is needed.')
    return redirect('core:import_questions_ai')

@login_required
def import_questions_ai(request):
    if not request.user.has_role('subject_teacher'):
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    
    if request.method == 'POST':
        text_content = request.POST.get('text_content')
        subject_id = request.POST.get('subject_id')
        school_class_id = request.POST.get('school_class_id') or None
        
        try:
            from .ai_question_importer import AIQuestionImporter
            importer = AIQuestionImporter()
            
            # Extract questions using AI
            extracted_data = importer.extract_questions_from_text(text_content, subject_id)
            
            # Import to database
            imported_count = importer.import_to_database(
                extracted_data, 
                subject_id, 
                teacher, 
                school_class_id
            )
            
            messages.success(request, f'Successfully imported {imported_count} questions using AI!')
            return redirect('core:question_bank')
        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')
    
    return render(request, 'teacher/import_questions_ai.html', {
        'subjects': teacher.subjects.all(),
        'classes': teacher.classes.all()
    })

@login_required
@feature_required('cbt_quiz')
def question_bank(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    
    teacher = get_object_or_404(Teacher, user=request.user, status='active')
    from .forms_quiz import QuestionBankForm
    classes, subjects = _teacher_quiz_scope(teacher)
    quiz = None
    if request.GET.get('quiz_id', '').isdigit():
        quiz = get_object_or_404(Quiz, pk=request.GET['quiz_id'], teacher=teacher)
        subjects = subjects.filter(pk=quiz.subject_id)
    form = QuestionBankForm(request.POST if request.method == 'POST' else None, classes=classes, subjects=subjects)
    
    if request.method == 'POST':
        if form.is_valid():
            question = form.save(commit=False)
            question.created_by = teacher
            question.save()
            messages.success(request, 'Question added to bank')
            return redirect(request.get_full_path())
    
    # Organize questions by groups and standalone
    groups = QuestionGroup.objects.filter(subject__in=subjects).prefetch_related('questions')
    standalone_questions = QuestionBank.objects.filter(subject__in=subjects, group__isnull=True).order_by('-created_at')
    
    questions_data = []
    for group in groups:
        questions_data.append({'type': 'group', 'group': group, 'questions': group.questions.all()})
    for question in standalone_questions:
        questions_data.append({'type': 'question', 'question': question})
    
    return render(request, 'teacher/question_bank.html', {
        'questions_data': questions_data,
        'subjects': subjects,
        'classes': classes,
        'quiz': quiz,
        'teacher': teacher,
        'form': form
    })

@login_required
def upload_image(request):
    if request.method == 'POST' and request.FILES.get('upload'):
        import os
        from django.conf import settings
        
        upload = request.FILES['upload']
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, upload.name)
        with open(file_path, 'wb+') as destination:
            for chunk in upload.chunks():
                destination.write(chunk)
        
        url = f"{settings.MEDIA_URL}uploads/{upload.name}"
        return JsonResponse({'uploaded': 1, 'fileName': upload.name, 'url': url})
    
    return JsonResponse({'uploaded': 0, 'error': {'message': 'Upload failed'}})

@login_required
@feature_required('cbt_quiz')
def create_question_group(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if request.method == 'POST':
        teacher = get_object_or_404(Teacher, user=request.user, status='active')
        from .forms_quiz import content_present
        _, subjects = _teacher_quiz_scope(teacher)
        subject_id = request.POST.get('subject')
        instruction = request.POST.get('instruction')
        if not str(subject_id or '').isdigit() or not subjects.filter(pk=subject_id).exists() or not content_present(instruction):
            messages.error(request, 'Choose an assigned subject and enter the passage or instructions.')
            return redirect('core:question_bank')
        group = QuestionGroup.objects.create(
            subject_id=subject_id,
            instruction=instruction,
            created_by=teacher
        )
        messages.success(request, 'Question group created successfully')
        return redirect('core:question_bank')
    return redirect('core:question_bank')

def add_question_from_bank(request):
    from .views_quiz import add_question_from_bank as handler
    return handler(request)

def add_group_from_bank(request):
    from .views_quiz import add_group_from_bank as handler
    return handler(request)

def edit_question(request, question_id):
    from .views_quiz import edit_question as handler
    return handler(request, question_id)

def delete_question(request, question_id):
    from .views_quiz import delete_question as handler
    return handler(request, question_id)

def add_questions(request, quiz_id):
    from .views_quiz import add_questions as handler
    return handler(request, quiz_id)

@login_required
@feature_required('reports_broadsheet')
def class_broadsheet(request):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    if not getattr(request, 'school', None):
        messages.error(request, 'Open a school tenant before viewing broadsheets.')
        return redirect('core:dashboard')

    context = _build_broadsheet_context(request)
    if not context['selected_class']:
        messages.error(request, 'No class is available for your broadsheet scope.')
        return redirect('core:dashboard')
    if not context['term']:
        messages.error(request, 'Create a term before viewing broadsheets.')
    return render(request, 'class_teacher/broadsheet.html', context)


@login_required
@feature_required('reports_broadsheet')
def print_broadsheet(request):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    if not getattr(request, 'school', None):
        messages.error(request, 'Open a school tenant before printing broadsheets.')
        return redirect('core:dashboard')

    context = _build_broadsheet_context(request)
    if not context['selected_class']:
        messages.error(request, 'No class is available for your broadsheet scope.')
        return redirect('core:dashboard')
    if not context['can_print_download']:
        messages.error(request, 'Your account is view-only for this class broadsheet. Ask the school admin to enable print/download access.')
        return redirect('core:class_broadsheet')
    context['school_settings'] = SchoolSettings.get_for_school(getattr(request, 'school', None))
    return render(request, 'class_teacher/print_broadsheet.html', context)


@login_required
@feature_required('reports_broadsheet')
def download_broadsheet(request):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    if not getattr(request, 'school', None):
        messages.error(request, 'Open a school tenant before downloading broadsheets.')
        return redirect('core:dashboard')

    context = _build_broadsheet_context(request)
    if not context['selected_class']:
        messages.error(request, 'No class is available for your broadsheet scope.')
        return redirect('core:dashboard')
    if not context['can_print_download']:
        messages.error(request, 'Your account is view-only for this class broadsheet. Ask the school admin to enable print/download access.')
        return redirect('core:class_broadsheet')

    from html import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    school_class = context['selected_class']
    term = context['term']
    filename_parts = [
        'broadsheet',
        str(school_class).replace(' ', '_'),
    ]
    if term:
        filename_parts.extend([term.session.replace('/', '-'), term.name.replace(' ', '_')])
    filename = '_'.join(filename_parts) + '.pdf'

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    subjects = context['subjects']
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        response,
        pagesize=page_size,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=9 * mm,
    )
    usable_width = page_size[0] - doc.leftMargin - doc.rightMargin
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'BroadsheetTitle',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        spaceAfter=3,
    )
    meta_style = ParagraphStyle(
        'BroadsheetMeta',
        parent=styles['Normal'],
        alignment=TA_CENTER,
        fontSize=7,
        leading=8,
        spaceAfter=6,
    )
    cell_font_size = 5.2 if len(subjects) > 12 else 6
    cell_style = ParagraphStyle(
        'BroadsheetCell',
        parent=styles['Normal'],
        fontSize=cell_font_size,
        leading=cell_font_size + .8,
    )
    header_style = ParagraphStyle(
        'BroadsheetHeaderCell',
        parent=cell_style,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    )

    def p(value, style=cell_style):
        return Paragraph(escape(str(value or '')).replace('\n', '<br/>'), style)

    fixed_widths = [
        16 * mm,  # position
        35 * mm,  # student
        15 * mm,  # total
        15 * mm,  # average
        16 * mm,  # class position
        28 * mm,  # teacher comment
        28 * mm,  # admin comment
    ]
    subject_column_count = max(1, len(subjects) * 2)
    subject_width = (usable_width - sum(fixed_widths)) / subject_column_count
    subject_width = max(7 * mm, subject_width)
    col_widths = [fixed_widths[0], fixed_widths[1]]
    for subject in subjects:
        col_widths.extend([subject_width, subject_width])
    col_widths.extend(fixed_widths[2:])
    total_width = sum(col_widths)
    if total_width > usable_width:
        scale = usable_width / total_width
        col_widths = [width * scale for width in col_widths]

    rows = [[p('Pos', header_style), p('Student', header_style)]]
    for subject in subjects:
        rows[0].extend([
            p(f'{subject.code} Score', header_style),
            p(f'{subject.code} Pos', header_style),
        ])
    rows[0].extend([
        p('Total', header_style),
        p('Avg', header_style),
        p('Class Pos', header_style),
        p('Teacher Comment', header_style),
        p('Admin Comment', header_style),
    ])

    for data in context['broadsheet_data']:
        row = [
            p(data['class_position']),
            p(f"{data['student'].user.get_full_name()}\n{data['student'].student_id}"),
        ]
        for subject in subjects:
            result = data['results'].get(subject.code) or {}
            row.extend([
                p(f"{result.get('total', '') if result else ''} {result.get('grade', '') if result else ''}".strip()),
                p(data['subject_positions'].get(subject.code, '')),
            ])
        row.extend([
            p(data['total_score']),
            p(f"{data['average']}%"),
            p(f"{data['class_position']}/{context['total_students']}"),
            p(data['teacher_comment']),
            p(data['ht_comment']),
        ])
        rows.append(row)

    best_row = [p('', header_style), p('Best Per Subject', header_style)]
    for subject in subjects:
        best = context['best_per_subject'].get(subject.code)
        best_row.extend([
            p(f"{best['score']:.0f}\n{best['student']}" if best else '-'),
            p(''),
        ])
    best_row.extend([p(''), p(''), p(''), p(''), p('')])
    rows.append(best_row)

    avg_row = [p('', header_style), p('Class Average', header_style)]
    for subject in subjects:
        avg = context['subject_averages'].get(subject.code, 0)
        avg_row.extend([p(f'{avg:.1f}%'), p('')])
    avg_row.extend([
        p(f"{context['grand_total']:.0f}"),
        p(f"{context['grand_average']:.1f}%"),
        p(''),
        p(''),
        p(''),
    ])
    rows.append(avg_row)

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .35, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor('#f3f4f6')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    school_settings = SchoolSettings.get_for_school(getattr(request, 'school', None))
    elements = [
        Paragraph(escape(getattr(school_settings, 'school_name', '') or getattr(request.school, 'name', 'School')), title_style),
        Paragraph(
            escape(f"Broadsheet Report | {term.session if term else ''} {term.name if term else ''} | Class: {school_class}"),
            meta_style,
        ),
        Spacer(1, 3),
        table,
    ]

    def add_page_number(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont('Helvetica', 6)
        canvas.drawRightString(page_size[0] - doc_obj.rightMargin, 5 * mm, f'Page {doc_obj.page}')
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)

    return response


@login_required
def manage_attendance(request):
    """Allow class teachers to record attendance and result comments for their students."""
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')

    teacher = Teacher.objects.get(user=request.user)
    class_teacher = _get_class_teacher_assignment(teacher, request.GET.get('class_id') or request.POST.get('class_id'))
    if not class_teacher:
        return redirect('core:dashboard')
    class_teacher_assignments = _get_class_teacher_assignments(teacher)

    terms = Term.objects.all().order_by('-session', '-start_date', 'name')
    requested_term_id = request.POST.get('term_id') or request.GET.get('term_id')
    requested_session = request.POST.get('academic_session') or request.GET.get('academic_session')
    term = None

    if requested_term_id:
        try:
            term = terms.filter(id=int(requested_term_id)).first()
        except (TypeError, ValueError):
            term = None

    if term and requested_session and term.session != requested_session:
        term = None

    if not term and requested_session:
        term = (
            terms.filter(session=requested_session, is_active=True).first()
            or terms.filter(session=requested_session).first()
        )

    if not term:
        term = terms.filter(is_active=True).first() or terms.first()

    if not term:
        messages.error(request, 'No term is set. Please contact the administrator.')
        return redirect('core:dashboard')

    students = students_for_term(
        teacher.school,
        class_teacher.school_class,
        term,
    ).select_related('user').order_by('user__first_name', 'user__last_name', 'student_id')
    results_locked = _teacher_result_adjustments_locked(request.user, term)

    if request.method == 'POST':
        if results_locked:
            messages.error(request, 'Results for this term have been published. Ask the school admin to withdraw them before making adjustments.')
            return redirect(f"{reverse('core:manage_attendance')}?class_id={class_teacher.school_class_id}&term_id={term.id}&academic_session={term.session}")

        attendance_updates = {}
        attendance_errors = []
        for student in students:
            total_days_str = request.POST.get(f'attendance_{student.id}_total_days', '').strip()
            present_days_str = request.POST.get(f'attendance_{student.id}_days_present', '').strip()
            if total_days_str or present_days_str:
                try:
                    total_days = int(total_days_str or 0)
                    days_present = int(present_days_str or 0)
                except ValueError:
                    attendance_errors.append(
                        f'{student.user.get_full_name() or student.student_id}: use whole numbers for attendance.'
                    )
                    continue

                if total_days < 0 or days_present < 0 or days_present > total_days:
                    attendance_errors.append(
                        f'{student.user.get_full_name() or student.student_id}: days present must be between 0 and total school days.'
                    )
                    continue
                attendance_updates[student.id] = {
                    'total_days': total_days,
                    'days_present': days_present,
                    'days_absent': total_days - days_present,
                }

        if attendance_errors:
            for error in attendance_errors[:5]:
                messages.error(request, error)
            if len(attendance_errors) > 5:
                messages.error(request, f'{len(attendance_errors) - 5} more attendance rows need correction.')
            return redirect(f"{reverse('core:manage_attendance')}?class_id={class_teacher.school_class_id}&term_id={term.id}&academic_session={term.session}")

        with transaction.atomic():
            for student in students:
                if student.id in attendance_updates:
                    Attendance.objects.update_or_create(
                        student=student,
                        term=term,
                        defaults=attendance_updates[student.id],
                    )

                teacher_comment = request.POST.get(f'comment_{student.id}', '').strip()
                if teacher_comment or Comment.objects.filter(student=student, term=term).exists():
                    Comment.objects.update_or_create(
                        student=student,
                        term=term,
                        defaults={'teacher_comment': teacher_comment},
                    )

        messages.success(request, 'Attendance and comments updated successfully.')
        return redirect(f"{reverse('core:manage_attendance')}?class_id={class_teacher.school_class_id}&term_id={term.id}&academic_session={term.session}")

    # Preload existing attendance and comments for display
    attendance_qs = Attendance.objects.filter(student__in=students, term=term)
    comment_qs = Comment.objects.filter(student__in=students, term=term)

    attendance_map = {att.student.id: att for att in attendance_qs}
    comment_map = {com.student.id: com for com in comment_qs}
    academic_sessions = sorted({term_obj.session for term_obj in terms if term_obj.session}, reverse=True)

    return render(request, 'class_teacher/manage_attendance.html', {
        'teacher': teacher,
        'class_teacher': class_teacher,
        'class_teacher_assignments': class_teacher_assignments,
        'students': students,
        'term': term,
        'terms': terms,
        'academic_sessions': academic_sessions,
        'selected_academic_session': term.session,
        'attendance_map': attendance_map,
        'comment_map': comment_map,
        'results_locked': results_locked,
    })

@login_required
def results_overview(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    classes, subjects = _get_teacher_assessment_scope(teacher)
    return render(request, 'teacher/results_overview.html', {
        'classes': classes,
        'subjects': subjects,
    })

@login_required
@feature_required('reports_results')
def component_results(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    classes, subjects = _get_teacher_assessment_scope(teacher)
    terms = Term.objects.all().order_by('-start_date')
    active_term = terms.filter(is_active=True).first()
    selected_term = terms.filter(pk=request.GET.get('term_id')).first() if str(request.GET.get('term_id', '')).isdigit() else None
    selected_term = selected_term or active_term or terms.first()
    return render(request, 'teacher/component_results.html', {
        'classes': classes,
        'subjects': subjects,
        'terms': terms,
        'active_term': active_term,
        'selected_term': selected_term,
    })

@login_required
def get_components(request):
    if not _request_user_has_result_access(request):
        return JsonResponse({'components': [], 'error': 'Result access disabled'}, status=403)

    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if class_id and subject_id:
        if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
            return JsonResponse({'components': []}, status=403)

        teacher = Teacher.objects.filter(user=request.user).first()
        if not teacher or not _teacher_can_manage_component_results(request.user, teacher, class_id, subject_id):
            return JsonResponse({'components': []}, status=403)

        components = ResultComponent.objects.filter(
            school_class_id=class_id,
            subject_id=subject_id
        ).values('id', 'component_name', 'weight', 'max_score')
        
        return JsonResponse({'components': list(components)})
    
    return JsonResponse({'components': []})

@login_required
def get_student_results(request):
    if not _request_user_has_result_access(request):
        return JsonResponse({'students': [], 'error': 'Result access disabled'}, status=403)

    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    term_id = request.GET.get('term_id')
    
    if class_id and subject_id and term_id:
        if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
            return JsonResponse({'students': []}, status=403)

        teacher = Teacher.objects.filter(user=request.user).first()
        if not teacher or not _teacher_can_manage_component_results(request.user, teacher, class_id, subject_id):
            return JsonResponse({'students': []}, status=403)

        term = Term.objects.filter(id=term_id).first()
        school_class = SchoolClass.objects.filter(id=class_id).first()
        if not term or not school_class:
            return JsonResponse({'students': [], 'error': 'Select a valid class and term'}, status=400)
        results_locked = _teacher_result_adjustments_locked(request.user, term)
        students = list(students_for_term(teacher.school, school_class, term).select_related('user').order_by(
            'user__first_name', 'user__last_name', 'student_id',
        ))
        student_ids = [student.id for student in students]
        component_ids = list(ResultComponent.objects.filter(
            school_class=school_class, subject_id=subject_id,
        ).order_by('id').values_list('id', flat=True))
        marks = {
            (mark.student_id, mark.component_id): float(mark.score)
            for mark in ComponentResult.objects.filter(
                student_id__in=student_ids, component_id__in=component_ids, term=term,
            )
        }
        results = {
            result.student_id: result for result in Result.objects.filter(
                student_id__in=student_ids, subject_id=subject_id, term=term,
            )
        }
        student_data = []
        for student in students:
            result = results.get(student.id)
            student_data.append({
                'id': student.id,
                'name': student.user.get_full_name() or student.user.username,
                'student_id': student.student_id,
                'component_scores': {component_id: marks.get((student.id, component_id)) for component_id in component_ids},
                'total_score': float(result.total_score) if result else None,
                'grade': result.grade if result else None,
            })

        return JsonResponse({
            'students': student_data,
            'results_locked': results_locked,
            'lock_message': 'Results for this term have been published. Ask the school admin to withdraw them before making adjustments.' if results_locked else '',
        })
    
    return JsonResponse({'students': []})

@login_required
def update_component_score(request):
    if not _request_user_has_result_access(request):
        return JsonResponse({'success': False, 'message': 'Result access disabled'}, status=403)

    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
        
        student_id = data.get('student_id')
        component_id = data.get('component_id')
        term_id = data.get('term_id')
        score = data.get('score')

        try:
            with transaction.atomic():
                student = Student.objects.select_for_update().get(id=student_id)
                component = ResultComponent.objects.get(id=component_id)
                term = Term.objects.get(id=term_id)

                if _teacher_result_adjustments_locked(request.user, term):
                    return JsonResponse({
                        'success': False,
                        'message': 'Results for this term have been published. Ask the school admin to withdraw them before making adjustments.'
                    })

                # Verify teacher can manage this
                teacher = Teacher.objects.get(user=request.user)
                if not _teacher_can_manage_component_instance(request.user, teacher, student, component, term):
                    return JsonResponse({'success': False, 'message': 'Unauthorized'})

                score = Decimal(str(score))
                if not score.is_finite() or score < 0 or score > component.max_score or component.max_score <= 0:
                    return JsonResponse({'success': False, 'message': 'Score must be between zero and the assessment maximum.'}, status=400)
                if score != score.quantize(Decimal('0.01')):
                    return JsonResponse({'success': False, 'message': 'Use at most two decimal places for a score.'}, status=400)
                with transaction.atomic():
                    capture_term_placement(student, term, component.school_class)
                    ComponentResult.objects.update_or_create(
                        student=student, component=component, term=term, defaults={'score': score},
                    )
                    result, created = Result.objects.get_or_create(
                        student=student, subject=component.subject, term=term,
                    )
                    result.calculate_total()

                return JsonResponse({
                    'success': True,
                    'total_score': float(result.total_score),
                    'grade': result.grade
                })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def class_community(request):
    school = getattr(request, 'school', None)
    if not school or not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'Class community is available to school admins and class teachers.')
        return redirect('core:dashboard')

    is_admin = request.user.has_role('super_admin')
    if is_admin:
        classes = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')
    else:
        classes = SchoolClass.all_objects.filter(
            school=school,
            class_teacher_assignments__teacher__user=request.user,
        ).distinct().order_by('name', 'stream')

    selected_class = classes.filter(id=request.GET.get('class_id')).first() if request.GET.get('class_id') else classes.first()
    students = active_students(school).filter(
        school_class=selected_class,
    ).select_related('user', 'school_class').order_by('user__first_name', 'user__last_name', 'student_id') if selected_class else Student.objects.none()

    search = request.GET.get('search', '').strip()
    if search:
        students = students.filter(
            Q(student_id__icontains=search) | Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search)
        )

    memberships = {
        membership.user_id: membership
        for membership in SchoolMembership.objects.filter(school=school, user_id__in=students.values('user_id'))
    }
    student_rows = [{'student': student, 'membership': memberships.get(student.user_id)} for student in students]
    population = active_students(school).filter(school_class=selected_class) if selected_class else Student.objects.none()

    return render(request, 'class_teacher/class_community.html', {
        'classes': classes,
        'selected_class': selected_class,
        'student_rows': student_rows,
        'search': search,
        'is_admin': is_admin,
        'total_population': population.count(),
        'male_population': population.filter(gender='M').count(),
        'female_population': population.filter(gender='F').count(),
    })


@login_required
def student_promotion(request):
    school = getattr(request, 'school', None)
    is_admin = request.user.has_role('super_admin')
    if is_admin:
        class_options = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')
        selected_class = class_options.filter(id=request.GET.get('class_id')).first() if request.GET.get('class_id') else class_options.first()
        class_teacher_assignments = ClassTeacher.objects.none()
        class_teacher = None
    else:
        teacher = Teacher.objects.filter(user=request.user, school=school).first()
        class_teacher = _get_class_teacher_assignment(teacher, request.GET.get('class_id')) if teacher else None
        class_teacher_assignments = _get_class_teacher_assignments(teacher) if teacher else ClassTeacher.objects.none()
        class_options = SchoolClass.all_objects.filter(
            id__in=class_teacher_assignments.values_list('school_class_id', flat=True)
        ).order_by('name', 'stream')
        selected_class = class_teacher.school_class if class_teacher else None
    if not selected_class:
        messages.error(request, 'Create or assign a class before opening student promotion.')
        return redirect('core:dashboard')
    
    students = active_students(school).filter(school_class=selected_class)
    
    # Calculate promotion eligibility
    students_data = []
    eligible_count = 0
    not_eligible_count = 0
    promoted_count = 0
    
    active_term = Term.objects.filter(is_active=True).first()
    
    promotion_settings = SchoolSettings.get_for_school(school)
    min_average = float(getattr(promotion_settings, 'promotion_min_average', 50))
    max_failures = int(getattr(promotion_settings, 'promotion_max_failed_subjects', 2))
    min_attendance = float(getattr(promotion_settings, 'promotion_min_attendance', 75))
    for student in students:
        # Calculate average and failures
        results = Result.objects.filter(student=student, term=active_term)
        
        if results.exists():
            total_score = sum(float(r.total_score) for r in results)
            average = total_score / results.count()
            failures = results.filter(total_score__lt=min_average).count()
        else:
            average = 0
            failures = 0
        
        attendance_record = Attendance.objects.filter(student=student, term=active_term).first()
        attendance = attendance_record.percentage() if attendance_record else 0
        
        # Check eligibility
        eligible = (average >= min_average and failures <= max_failures and attendance >= min_attendance)
        
        if student.is_promoted:
            promoted_count += 1
        elif eligible:
            eligible_count += 1
        else:
            not_eligible_count += 1
        
        students_data.append({
            'student': student,
            'average': average,
            'failures': failures,
            'attendance': attendance,
            'eligible': eligible
        })
    
    # Get available classes for promotion
    available_classes = SchoolClass.all_objects.filter(school=school).exclude(id=selected_class.id)
    
    return render(request, 'class_teacher/student_promotion.html', {
        'class_teacher': class_teacher,
        'class_teacher_assignments': class_teacher_assignments,
        'class_options': class_options,
        'selected_class': selected_class,
        'students_data': students_data,
        'available_classes': available_classes,
        'eligible_count': eligible_count,
        'not_eligible_count': not_eligible_count,
        'promoted_count': promoted_count,
        'total_students': students.count()
        ,'promotion_settings': promotion_settings
        ,'is_admin': is_admin
    })

@login_required
def promote_students(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Invalid promotion request.'}, status=400)
        
        student_ids = data.get('student_ids', [])
        target_class_id = data.get('target_class_id')
        force_promote = data.get('force_promote', False)
        
        try:
            school = getattr(request, 'school', None)
            if not school or not request.user.has_any_role(['super_admin', 'class_teacher']):
                return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
            if not student_ids or not target_class_id:
                return JsonResponse({'success': False, 'message': 'Select students and a target class.'}, status=400)

            target_class = SchoolClass.all_objects.get(id=target_class_id, school=school)
            with transaction.atomic():
                students = list(Student.all_objects.select_for_update().filter(
                    id__in=student_ids,
                    school=school,
                    status='active',
                ))
                if len(students) != len(set(str(student_id) for student_id in student_ids)):
                    return JsonResponse({'success': False, 'message': 'One or more selected students could not be found.'}, status=400)
                if not request.user.has_role('super_admin'):
                    allowed_class_ids = set(_class_teacher_assignments_for_user(
                        request.user, school
                    ).values_list('school_class_id', flat=True))
                    if any(student.school_class_id not in allowed_class_ids for student in students):
                        return JsonResponse({'success': False, 'message': 'You can only promote students in your assigned classes.'}, status=403)
                if any(student.school_class_id == target_class.id for student in students):
                    return JsonResponse({'success': False, 'message': 'A student is already in the selected target class.'}, status=400)

                for student in students:
                    capture_before_promotion(student)
                    student.promoted_from_id = student.school_class_id
                    student.school_class = target_class
                    student.promoted_to = target_class
                    student.is_promoted = True
                    student.save(update_fields=['promoted_from', 'school_class', 'promoted_to', 'is_promoted'])
            
            return JsonResponse({
                'success': True, 
                'message': f'{len(students)} students promoted successfully'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False})

@login_required
@feature_required('reports_analytics')
def view_analytics(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    teacher = Teacher.objects.get(user=request.user)
    classes, subjects = _get_teacher_assessment_scope(teacher)
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if class_id and subject_id:
        if not _teacher_can_manage_component_results(request.user, teacher, class_id, subject_id):
            return redirect('core:dashboard')
        school_class = get_object_or_404(SchoolClass.all_objects, pk=class_id, school=teacher.school)
        results = results_for_class(teacher.school, school_class).filter(subject_id=subject_id)
        
        total_students = results.values('student').distinct().count()
        avg_score = results.aggregate(Avg('total_score'))['total_score__avg'] or 0
        pass_count = results.filter(total_score__gte=50).count()
        fail_count = results.filter(total_score__lt=50).count()
        
        grade_distribution = []
        for grade in ['A+', 'A', 'B', 'C', 'D', 'F']:
            count = results.filter(grade=grade).count()
            percentage = (count * 100 / total_students) if total_students > 0 else 0
            grade_distribution.append({'grade': grade, 'count': count, 'percentage': percentage})
        
        context = {
            'school_class': SchoolClass.objects.get(id=class_id),
            'subject': Subject.objects.get(id=subject_id),
            'total_students': total_students,
            'avg_score': avg_score,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'grade_distribution': grade_distribution,
            'has_data': True,
        }
    else:
        context = {
            'classes': classes,
            'subjects': subjects,
        }
    
    return render(request, 'teacher/analytics.html', context)

@login_required
def export_results(request):
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    import csv
    from django.http import HttpResponse
    
    class_id = request.GET.get('class_id')
    subject_id = request.GET.get('subject_id')
    
    if not class_id or not subject_id:
        messages.error(request, 'Please select class and subject')
        return redirect('core:results_overview')
    
    school_class = SchoolClass.objects.get(id=class_id)
    subject = Subject.objects.get(id=subject_id)
    teacher = Teacher.objects.get(user=request.user)
    if not _teacher_can_manage_component_results(request.user, teacher, class_id, subject_id):
        messages.error(request, 'You do not have permission to export results for that class and subject.')
        return redirect('core:results_overview')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{school_class.name}_{subject.code}_results.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Total Score', 'Grade', 'Grade Point', 'Remark'])
    
    results = results_for_class(
        teacher.school, school_class,
    ).filter(subject=subject).select_related('student__user')
    
    for result in results:
        writer.writerow([
            result.student.student_id,
            result.student.user.get_full_name(),
            result.total_score,
            result.grade,
            result.grade_point,
            result.remark
        ])
    
    return response

def view_quiz_result(request, quiz_id):
    from .views_quiz import view_quiz_result as handler
    return handler(request, quiz_id)

@login_required
def generate_tokens(request):
    if not request.user.has_role('super_admin'):
        return redirect('core:dashboard')

    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Open a school tenant before generating result tokens.')
        return redirect('core:dashboard')
    
    terms = _tenant_terms_queryset(school)
    classes = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')

    if request.method == 'POST':
        action = request.POST.get('action', 'create')

        if action in ['send_token_details', 'send_visible_tokens']:
            channels = delivery_channels_from_post(request.POST, default=['email'])
            token_queryset = ResultToken.all_objects.filter(
                student__school=school,
                term__school=school,
            ).select_related('student__user', 'student__school_class', 'term')

            filter_class_id = request.POST.get('filter_school_class', '')
            filter_term_id = request.POST.get('filter_term', '')
            filter_query = (request.POST.get('filter_q') or '').strip()

            if action == 'send_token_details':
                token_queryset = token_queryset.filter(id=request.POST.get('token_id'))
            else:
                if filter_class_id:
                    token_queryset = token_queryset.filter(student__school_class_id=filter_class_id)
                if filter_term_id:
                    token_queryset = token_queryset.filter(term_id=filter_term_id)
                if filter_query:
                    token_queryset = token_queryset.filter(
                        Q(token__icontains=filter_query) |
                        Q(student__student_id__icontains=filter_query) |
                        Q(student__user__first_name__icontains=filter_query) |
                        Q(student__user__last_name__icontains=filter_query) |
                        Q(student__user__username__icontains=filter_query)
                    )

            delivery_service = TenantPortalDeliveryService(school, sender=request.user, request=request)
            summary = DeliverySummary()
            processed = 0
            for result_token in token_queryset:
                if not student_has_result_access(result_token.student):
                    summary.add(skipped=1, error=f'{result_token.student.student_id} result access is disabled.')
                    continue
                summary.merge(delivery_service.send_result_token_details(result_token, channels))
                processed += 1

            if not processed and not summary.skipped:
                messages.warning(request, 'No result tokens matched the selected send action.')
            else:
                message_text = f'Token delivery processed for {processed} token(s): {summary.as_message()}.'
                if summary.failed:
                    messages.warning(request, message_text)
                else:
                    messages.success(request, message_text)

            query_params = {
                'school_class': filter_class_id,
                'term': filter_term_id,
                'q': filter_query,
            }
            query_string = urlencode({key: value for key, value in query_params.items() if value})
            redirect_url = reverse('core:generate_tokens')
            if query_string:
                redirect_url = f'{redirect_url}?{query_string}'
            return redirect(redirect_url)

        term_id = request.POST.get('term_id')
        try:
            max_uses = max(1, int(request.POST.get('max_uses', 3)))
        except (TypeError, ValueError):
            max_uses = 3
        individual = request.POST.get('individual')
        
        term = get_object_or_404(Term.all_objects, id=term_id, school=school)
        
        if individual:
            student_id = request.POST.get('student_id')
            student = get_object_or_404(Student.all_objects, id=student_id, school=school)
            if action == 'regenerate':
                ResultToken.all_objects.filter(student=student, term=term).delete()
                ResultToken.all_objects.create(student=student, term=term, max_uses=max_uses)
                messages.success(request, f'New token regenerated for {student.user.get_full_name()}')
            else:
                _, created = ResultToken.all_objects.get_or_create(
                    student=student,
                    term=term,
                    defaults={'max_uses': max_uses}
                )
                if created:
                    messages.success(request, f'Token generated for {student.user.get_full_name()}')
                else:
                    messages.warning(request, f'Token already exists for {student.user.get_full_name()} - use Regenerate to create new token')
        else:
            selected_class_id = request.POST.get('school_class') or ''
            selected_class = None
            students = Student.all_objects.filter(school=school).select_related('user', 'school_class')
            if selected_class_id:
                selected_class = classes.filter(pk=selected_class_id).first()
                if not selected_class:
                    messages.error(request, 'Choose a valid class before generating tokens.')
                    return redirect('core:generate_tokens')
                students = students.filter(school_class=selected_class)
            student_count = students.count()
            class_label = f' in {selected_class}' if selected_class else ''
            
            if action == 'regenerate':
                if selected_class:
                    ResultToken.all_objects.filter(
                        term=term,
                        student__school=school,
                        student__school_class=selected_class,
                    ).delete()
                else:
                    ResultToken.all_objects.filter(term=term, student__school=school).delete()
                for student in students:
                    ResultToken.all_objects.create(student=student, term=term, max_uses=max_uses)
                messages.success(request, f'Tokens regenerated for {student_count} students{class_label}')
            else:
                created_count = 0
                for student in students:
                    _, created = ResultToken.all_objects.get_or_create(
                        student=student,
                        term=term,
                        defaults={'max_uses': max_uses}
                    )
                    if created:
                        created_count += 1
                messages.success(request, f'Tokens generated{class_label}: {created_count} new, {student_count - created_count} already existed')
        
        return redirect('core:generate_tokens')
    
    selected_class_id = request.GET.get('school_class', '')
    selected_term_id = request.GET.get('term', '')
    search_query = (request.GET.get('q') or '').strip()
    students = Student.all_objects.filter(school=school).select_related('user', 'school_class').order_by('student_id')
    tokens = ResultToken.all_objects.filter(
        student__school=school,
        term__school=school,
    ).select_related('student__user', 'student__school_class', 'term').order_by('-created_at')
    if selected_class_id:
        tokens = tokens.filter(student__school_class_id=selected_class_id)
    if selected_term_id:
        tokens = tokens.filter(term_id=selected_term_id)
    if search_query:
        tokens = tokens.filter(
            Q(token__icontains=search_query) |
            Q(student__student_id__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(student__user__username__icontains=search_query)
        )
    check_result_url = request.build_absolute_uri(reverse('core:check_result'))
    tokens = list(tokens)
    for result_token in tokens:
        student_name = result_token.student.user.get_full_name() or result_token.student.user.username
        result_token.copy_text = (
            f"Student: {student_name}\n"
            f"Student ID: {result_token.student.student_id}\n"
            f"Class: {result_token.student.school_class}\n"
            f"Term: {result_token.term.session} - {result_token.term.name}\n"
            f"Result Token: {result_token.token}\n"
            f"Result Portal: {check_result_url}\n"
            "Use the token above on the result portal to view the result."
        )
    return render(request, 'admin/generate_tokens.html', {
        'terms': terms,
        'classes': classes,
        'students': students,
        'tokens': tokens,
        'selected_class_id': selected_class_id,
        'selected_term_id': selected_term_id,
        'search_query': search_query,
        'check_result_url': check_result_url,
    })

def check_result(request):
    if request.method == 'POST':
        token = request.POST.get('token', '').strip().upper()
        
        try:
            result_token = ResultToken.objects.select_related(
                'student__user',
                'student__school',
                'term',
            ).get(token=token)

            if not result_token.term.result_published:
                messages.error(request, 'This result has not been published by the school yet.')
                return redirect('core:check_result')

            if not student_has_result_access(result_token.student):
                messages.error(request, 'Result access for this student is currently disabled. Please contact the school administrator.')
                return redirect('core:check_result')
            
            if not result_token.can_use():
                messages.error(request, 'Token usage limit exceeded')
                return redirect('core:check_result')
            
            result_token.use_token()
            return redirect('core:view_result_card', token=token)
            
        except ResultToken.DoesNotExist:
            messages.error(request, 'Invalid token')
    
    return render(request, 'check_result.html')


REPORT_CARD_TEMPLATE_FILES = {
    ReportCardSettings.TEMPLATE_CLASSIC: 'result_card.html',
    ReportCardSettings.TEMPLATE_THEME_BACKGROUND: 'result_card.html',
    ReportCardSettings.TEMPLATE_NURSERY_PLAYFUL: 'result_cards/nursery_playful.html',
    ReportCardSettings.TEMPLATE_NURSERY_CLEAN: 'result_cards/nursery_clean.html',
}


def _report_settings_queryset():
    return ReportCardSettings.all_objects if hasattr(ReportCardSettings, 'all_objects') else ReportCardSettings.objects


def _get_report_card_settings(school):
    queryset = _report_settings_queryset()
    settings = queryset.filter(school=school, is_active=True).first()
    if settings:
        return settings
    settings = queryset.filter(school=school).first()
    if settings:
        return settings
    return ReportCardSettings(school=school)


def _report_card_template_name(report_settings, school_class):
    selected_template = report_settings.template_for_class(school_class)
    return REPORT_CARD_TEMPLATE_FILES.get(selected_template, 'result_card.html'), selected_template


@lru_cache(maxsize=1)
def _learner_domain_criterion_supports_class_scope():
    try:
        field = LearnerDomainCriterion._meta.get_field('classes')
    except FieldDoesNotExist:
        return False

    if not getattr(field, 'many_to_many', False):
        return False

    try:
        through_table = field.remote_field.through._meta.db_table
        return through_table in connection.introspection.table_names()
    except Exception:
        return False


def _learner_domain_criteria_for_class(school, school_class):
    criteria = LearnerDomainCriterion.all_objects.filter(
        school=school,
        is_active=True,
    )
    if school_class and _learner_domain_criterion_supports_class_scope():
        criteria = criteria.filter(
            Q(classes__isnull=True) |
            Q(classes=school_class)
        ).distinct()
    return criteria.order_by('domain_type', 'display_order', 'name')


def _learner_domain_rating_rows(student, term, effective_domain=None, psychomotor=None, school_class=None):
    LearnerDomainCriterion.ensure_defaults(student.school)
    criteria = list(_learner_domain_criteria_for_class(student.school, school_class or student.school_class))
    ratings = {
        rating.criterion_id: rating.value
        for rating in LearnerDomainRating.all_objects.filter(
            student=student,
            term=term,
            criterion__in=criteria,
        )
    }

    effective_rows = []
    psychomotor_rows = []
    for criterion in criteria:
        value = ratings.get(criterion.id, '')
        if not value and criterion.legacy_field:
            if criterion.domain_type == LearnerDomainCriterion.DOMAIN_EFFECTIVE and effective_domain:
                value = getattr(effective_domain, criterion.legacy_field, '')
            elif criterion.domain_type == LearnerDomainCriterion.DOMAIN_PSYCHOMOTOR and psychomotor:
                value = getattr(psychomotor, criterion.legacy_field, '')

        row = {'name': criterion.name, 'value': value}
        if criterion.domain_type == LearnerDomainCriterion.DOMAIN_EFFECTIVE:
            effective_rows.append(row)
        else:
            psychomotor_rows.append(row)

    return effective_rows, psychomotor_rows


def _domain_rating_values(*rating_groups):
    values = []
    seen = set()
    for rating_group in rating_groups:
        for row in rating_group:
            value = str(row.get('value') or '').strip()
            if not value:
                continue
            normalized = value.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            values.append(value)
    return values


def _domain_rating_guide(report_settings, school_class=None):
    if hasattr(report_settings, 'active_domain_rating_guide'):
        return report_settings.active_domain_rating_guide(school_class)
    return []


def _report_term_number(term):
    if '1st' in term.name or 'First' in term.name:
        return 1
    if '2nd' in term.name or 'Second' in term.name:
        return 2
    if '3rd' in term.name or 'Third' in term.name:
        return 3
    return None


def _build_report_card_data(student, term, request=None, can_print_download=False, is_admin_view=False, result_token=None):
    report_settings = _get_report_card_settings(student.school)
    report_class = report_class_for_term(student, term)
    placement = placement_for_term(student, term)
    results = Result.objects.filter(
        student=student,
        term=term,
        subject__school=student.school,
    ).select_related('subject')

    component_breakdown, result_warnings, total_obtainable = report_component_rows(student, term, results)
    if report_class is None:
        result_warnings.append('The class for this historical term could not be established. Please ask the school administrator to review it.')
    components_by_subject = {row['subject'].id: row['components'] for row in component_breakdown}

    term_number = _report_term_number(term)
    cumulative_results = []
    if term_number == 3 and report_settings.third_term_mode == 'cumulative':
        session_terms = Term.all_objects.filter(
            school=student.school,
            session=term.session,
        ).order_by('start_date')

        for result in results:
            subject_cumulative = {
                'subject': result.subject,
                'first_term': None,
                'second_term': None,
                'third_term': None,
                'components': [],
                'cumulative_total': 0,
                'cumulative_average': 0,
                'grade': '',
                'remark': '',
                'terms_count': 0,
            }

            for session_term in session_terms:
                try:
                    term_result = Result.objects.get(
                        student=student,
                        subject=result.subject,
                        term=session_term,
                    )
                except Result.DoesNotExist:
                    continue

                score = float(term_result.total_score)
                subject_cumulative['cumulative_total'] += score
                subject_cumulative['terms_count'] += 1
                if _report_term_number(session_term) == 1:
                    subject_cumulative['first_term'] = score
                elif _report_term_number(session_term) == 2:
                    subject_cumulative['second_term'] = score
                elif _report_term_number(session_term) == 3:
                    subject_cumulative['third_term'] = score
                    subject_cumulative['components'] = components_by_subject[result.subject_id]

            if subject_cumulative['terms_count'] > 0:
                subject_cumulative['cumulative_average'] = (
                    subject_cumulative['cumulative_total'] / subject_cumulative['terms_count']
                )
                cumulative_grade = GradingSystem.all_objects.filter(
                    school=student.school,
                    min_score__lte=subject_cumulative['cumulative_average'],
                    max_score__gte=subject_cumulative['cumulative_average'],
                ).first()
                if cumulative_grade:
                    subject_cumulative['grade'] = cumulative_grade.grade
                    subject_cumulative['remark'] = cumulative_grade.remark

            cumulative_results.append(subject_cumulative)

    total_score = sum(float(r.total_score) for r in results)
    total_subjects = results.count()
    average = total_score / total_subjects if total_subjects > 0 else 0
    grading = GradingSystem.all_objects.filter(
        school=student.school,
        min_score__lte=average,
        max_score__gte=average,
    ).first()
    overall_grade = grading.grade if grading else None
    overall_remark = grading.remark if grading else ''

    classmates = students_for_term(student.school, report_class, term)
    class_results = Result.objects.filter(
        student__school=student.school,
        student__in=classmates,
        subject__school=student.school,
        term=term,
    ).values('student').annotate(avg=Avg('total_score')).order_by('-avg')
    position = 1
    class_highest = 0
    class_lowest = 0
    class_average = 0
    if class_results:
        for idx, class_result in enumerate(class_results, 1):
            if class_result['student'] == student.id:
                position = idx
                break
        avg_values = [float(class_result['avg']) for class_result in class_results]
        class_highest = max(avg_values)
        class_lowest = min(avg_values)
        class_average = sum(avg_values) / len(avg_values)

    attendance = Attendance.objects.filter(student=student, term=term).first()
    comment = Comment.objects.filter(student=student, term=term).first()
    psychomotor = Psychomotor.objects.filter(student=student, term=term).first()
    effective_domain = EffectiveDomain.objects.filter(student=student, term=term).first()
    effective_domain_ratings, psychomotor_ratings = _learner_domain_rating_rows(
        student,
        term,
        effective_domain=effective_domain,
        psychomotor=psychomotor,
        school_class=report_class,
    )
    school_settings = SchoolSettings.get_for_school(student.school)
    total_students = classmates.count()
    class_teacher = ClassTeacher.objects.select_related('teacher__user').filter(
        school_class=report_class,
        teacher__school=student.school,
        teacher__status='active',
    ).order_by('id').first()
    head_teacher = HeadTeacher.objects.select_related('teacher__user').filter(
        teacher__school=student.school,
        teacher__status='active',
        classes=report_class,
    ).first()

    vacation_date = term.vacation_date
    next_resumption = term.resumption_date

    available_result_tokens = ResultToken.all_objects.none()
    if result_token:
        available_result_tokens = ResultToken.all_objects.filter(
            student=student,
            term__result_published=True,
            term__school=student.school,
        ).select_related('term').order_by('-term__start_date', 'term__session', 'term__name')

    report_template = report_settings.template_for_class(report_class)
    frozen_signatory = placement is not None and placement.signatory_frozen
    if frozen_signatory and not placement.teacher_name:
        result_warnings.append('The original class teacher needs confirmation by the school administrator.')
    class_teacher_name = placement.teacher_name if frozen_signatory else (class_teacher.teacher.user.get_full_name() if class_teacher else '')
    class_teacher_signature = placement.teacher_signature if frozen_signatory else (class_teacher.teacher.signature if class_teacher else None)
    return {
        'student': student,
        'report_class': report_class,
        'class_teacher_name': class_teacher_name,
        'class_teacher_signature': class_teacher_signature,
        'term': term,
        'term_number': term_number,
        'results': results,
        'cumulative_results': cumulative_results,
        'component_breakdown': component_breakdown,
        'result_warnings': result_warnings,
        'average': average,
        'total_score': total_score,
        'total_obtainable': total_obtainable,
        'overall_percentage': average,
        'overall_grade': overall_grade,
        'overall_remark': overall_remark,
        'position': position,
        'total_students': total_students,
        'class_highest': class_highest,
        'class_lowest': class_lowest,
        'class_average': class_average,
        'attendance': attendance,
        'comment': comment,
        'psychomotor': psychomotor,
        'effective_domain': effective_domain,
        'effective_domain_ratings': effective_domain_ratings,
        'psychomotor_ratings': psychomotor_ratings,
        'domain_rating_values': _domain_rating_values(effective_domain_ratings, psychomotor_ratings),
        'domain_rating_guide': _domain_rating_guide(report_settings, report_class),
        'school_settings': school_settings,
        'class_teacher': class_teacher,
        'head_teacher': head_teacher,
        'vacation_date': vacation_date,
        'next_resumption': next_resumption,
        'report_settings': report_settings,
        'report_template': report_template,
        'signatories': report_settings.active_signatories(),
        'is_admin_view': is_admin_view,
        'can_print_download': can_print_download,
        'current_result_token': result_token,
        'available_result_tokens': available_result_tokens,
    }


def view_result_card(request, token):
    result_token = get_object_or_404(
        ResultToken.objects.select_related('student__user', 'student__school', 'student__school_class', 'term'),
        token=token,
    )
    student = result_token.student
    term = result_token.term

    if not term.result_published:
        messages.error(request, 'This result has not been published by the school yet.')
        return redirect('core:check_result')

    if not student_has_result_access(student):
        messages.error(request, 'Result access for this student is currently disabled. Please contact the school administrator.')
        return redirect('core:check_result')
    
    context = _build_report_card_data(
        student, term, request=request, can_print_download=True, result_token=result_token,
    )
    template_name, _ = _report_card_template_name(context['report_settings'], context['report_class'])
    return render(request, template_name, context)

@login_required
def revert_promotion(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        
        student_id = data.get('student_id')
        
        try:
            school = getattr(request, 'school', None)
            if not school or not request.user.has_any_role(['super_admin', 'class_teacher']):
                return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
            student = Student.all_objects.get(id=student_id, school=school)
            if not request.user.has_role('super_admin') and not _class_teacher_assignments_for_user(
                request.user, school
            ).filter(Q(school_class=student.school_class) | Q(school_class=student.promoted_from)).exists():
                return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
            if not student.is_promoted or not student.promoted_from_id:
                return JsonResponse({'success': False, 'message': 'This promotion cannot be reverted.'}, status=400)
            with transaction.atomic():
                student.school_class_id = student.promoted_from_id
                student.is_promoted = False
                student.promoted_from = None
                student.promoted_to = None
                student.save(update_fields=['school_class', 'is_promoted', 'promoted_from', 'promoted_to'])
            
            return JsonResponse({'success': True, 'message': 'Promotion reverted successfully'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False})

@login_required
def save_broadsheet_comments(request):
    if not _request_user_has_result_access(request):
        return JsonResponse({'success': False, 'message': 'Result access disabled'}, status=403)

    if request.method == 'POST':
        import json
        try:
            school = getattr(request, 'school', None)
            if not school:
                return JsonResponse({'success': False, 'message': 'No active school tenant'})

            data = json.loads(request.body)
            comments = data.get('comments', [])
            comment_scope = data.get('comment_scope')
            term = Term.all_objects.filter(school=school, id=data.get('term_id')).first()
            if not term:
                return JsonResponse({'success': False, 'message': 'Select a valid term'})

            class_options, _, _, _ = _broadsheet_class_scope(request)
            school_class = class_options.filter(id=data.get('class_id')).first()
            if not school_class:
                return JsonResponse({'success': False, 'message': 'You cannot save comments for that class'})

            is_admin = _is_school_admin_user(request.user)
            if comment_scope == 'admin':
                if not is_admin:
                    return JsonResponse({'success': False, 'message': 'Only school admins can save admin comments'})
                comment_field = 'proprietor_comment'
                payload_key = 'ht_comment'
            elif comment_scope == 'teacher':
                if is_admin or not request.user.has_role('class_teacher'):
                    return JsonResponse({'success': False, 'message': 'Only class teachers can save class teacher comments'})
                if term.result_published:
                    return JsonResponse({
                        'success': False,
                        'message': 'Results for this term have been published. Ask the school admin to withdraw them before making adjustments.'
                    })
                comment_field = 'teacher_comment'
                payload_key = 'teacher_comment'
            else:
                return JsonResponse({'success': False, 'message': 'Choose which comment section to save'})

            student_ids = [item.get('student_id') for item in comments]
            students = {
                str(student.id): student
                for student in students_for_term(
                    school, school_class, term,
                ).filter(id__in=student_ids)
            }
            
            for comment_data in comments:
                student = students.get(str(comment_data.get('student_id')))
                if not student:
                    return JsonResponse({'success': False, 'message': 'One or more students are outside your allowed class'})
                Comment.all_objects.update_or_create(
                    student=student,
                    term=term,
                    defaults={comment_field: comment_data.get(payload_key, '').strip()}
                )
            
            return JsonResponse({'success': True, 'message': 'Comments saved successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def generate_ai_comment(request):
    if not _request_user_has_result_access(request):
        return JsonResponse({'success': False, 'message': 'Result access disabled'}, status=403)

    if request.method == 'POST':
        import json
        try:
            school = getattr(request, 'school', None)
            if not school:
                return JsonResponse({'success': False, 'message': 'No active school tenant'})
            if not _is_school_admin_user(request.user):
                return JsonResponse({'success': False, 'message': 'Only school admins can generate admin comments'})

            data = json.loads(request.body)
            student_id = data.get('student_id')
            average = float(data.get('average', 0))
            
            class_options, _, _, _ = _broadsheet_class_scope(request)
            student = Student.all_objects.get(
                id=student_id,
                school=school,
                school_class__in=class_options,
            )
            term = Term.all_objects.filter(school=school, id=data.get('term_id')).first()
            if not term:
                return JsonResponse({'success': False, 'message': 'Select a valid term'})
            
            # Get student results for more context
            results = Result.all_objects.filter(
                student=student,
                term=term,
                subject__school=school,
            )
            
            # Count strengths and weaknesses
            strong_subjects = []
            weak_subjects = []
            
            for result in results:
                if float(result.total_score) >= 75:
                    strong_subjects.append(result.subject.name)
                elif float(result.total_score) < 50:
                    weak_subjects.append(result.subject.name)
            
            # Generate contextual comment
            name = student.user.first_name
            comment = f"{name} "
            
            if average >= 80:
                comment += "has demonstrated exceptional academic excellence this term. "
                if strong_subjects:
                    comment += f"Particularly outstanding in {', '.join(strong_subjects[:2])}. "
                comment += "Continue this remarkable performance."
            elif average >= 70:
                comment += "has shown very good academic performance. "
                if strong_subjects:
                    comment += f"Shows strength in {', '.join(strong_subjects[:2])}. "
                if weak_subjects:
                    comment += f"Should focus more on {', '.join(weak_subjects[:2])}. "
                comment += "Keep up the good work."
            elif average >= 60:
                comment += "has made satisfactory progress this term. "
                if weak_subjects:
                    comment += f"Needs improvement in {', '.join(weak_subjects[:2])}. "
                comment += "More consistent effort required."
            elif average >= 50:
                comment += "shows fair performance but needs significant improvement. "
                if weak_subjects:
                    comment += f"Requires extra attention in {', '.join(weak_subjects[:2])}. "
                comment += "Must work harder next term."
            else:
                comment += "requires urgent intervention and support. "
                comment += "Parent-teacher conference recommended. "
                comment += "Extra classes and dedicated study time essential."
            
            return JsonResponse({'success': True, 'comment': comment})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def admin_view_result(request, student_id, term_id):
    if not request.user.has_any_role(['super_admin', 'subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')
    
    student = get_object_or_404(
        Student.all_objects.select_related('user', 'school', 'school_class'),
        id=student_id,
    )
    term = get_object_or_404(Term.all_objects, id=term_id, school=student.school)
    if not request.user.has_role('super_admin') and not student_has_result_access(student):
        messages.error(request, 'Result access for this student is currently disabled.')
        return redirect('core:dashboard')
    if not _user_can_view_student_report(request, student, term):
        messages.error(request, 'You can only view report cards for your assigned class.')
        return redirect('core:dashboard')
    
    context = _build_report_card_data(
        student, term, request=request, is_admin_view=True,
        can_print_download=_user_can_print_or_download_class_records(request, report_class_for_term(student, term)),
    )
    template_name, _ = _report_card_template_name(context['report_settings'], context['report_class'])
    return render(request, template_name, context)


@login_required
@feature_required('reports_results')
def bulk_print_report_cards(request):
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')

    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Open a school tenant before printing report cards.')
        return redirect('core:dashboard')

    class_options, _, _, _ = _broadsheet_class_scope(request)
    class_id = request.GET.get('class_id') or request.POST.get('class_id')
    selected_class = class_options.filter(id=class_id).first() if class_id else class_options.first()
    term_id = request.GET.get('term_id') or request.POST.get('term_id')
    term = Term.all_objects.filter(school=school, id=term_id).first() if term_id else None
    if not term:
        term = Term.all_objects.filter(school=school, is_active=True).order_by('-start_date').first()
    if not term:
        term = Term.all_objects.filter(school=school).order_by('-start_date').first()

    if not selected_class:
        messages.error(request, 'Select a class before printing report cards.')
        return redirect('core:student_results_lookup')
    if not term:
        messages.error(request, 'Create or select a term before printing report cards.')
        return redirect('core:student_results_lookup')
    if not _user_can_print_or_download_class_records(request, selected_class):
        messages.error(request, 'Your account is view-only for this class report card. Ask the school admin to enable print/download access.')
        return redirect('core:student_results_lookup')

    raw_student_ids = []
    for value in request.GET.getlist('student_ids') + request.POST.getlist('student_ids'):
        raw_student_ids.extend(str(value).split(','))
    selected_student_ids = [
        int(student_id)
        for student_id in raw_student_ids
        if str(student_id).strip().isdigit()
    ]

    students = students_for_term(
        school, selected_class, term,
    ).select_related('user', 'school_class').order_by(
        'user__first_name', 'user__last_name', 'student_id',
    )
    if selected_student_ids:
        students = students.filter(id__in=selected_student_ids)
    if not request.user.has_role('super_admin'):
        blocked_student_user_ids = SchoolMembership.objects.filter(
            Q(is_active=False) | Q(portal_access_enabled=False) | Q(result_access_enabled=False),
            school=school,
        ).values_list('user_id', flat=True)
        students = students.exclude(user_id__in=blocked_student_user_ids)

    report_cards = [
        _build_report_card_data(
            student,
            term,
            request=request,
            can_print_download=False,
            is_admin_view=False,
        )
        for student in students
    ]

    return render(request, 'admin/bulk_report_cards.html', {
        'report_cards': report_cards,
        'selected_class': selected_class,
        'term': term,
        'school_settings': SchoolSettings.get_for_school(school),
    })


@login_required
def report_card_settings(request):
    if not request.user.has_role('super_admin'):
        return redirect('core:dashboard')

    school = getattr(request, 'school', None)
    settings = _get_report_card_settings(school)
    if not settings.pk:
        for field_name, value in {
            'show_position': True,
            'show_subject_position': True,
            'show_class_average': True,
            'show_highest_in_class': True,
            'show_attendance': True,
            'show_psychomotor': True,
            'show_effective_domain': True,
            'show_next_resumption': True,
            'show_total_obtainable': True,
            'show_school_opened_days': True,
        }.items():
            setattr(settings, field_name, value)
        settings.school = school
        settings.is_active = True
        settings.save()

    classes = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream') if school else SchoolClass.objects.none()
    template_choices = ReportCardSettings.TEMPLATE_CHOICES
    valid_templates = {key for key, _ in template_choices}
    terms = Term.all_objects.filter(school=school).order_by('-start_date') if school else Term.objects.none()
    selected_teacher_term = None
    teacher_term_id = request.POST.get('teacher_term') if request.method == 'POST' else request.GET.get('teacher_term')
    if teacher_term_id:
        selected_teacher_term = terms.filter(pk=teacher_term_id).first()
    if not selected_teacher_term:
        selected_teacher_term = terms.filter(is_active=True).first() or terms.first()
    
    if request.method == 'POST':
        if request.POST.get('action') == 'save_report_teachers':
            if not selected_teacher_term:
                messages.error(request, 'Select a valid term before changing report card teachers.')
                return redirect('core:report_card_settings')

            updated_students = 0
            updated_classes = 0
            with transaction.atomic():
                for school_class in classes:
                    selected_teacher_id = (request.POST.get(f'report_teacher_{school_class.id}') or '').strip()
                    if not selected_teacher_id:
                        continue

                    if selected_teacher_id == 'automatic':
                        placements = StudentTermPlacement.all_objects.filter(
                            term=selected_teacher_term,
                            school_class=school_class,
                            student__school=school,
                        )
                        updated_students += placements.update(signatory_frozen=False)
                        updated_classes += 1
                        continue

                    teacher = Teacher.all_objects.filter(
                        pk=selected_teacher_id,
                        school=school,
                    ).select_related('user').first()
                    if not teacher:
                        messages.error(request, f'The selected teacher for {school_class} is invalid.')
                        continue

                    class_students = students_for_term(school, school_class, selected_teacher_term)
                    class_update_count = 0
                    for student in class_students.iterator():
                        StudentTermPlacement.all_objects.update_or_create(
                            student=student,
                            term=selected_teacher_term,
                            defaults={
                                'school_class': school_class,
                                'class_teacher': teacher,
                                'teacher_name': teacher.user.get_full_name() or teacher.user.username,
                                'teacher_signature': teacher.signature.name if teacher.signature else '',
                                'signatory_frozen': True,
                            },
                        )
                        class_update_count += 1
                    if class_update_count:
                        updated_classes += 1
                        updated_students += class_update_count

            if updated_students:
                messages.success(
                    request,
                    f'Report card teacher updated for {updated_students} learner(s) in {updated_classes} class(es).',
                )
            elif updated_classes:
                messages.success(request, 'Automatic class-teacher selection restored for the selected report cards.')
            else:
                messages.warning(request, 'No report card teacher changes were selected.')
            query = urlencode({'teacher_term': selected_teacher_term.id})
            return redirect(f"{reverse('core:report_card_settings')}?{query}")

        third_term_mode = request.POST.get('third_term_mode')
        if third_term_mode in dict(ReportCardSettings.THIRD_TERM_MODE_CHOICES):
            settings.third_term_mode = third_term_mode
        settings.show_position = request.POST.get('show_position') == 'on'
        settings.show_subject_position = request.POST.get('show_subject_position') == 'on'
        settings.show_class_average = request.POST.get('show_class_average') == 'on'
        settings.show_highest_in_class = request.POST.get('show_highest_in_class') == 'on'
        settings.show_attendance = request.POST.get('show_attendance') == 'on'
        settings.show_psychomotor = request.POST.get('show_psychomotor') == 'on'
        settings.show_effective_domain = request.POST.get('show_effective_domain') == 'on'
        settings.show_next_resumption = request.POST.get('show_next_resumption') == 'on'
        settings.show_total_obtainable = request.POST.get('show_total_obtainable') == 'on'
        settings.show_school_opened_days = request.POST.get('show_school_opened_days') == 'on'
        selected_template = request.POST.get('template')
        if selected_template in valid_templates:
            settings.template = selected_template

        class_templates = {}
        for school_class in classes:
            selected = request.POST.get(f'class_template_{school_class.id}', '').strip()
            if selected in valid_templates and selected != settings.template:
                class_templates[str(school_class.id)] = selected
        settings.class_templates = class_templates

        signatories = []
        for index in range(1, 4):
            name = (request.POST.get(f'signatory_{index}_name') or '').strip()
            title = (request.POST.get(f'signatory_{index}_title') or '').strip()
            comment = (request.POST.get(f'signatory_{index}_comment') or '').strip()
            if name or title or comment:
                signatories.append({
                    'name': name,
                    'title': title,
                    'comment': comment,
                })
        settings.signatories = signatories[:3]

        domain_rating_guide = []
        for index in range(1, 9):
            label = (request.POST.get(f'domain_rating_{index}_label') or '').strip()
            description = (request.POST.get(f'domain_rating_{index}_description') or '').strip()
            if label or description:
                domain_rating_guide.append({
                    'label': label,
                    'description': description,
                })
        settings.domain_rating_guide = domain_rating_guide[:8]

        class_domain_rating_guides = {}
        for school_class in classes:
            class_guide = []
            for index in range(1, 9):
                label = (request.POST.get(f'class_domain_rating_{school_class.id}_{index}_label') or '').strip()
                description = (request.POST.get(f'class_domain_rating_{school_class.id}_{index}_description') or '').strip()
                if label or description:
                    class_guide.append({
                        'label': label,
                        'description': description,
                    })
            if class_guide:
                class_domain_rating_guides[str(school_class.id)] = class_guide[:8]
        settings.class_domain_rating_guides = class_domain_rating_guides
        settings.save()
        
        messages.success(request, 'Report card settings updated successfully!')
        return redirect('core:report_card_settings')

    class_template_map = settings.class_templates or {}
    class_template_rows = [
        {
            'school_class': school_class,
            'selected_template': class_template_map.get(str(school_class.id), ''),
        }
        for school_class in classes
    ]
    signatory_slots = settings.active_signatories()
    while len(signatory_slots) < 3:
        signatory_slots.append({'name': '', 'title': '', 'comment': ''})
    domain_rating_guide_slots = _domain_rating_guide(settings)
    while len(domain_rating_guide_slots) < 5:
        domain_rating_guide_slots.append({'label': '', 'description': ''})
    class_domain_rating_guides = settings.class_domain_rating_guides or {}
    class_domain_rating_guide_rows = []
    for school_class in classes:
        guide_slots = ReportCardSettings._clean_domain_rating_guide(
            class_domain_rating_guides.get(str(school_class.id), [])
        )
        while len(guide_slots) < 5:
            guide_slots.append({'label': '', 'description': ''})
        class_domain_rating_guide_rows.append({
            'school_class': school_class,
            'guide_slots': guide_slots,
            'has_override': str(school_class.id) in class_domain_rating_guides,
        })

    report_teacher_rows = []
    report_teachers = Teacher.all_objects.filter(school=school).select_related('user').order_by(
        'status', 'user__first_name', 'user__last_name', 'employee_id',
    ) if school else Teacher.objects.none()
    if selected_teacher_term:
        for school_class in classes:
            placements = StudentTermPlacement.all_objects.filter(
                term=selected_teacher_term,
                school_class=school_class,
                student__school=school,
            ).select_related('class_teacher__user')
            frozen_names = list(
                placements.filter(signatory_frozen=True)
                .exclude(teacher_name='')
                .values_list('teacher_name', flat=True)
                .distinct()
            )
            if len(frozen_names) == 1:
                current_teacher_label = frozen_names[0]
            elif len(frozen_names) > 1:
                current_teacher_label = 'Mixed historical teachers'
            else:
                assigned_teachers = list(
                    ClassTeacher.all_objects.filter(
                        school_class=school_class,
                        teacher__school=school,
                        teacher__status='active',
                    ).select_related('teacher__user')[:2]
                )
                if len(assigned_teachers) == 1:
                    assigned_user = assigned_teachers[0].teacher.user
                    current_teacher_label = assigned_user.get_full_name() or assigned_user.username
                elif len(assigned_teachers) > 1:
                    current_teacher_label = 'Multiple class teachers assigned'
                else:
                    current_teacher_label = 'No teacher set'
            report_teacher_rows.append({
                'school_class': school_class,
                'current_teacher_label': current_teacher_label,
            })

    return render(request, 'admin/report_card_settings.html', {
        'settings': settings,
        'classes': classes,
        'template_choices': template_choices,
        'third_term_mode_choices': ReportCardSettings.THIRD_TERM_MODE_CHOICES,
        'class_template_rows': class_template_rows,
        'signatory_slots': signatory_slots,
        'domain_rating_guide_slots': domain_rating_guide_slots,
        'class_domain_rating_guide_rows': class_domain_rating_guide_rows,
        'terms': terms,
        'selected_teacher_term': selected_teacher_term,
        'report_teachers': report_teachers,
        'report_teacher_rows': report_teacher_rows,
    })

@login_required
def student_results_lookup(request):
    if not request.user.has_any_role(['super_admin', 'subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    if not _request_user_has_result_access(request):
        _deny_result_access_message(request)
        return redirect('core:dashboard')

    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Open a school tenant before viewing student results.')
        return redirect('core:dashboard')

    students = Student.all_objects.select_related('user', 'school_class').order_by(
        'school_class__name',
        'school_class__stream',
        'user__first_name',
        'user__last_name',
    )
    classes = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')
    terms = Term.all_objects.order_by('-start_date')
    students = students.filter(school=school)
    terms = terms.filter(school=school)

    is_limited_report_lookup = not request.user.has_role('super_admin')
    report_lookup_class_ids = []
    if is_limited_report_lookup:
        report_lookup_class_ids = _teacher_report_class_ids(
            request.user,
            school,
            role=request.session.get('selected_role') or getattr(request.user, 'role', None),
        )
        students = students.filter(
            Q(school_class_id__in=report_lookup_class_ids) |
            Q(term_placements__school_class_id__in=report_lookup_class_ids) |
            Q(componentresult__component__school_class_id__in=report_lookup_class_ids)
        ).distinct()
        classes = classes.filter(id__in=report_lookup_class_ids)
        blocked_student_user_ids = [
            membership.user_id for membership in SchoolMembership.objects.filter(
                Q(is_active=False) | Q(portal_access_enabled=False) | Q(result_access_enabled=False),
                school=school,
            )
        ]
        if blocked_student_user_ids:
            students = students.exclude(user_id__in=blocked_student_user_ids)
    
    return render(request, 'admin/student_results_lookup.html', {
        'students': students,
        'classes': classes,
        'terms': terms,
        'is_limited_report_lookup': is_limited_report_lookup,
        'report_lookup_class_count': len(report_lookup_class_ids),
    })

def enhanced_quiz(request, quiz_id):
    from .views_quiz import enhanced_quiz as handler
    return handler(request, quiz_id)

