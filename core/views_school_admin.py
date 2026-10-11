from datetime import timedelta
from functools import lru_cache

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

from .forms_academic import AcademicEventForm, HolidayForm
from .services_term_placements import capture_term_placement, students_for_term
from .staffing import active_staff, active_students
from .forms_school_admin import (
    ClassTeacherSignatureForm,
    ClassTeacherStudentRegistrationForm,
    SchoolBulkResultComponentForm,
    SchoolClassTeacherAssignmentForm,
    SchoolClassForm,
    SchoolCommunicationForm,
    SchoolExamScheduleForm,
    SchoolGradingSystemForm,
    SchoolHeadTeacherAssignmentForm,
    SchoolResultComponentForm,
    SchoolSettingsForm,
    SchoolStudentForm,
    SchoolSubjectForm,
    SchoolTeacherForm,
    SchoolTermForm,
    SchoolUserForm,
    SchoolUserPasswordResetForm,
    SchoolWardParentAssignmentForm,
)
from .models import (
    AcademicEvent,
    ClassTeacher,
    EffectiveDomain,
    ExamSchedule,
    GradingSystem,
    HeadTeacher,
    Holiday,
    LearnerDomainCriterion,
    LearnerDomainRating,
    Psychomotor,
    Result,
    ResultComponent,
    ReportCardSettings,
    SchoolClass,
    SchoolSettings,
    SchoolMembership,
    Student,
    Subject,
    Teacher,
    Term,
    NotificationLog,
)
from .models_biodata import Guardian
from .tenant_permissions import grant_school_admin_permissions
from .services_school_communication import SchoolCommunicationService
from .services_portal_delivery import TenantPortalDeliveryService, delivery_channels_from_post

User = get_user_model()


def _is_school_admin_user(request):
    if request.user.is_superuser:
        return True
    if getattr(request.user, 'has_role', None) and request.user.has_any_role(['super_admin', 'administrator']):
        return True
    return False


def _require_school_admin(request):
    if _is_school_admin_user(request):
        return True
    messages.error(request, 'You do not have permission to access school management.')
    return False


def _active_school_or_redirect(request):
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
    return school


def _ensure_admin_staff_profile(school, user, roles, custom_job_title='', active=True):
    from .staffing import ensure_staff_profile
    return ensure_staff_profile(school, user, roles, custom_job_title, active)


def _get_class_teacher_assignment(user, school):
    if not school:
        return None
    try:
        teacher = Teacher.all_objects.get(user=user, school=school, status='active')
    except Teacher.DoesNotExist:
        return None
    return _class_teacher_assignments_for_teacher(teacher, school).first()


def _class_teacher_assignments_for_teacher(teacher, school):
    if not teacher or not school:
        return ClassTeacher.objects.none()
    return ClassTeacher.objects.filter(
        teacher=teacher,
        teacher__status='active',
        school_class__school=school,
    ).select_related('teacher__user', 'school_class').order_by('school_class__name', 'school_class__stream')


def _require_school_admin_or_class_teacher(request):
    if _is_school_admin_user(request):
        return True
    school = getattr(request, 'school', None)
    if school and _get_class_teacher_assignment(request.user, school):
        return True
    messages.error(request, 'You do not have permission to access this class management page.')
    return False


def _require_assessment_setup_access(request):
    if _is_school_admin_user(request):
        return True

    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
        return False

    teacher = Teacher.all_objects.filter(user=request.user, school=school, status='active').first()
    if teacher and request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return True

    messages.error(request, 'You do not have permission to access assessment setup.')
    return False


def _assessment_scope_for_teacher(teacher, school):
    class_teacher_class_ids = ClassTeacher.objects.filter(
        teacher=teacher,
        school_class__school=school,
    ).values_list('school_class_id', flat=True)
    classes = SchoolClass.all_objects.filter(
        Q(id__in=teacher.classes.filter(school=school).values_list('id', flat=True)) |
        Q(id__in=class_teacher_class_ids)
    ).distinct().order_by('name', 'stream')
    subjects = teacher.subjects.filter(school=school, subject_type='academic').order_by('name')

    if not subjects.exists():
        subjects = Subject.all_objects.filter(
            school=school,
            subject_type='academic',
            timetable__school_class__in=classes,
        ).distinct().order_by('name')

    if not subjects.exists():
        subjects = Subject.all_objects.filter(
            school=school,
            subject_type='academic',
            resultcomponent__school_class__in=classes,
        ).distinct().order_by('name')

    return classes, subjects


def _parent_ward_assignment_scope(request, school):
    if _is_school_admin_user(request):
        return True, None

    assignment = _get_class_teacher_assignment(request.user, school)
    if assignment and assignment.can_assign_parent_wards:
        return True, assignment.school_class

    return False, None


def _parent_title_for_relationship(relationship):
    if relationship == 'mother':
        return 'Mrs'
    if relationship == 'father':
        return 'Mr'
    return 'Mr'


def _guardian_defaults(student, parent_user, relationship, is_primary_contact=False, is_emergency_contact=False):
    first_name = parent_user.first_name or parent_user.username
    last_name = parent_user.last_name or 'Parent'
    phone_number = getattr(parent_user, 'phone', '') or '00000000000'
    email = parent_user.email or ''
    return {
        'relationship': relationship,
        'title': _parent_title_for_relationship(relationship),
        'first_name': first_name,
        'last_name': last_name,
        'phone_number': phone_number,
        'email': email,
        'occupation': 'Not provided',
        'home_address': student.address or 'Not provided',
        'is_primary_contact': is_primary_contact,
        'is_emergency_contact': is_emergency_contact,
    }


DEFAULT_TRANSCRIPT_GRADES = [
    {'min': 90, 'max': 100, 'grade': 'A+', 'remark': 'Excellent'},
    {'min': 80, 'max': 89.99, 'grade': 'A', 'remark': 'Excellent'},
    {'min': 70, 'max': 79.99, 'grade': 'B', 'remark': 'Very Good'},
    {'min': 60, 'max': 69.99, 'grade': 'C', 'remark': 'Good'},
    {'min': 50, 'max': 59.99, 'grade': 'D', 'remark': 'Fair'},
    {'min': 0, 'max': 49.99, 'grade': 'F', 'remark': 'Needs Improvement'},
]


def _transcript_grade_for_score(school, score):
    score = float(score or 0)
    fallback_score = max(0, min(score, 100))
    grading = GradingSystem.all_objects.filter(
        school=school,
        min_score__lte=score,
        max_score__gte=score,
    ).order_by('-min_score').first()
    if grading:
        return {
            'grade': grading.grade,
            'grade_point': grading.grade_point,
            'remark': grading.remark,
        }

    for fallback in DEFAULT_TRANSCRIPT_GRADES:
        if fallback['min'] <= fallback_score <= fallback['max']:
            return {
                'grade': fallback['grade'],
                'grade_point': '',
                'remark': fallback['remark'],
            }

    return {'grade': '-', 'grade_point': '', 'remark': '-'}


def _school_member_queryset(school):
    return SchoolMembership.objects.filter(
        school=school,
        user__is_superuser=False,
    ).select_related('user')


def _get_editable_member(school, user_id):
    if not user_id:
        return None
    return _school_member_queryset(school).filter(user_id=user_id).first()


def _related_usage_summary(obj):
    usage = []
    for relation in obj._meta.related_objects:
        accessor_name = relation.get_accessor_name()
        if not accessor_name:
            continue
        try:
            related = getattr(obj, accessor_name)
            if hasattr(related, 'exists'):
                count = related.count()
            else:
                count = 1 if related else 0
        except relation.related_model.DoesNotExist:
            count = 0
        if count:
            label = relation.related_model._meta.verbose_name_plural
            usage.append(f'{count} {label}')
    return usage


EFFECTIVE_LEGACY_FIELDS = [
    'punctuality',
    'neatness',
    'attentiveness',
    'politeness',
    'relationship_with_others',
]
PSYCHOMOTOR_LEGACY_FIELDS = [
    'sports_games',
    'handwriting',
    'drawing_painting',
    'crafts',
    'music_drama',
]


def _domain_redirect(selected_class_id=None, selected_term_id=None):
    query = []
    if selected_class_id:
        query.append(f'school_class={selected_class_id}')
    if selected_term_id:
        query.append(f'term={selected_term_id}')
    url = reverse('core:school_admin_learner_domains')
    return f'{url}?{"&".join(query)}' if query else url


def _criterion_name_exists(school, domain_type, name, exclude_id=None):
    queryset = LearnerDomainCriterion.all_objects.filter(
        school=school,
        domain_type=domain_type,
        is_active=True,
        name__iexact=name,
    )
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    return queryset.exists()


def _active_criterion_by_name(school, domain_type, name):
    return LearnerDomainCriterion.all_objects.filter(
        school=school,
        domain_type=domain_type,
        is_active=True,
        name__iexact=name,
    ).first()


def _learner_domain_criteria_for_class(school, school_class):
    queryset = LearnerDomainCriterion.all_objects.filter(
        school=school,
        is_active=True,
    )
    if school_class and _learner_domain_criterion_supports_class_scope():
        queryset = queryset.filter(
            Q(classes__isnull=True) |
            Q(classes=school_class)
        ).distinct()
    return queryset.order_by('domain_type', 'display_order', 'name')


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


def _criterion_class_ids_from_post(request, school, selected_class_id=None):
    if not _learner_domain_criterion_supports_class_scope():
        return None

    scope = request.POST.get('criterion_scope', 'all')
    selected_class = SchoolClass.all_objects.filter(school=school, id=selected_class_id).first()
    if scope == 'selected':
        return [selected_class.id] if selected_class else []

    if scope == 'specific':
        class_ids = list(SchoolClass.all_objects.filter(
            school=school,
            id__in=request.POST.getlist('criterion_classes'),
        ).values_list('id', flat=True))
        if not class_ids and selected_class:
            return [selected_class.id]
        return class_ids

    return None


def _make_existing_criterion_available_for_scope(criterion, class_ids):
    if not _learner_domain_criterion_supports_class_scope():
        return False

    current_class_ids = set(
        criterion.classes.filter(school=criterion.school).values_list('id', flat=True)
    )
    if not current_class_ids:
        return False

    if class_ids is None:
        criterion.classes.clear()
    else:
        tenant_class_ids = SchoolClass.all_objects.filter(
            school=criterion.school,
            id__in=current_class_ids.union(class_ids),
        ).values_list('id', flat=True)
        criterion.classes.set(tenant_class_ids)
    return True


def _set_criterion_classes_for_scope(criterion, class_ids):
    criterion.classes.set([] if class_ids is None else class_ids)


def _prepare_criterion_class_scope(criteria):
    if not _learner_domain_criterion_supports_class_scope():
        for criterion in criteria:
            criterion.assigned_class_ids = []
            criterion.assigned_class_names = ''
            criterion.applies_to_all_classes = True
        return

    for criterion in criteria:
        assigned_classes = list(criterion.classes.all())
        criterion.assigned_class_ids = [school_class.id for school_class in assigned_classes]
        criterion.assigned_class_names = ', '.join(str(school_class) for school_class in assigned_classes)
        criterion.applies_to_all_classes = not assigned_classes


def _clean_domain_rating_guide_from_post(request, prefix='domain_rating'):
    guide = []
    for index in range(1, 9):
        label = (request.POST.get(f'{prefix}_{index}_label') or '').strip()
        description = (request.POST.get(f'{prefix}_{index}_description') or '').strip()
        if label or description:
            guide.append({
                'label': label,
                'description': description,
            })
    return guide[:8]


def _school_report_card_settings(school):
    settings = ReportCardSettings.all_objects.filter(school=school, is_active=True).first()
    if not settings:
        settings = ReportCardSettings.all_objects.filter(school=school).first()
    if not settings:
        settings = ReportCardSettings(school=school)
    return settings


def _school_domain_rating_guide(school, school_class=None):
    settings = _school_report_card_settings(school)
    if settings:
        return settings.active_domain_rating_guide(school_class)
    return []


@login_required
def school_admin_dashboard(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    context = {
        'school': school,
        'total_users': _school_member_queryset(school).filter(is_active=True).count(),
        'total_students': active_students(school).count(),
        'total_staff': active_staff(school).count(),
        'total_classes': SchoolClass.all_objects.filter(school=school).count(),
        'total_subjects': Subject.all_objects.filter(school=school).count(),
        'total_assessments': ResultComponent.objects.filter(school_class__school=school).count(),
        'total_effective_domains': EffectiveDomain.objects.filter(student__school=school).count(),
        'total_psychomotor_domains': Psychomotor.objects.filter(student__school=school).count(),
    }
    return render(request, 'school_admin/dashboard.html', context)


@login_required
def school_admin_settings(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    settings = SchoolSettings.all_objects.filter(school=school).first()
    fallback_settings = SchoolSettings.get_for_school(school)
    initial = {}
    if not settings and fallback_settings:
        for field_name in SchoolSettingsForm.Meta.fields:
            if field_name not in ['school_logo', 'school_seal', 'principal_signature']:
                initial[field_name] = getattr(fallback_settings, field_name, '')
    initial.setdefault('school_name', school.name)

    form = SchoolSettingsForm(
        request.POST or None,
        request.FILES or None,
        instance=settings,
        initial=initial,
    )
    if request.method == 'POST' and form.is_valid():
        settings = form.save(commit=False)
        settings.school = school
        settings.save()
        messages.success(request, 'School details saved successfully.')
        return redirect('core:school_admin_settings')

    return render(request, 'school_admin/settings.html', {
        'school': school,
        'form': form,
        'school_settings_record': settings,
    })


@login_required
def class_teacher_signature(request):
    """Let an assigned class teacher maintain the signature used on report cards."""
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    teacher = Teacher.all_objects.filter(user=request.user, school=school, status='active').first()
    assignments = _class_teacher_assignments_for_teacher(teacher, school)
    if not teacher or not assignments.exists():
        messages.error(request, 'Only assigned class teachers can update a class-teacher signature.')
        return redirect('core:dashboard')

    form = ClassTeacherSignatureForm(
        request.POST or None,
        request.FILES or None,
        instance=teacher,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your class-teacher signature has been saved.')
        return redirect('core:class_teacher_signature')

    return render(request, 'class_teacher/signature.html', {
        'school': school,
        'teacher': teacher,
        'assignments': assignments,
        'form': form,
    })


@login_required
def class_teacher_students(request):
    """Allow an assigned class teacher to enrol learners in only their classes."""
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    teacher = Teacher.all_objects.filter(user=request.user, school=school, status='active').first()
    assignments = _class_teacher_assignments_for_teacher(teacher, school)
    if not teacher or not assignments.exists():
        messages.error(request, 'Only assigned class teachers can add students.')
        return redirect('core:dashboard')

    form = ClassTeacherStudentRegistrationForm(
        request.POST or None,
        request.FILES or None,
        school=school,
        teacher=teacher,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            student = form.save(school)
        except IntegrityError:
            form.add_error(None, 'This student could not be saved because one of the values already exists.')
        else:
            messages.success(
                request,
                f'{student.user.get_full_name() or student.user.username} was added successfully. '
                f'Student ID: {student.student_id}.',
            )
            return redirect('core:class_teacher_students')

    assigned_classes = SchoolClass.all_objects.filter(
        school=school,
        class_teacher_assignments__teacher=teacher,
    ).distinct().order_by('name', 'stream')
    students = Student.all_objects.filter(
        school=school,
        school_class__in=assigned_classes,
        status='active',
    ).select_related('user', 'school_class').order_by(
        'school_class__name',
        'school_class__stream',
        'user__first_name',
        'user__last_name',
        'student_id',
    )

    return render(request, 'class_teacher/students.html', {
        'school': school,
        'teacher': teacher,
        'assignments': assignments,
        'assigned_classes': assigned_classes,
        'students': students,
        'form': form,
    })


@login_required
def school_admin_communications(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    form = SchoolCommunicationForm(request.POST or None, school=school)
    if request.method == 'POST' and form.is_valid():
        service = SchoolCommunicationService(school)
        message_type = form.cleaned_data['message_type']
        results = []
        if message_type in ['result', 'fee_statement'] and form.cleaned_data['send_to_all_students']:
            students = Student.all_objects.filter(school=school).select_related('user')
        else:
            students = [form.cleaned_data.get('student')]

        if message_type == 'result':
            results = [service.send_result(student, form.cleaned_data['term']) for student in students]
        elif message_type == 'fee_statement':
            results = [service.send_fee_statement(student) for student in students]
        elif message_type == 'payslip':
            results = [service.send_payslip(form.cleaned_data['payroll'])]
        else:
            results = [service.send_announcement(
                form.cleaned_data['audience'],
                form.cleaned_data['subject'],
                form.cleaned_data['message'],
            )]

        result = {
            key: sum(item[key] for item in results)
            for key in ['sent', 'failed', 'skipped']
        }

        if result['sent']:
            messages.success(
                request,
                f"Communication sent to {result['sent']} recipient(s). Failed: {result['failed']}. Skipped: {result['skipped']}.",
            )
        else:
            messages.error(request, 'No communication was sent. Confirm that recipient email addresses and selected records are available.')
        return redirect('core:school_admin_communications')

    recent_logs = NotificationLog.all_objects.filter(school=school).order_by('-created_at')[:20]
    return render(request, 'school_admin/communications.html', {
        'school': school,
        'form': form,
        'recent_logs': recent_logs,
    })


@login_required
def school_admin_result_publication(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    if request.method == 'POST':
        term = get_object_or_404(Term.all_objects, id=request.POST.get('term_id'), school=school)
        action = request.POST.get('action')
        if action not in ['publish', 'unpublish']:
            messages.error(request, 'Choose whether to publish or unpublish the selected results.')
            return redirect('core:school_admin_result_publication')

        if action == 'publish' and not Result.all_objects.filter(
            student__school=school,
            term=term,
        ).exists():
            messages.error(
                request,
                f'{term.name} {term.session} has no results to publish. Enter and save results before publishing the term.',
            )
            return redirect('core:school_admin_result_publication')

        with transaction.atomic():
            term.result_published = action == 'publish'
            if term.result_published:
                students = Student.all_objects.filter(
                    school=school, result__term=term,
                ).distinct()
                for student in students:
                    capture_term_placement(student, term, freeze_teacher=True)
            term.save(update_fields=['result_published'])
        if term.result_published:
            messages.success(request, f'{term.name} {term.session} results have been published to student and parent portals.')
        else:
            messages.success(request, f'{term.name} {term.session} results have been unpublished and are no longer visible on student and parent portals.')
        return redirect('core:school_admin_result_publication')

    terms = Term.all_objects.filter(school=school).order_by('-start_date')
    result_summaries = {
        item['term_id']: item
        for item in Result.all_objects.filter(student__school=school).values('term_id').annotate(
            total=Count('id'),
            students=Count('student_id', distinct=True),
        )
    }
    for term in terms:
        summary = result_summaries.get(term.id, {})
        term.portal_result_count = summary.get('total', 0)
        term.portal_student_count = summary.get('students', 0)

    return render(request, 'school_admin/result_publication.html', {
        'school': school,
        'terms': terms,
    })


@login_required
def school_admin_users(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_user = None
    form = SchoolUserForm()
    password_reset_form = None

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'delete_user':
            membership = _get_editable_member(school, request.POST.get('user_id'))
            if not membership:
                messages.error(request, 'That user is not managed under this school.')
                return redirect('core:school_admin_users')

            user = membership.user
            if user == request.user:
                messages.error(request, 'You cannot delete your own user account from this page.')
                return redirect('core:school_admin_users')

            display_name = user.get_full_name() or user.username
            membership.delete()
            if not user.school_memberships.exists() and not user.is_superuser:
                user.delete()
                messages.success(request, f'{display_name} deleted successfully.')
            else:
                messages.success(request, f'{display_name} removed from {school.name}.')
            return redirect('core:school_admin_users')

        if action == 'send_login_details':
            membership = _get_editable_member(school, request.POST.get('user_id'))
            if not membership:
                messages.error(request, 'That user is not managed under this school.')
                return redirect('core:school_admin_users')
            if not membership.has_portal_access():
                messages.error(request, 'Enable portal access for this user before sending login details.')
                return redirect('core:school_admin_users')

            target_user = membership.user
            temporary_password = get_random_string(
                10,
                allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789',
            )
            target_user.set_password(temporary_password)
            target_user.is_active = True
            target_user.save(update_fields=['password', 'is_active'])

            channels = delivery_channels_from_post(request.POST, default=['email'])
            summary = TenantPortalDeliveryService(
                school,
                sender=request.user,
                request=request,
            ).send_login_details(target_user, temporary_password, channels)
            message_text = f'Login details processed for {target_user.get_full_name() or target_user.username}: {summary.as_message()}.'
            if summary.failed:
                messages.warning(request, message_text)
            else:
                messages.success(request, message_text)
            return redirect('core:school_admin_users')

        if action == 'reset_password':
            membership = _get_editable_member(school, request.POST.get('user_id'))
            if not membership:
                messages.error(request, 'That user is not managed under this school.')
                return redirect('core:school_admin_users')

            editing_user = membership.user
            form = SchoolUserForm(initial={
                'user_id': editing_user.id,
                'username': editing_user.username,
                'first_name': editing_user.first_name,
                'last_name': editing_user.last_name,
                'email': editing_user.email,
                'phone': editing_user.phone,
                'role': membership.primary_role,
                'extra_roles': membership.extra_roles or [],
                'custom_job_title': getattr(getattr(editing_user, 'teacher', None), 'custom_job_title', ''),
                'is_active': membership.is_active,
                'portal_access_enabled': membership.portal_access_enabled,
                'result_access_enabled': membership.result_access_enabled,
            }, include_password=False)
            password_reset_form = SchoolUserPasswordResetForm(request.POST)
            if password_reset_form.is_valid():
                editing_user.set_password(password_reset_form.cleaned_data['new_password'])
                editing_user.save(update_fields=['password'])
                messages.success(request, f'Password reset successfully for {editing_user.get_full_name() or editing_user.username}.')
                return redirect('core:school_admin_users')
        else:
            user_id = request.POST.get('user_id')
            form = SchoolUserForm(request.POST, include_password=not bool(user_id))

        if form.is_valid():
            user_id = form.cleaned_data.get('user_id')
            membership = _get_editable_member(school, user_id)

            if user_id and not membership:
                messages.error(request, 'That user is not managed under this school.')
                return redirect('core:school_admin_users')

            user = membership.user if membership else User(username=form.cleaned_data['username'])
            editing_user = user if user.pk else None

            duplicate_username = User.objects.filter(
                username=form.cleaned_data['username']
            ).exclude(pk=user.pk).exists()
            if duplicate_username:
                form.add_error('username', 'A user with this username already exists.')
            else:
                role = form.cleaned_data['role']
                extra_roles = form.cleaned_data.get('extra_roles') or []
                is_active = form.cleaned_data.get('is_active', True)
                portal_access_enabled = form.cleaned_data.get('portal_access_enabled', True)
                result_access_enabled = form.cleaned_data.get('result_access_enabled', True)

                user.username = form.cleaned_data['username']
                user.first_name = form.cleaned_data.get('first_name', '')
                user.last_name = form.cleaned_data.get('last_name', '')
                user.email = form.cleaned_data.get('email', '')
                user.phone = form.cleaned_data.get('phone', '')
                user.role = role
                user.extra_roles = extra_roles
                user.is_staff = False
                if not user.pk:
                    user.is_active = True
                    password = form.cleaned_data.get('password')
                    if password:
                        user.set_password(password)
                    else:
                        user.set_unusable_password()

                try:
                    user.save()
                    SchoolMembership.objects.update_or_create(
                        school=school,
                        user=user,
                        defaults={
                            'primary_role': role,
                            'extra_roles': extra_roles,
                            'is_active': is_active,
                            'portal_access_enabled': portal_access_enabled,
                            'result_access_enabled': result_access_enabled,
                        },
                    )
                    _, staff_profile_created = _ensure_admin_staff_profile(
                        school,
                        user,
                        [role, *extra_roles],
                        form.cleaned_data.get('custom_job_title', ''),
                        active=is_active,
                    )
                    grant_school_admin_permissions(user)
                    staff_note = ' Staff profile created.' if staff_profile_created else ''
                    messages.success(request, f'{user.get_full_name() or user.username} saved successfully.{staff_note}')
                    return redirect('core:school_admin_users')
                except IntegrityError:
                    form.add_error(None, 'This user could not be saved because one of the values already exists.')
        else:
            user_id = request.POST.get('user_id')
            membership = _get_editable_member(school, user_id)
            editing_user = membership.user if membership else None
    else:
        edit_user_id = request.GET.get('user')
        membership = _get_editable_member(school, edit_user_id)
        if membership:
            editing_user = membership.user
            form = SchoolUserForm(initial={
                'user_id': editing_user.id,
                'username': editing_user.username,
                'first_name': editing_user.first_name,
                'last_name': editing_user.last_name,
                'email': editing_user.email,
                'phone': editing_user.phone,
                'role': membership.primary_role,
                'extra_roles': membership.extra_roles or [],
                'custom_job_title': getattr(getattr(editing_user, 'teacher', None), 'custom_job_title', ''),
                'is_active': membership.is_active,
                'portal_access_enabled': membership.portal_access_enabled,
                'result_access_enabled': membership.result_access_enabled,
            }, include_password=False)
            password_reset_form = SchoolUserPasswordResetForm(initial={'user_id': editing_user.id})
        elif edit_user_id:
            messages.error(request, 'That user is not managed under this school.')
            return redirect('core:school_admin_users')

    if editing_user and password_reset_form is None:
        password_reset_form = SchoolUserPasswordResetForm(initial={'user_id': editing_user.id})

    search = request.GET.get('search', '').strip()
    memberships = _school_member_queryset(school)
    if search:
        memberships = memberships.filter(
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    return render(request, 'school_admin/users.html', {
        'school': school,
        'memberships': memberships.order_by('user__first_name', 'user__last_name', 'user__username'),
        'form': form,
        'password_reset_form': password_reset_form,
        'search': search,
        'editing_user': editing_user,
    })


@login_required
def school_admin_students(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_student = None
    student_form = SchoolStudentForm(school=school)

    if request.method == 'POST':
        student_pk = request.POST.get('student_pk')
        instance = None
        if student_pk:
            instance = Student.all_objects.filter(id=student_pk, school=school).first()
            if not instance:
                messages.error(request, 'That student profile is not managed under this school.')
                return redirect('core:school_admin_students')
            editing_student = instance

        student_form = SchoolStudentForm(request.POST, request.FILES, instance=instance, school=school)
        if student_form.is_valid():
            student = student_form.save(commit=False)
            student.school = school
            student.archived_at = None if student.status == 'active' else (student.archived_at or timezone.now())
            try:
                student.save()
                membership = SchoolMembership.objects.filter(school=school, user=student.user).first()
                if membership:
                    is_active_student = student.status == 'active'
                    membership.is_active = is_active_student
                    membership.portal_access_enabled = is_active_student
                    membership.result_access_enabled = is_active_student
                    membership.save(update_fields=[
                        'is_active', 'portal_access_enabled', 'result_access_enabled', 'updated_at',
                    ])
                messages.success(request, f'Student profile saved successfully. Student ID: {student.student_id}.')
                return redirect('core:school_admin_students')
            except IntegrityError:
                student_form.add_error(None, 'This student could not be saved because one of the values already exists.')
    else:
        edit_student_id = request.GET.get('student')
        if edit_student_id:
            editing_student = Student.all_objects.filter(id=edit_student_id, school=school).first()
            if not editing_student:
                messages.error(request, 'That student profile is not managed under this school.')
                return redirect('core:school_admin_students')
            student_form = SchoolStudentForm(instance=editing_student, school=school)

    students = Student.all_objects.filter(school=school).select_related('user', 'school_class').order_by('student_id')
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'active').strip()
    class_filter = request.GET.get('class_id', '').strip()
    if status_filter != 'all':
        students = students.filter(status=status_filter)
    if class_filter:
        students = students.filter(school_class_id=class_filter)
    if search:
        students = students.filter(
            Q(student_id__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    return render(request, 'school_admin/students.html', {
        'school': school,
        'students': students,
        'search': search,
        'form': student_form,
        'editing_student': editing_student,
        'status_filter': status_filter,
        'class_filter': class_filter,
        'classes': SchoolClass.all_objects.filter(school=school).order_by('name', 'stream'),
        'active_count': active_students(school).count(),
        'archived_count': Student.all_objects.filter(school=school).exclude(status='active').count(),
    })


@login_required
def school_admin_transcripts(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    search = request.GET.get('search', '').strip()
    selected_student_id = request.GET.get('student')
    students = Student.all_objects.filter(
        school=school,
    ).select_related('user', 'school_class').order_by(
        'school_class__name',
        'school_class__stream',
        'user__first_name',
        'user__last_name',
        'student_id',
    )

    if search:
        students = students.filter(
            Q(student_id__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(school_class__name__icontains=search) |
            Q(school_class__stream__icontains=search)
        )

    selected_student = None
    transcript_terms = []
    overall_average = 0
    overall_grade = ''
    overall_remark = ''
    school_settings = SchoolSettings.get_for_school(school)
    signatory = None

    if selected_student_id:
        selected_student = Student.all_objects.filter(
            id=selected_student_id,
            school=school,
        ).select_related('user', 'school_class').first()
        if not selected_student:
            messages.error(request, 'That learner is not managed under this school.')
            return redirect('/school-admin/transcripts/')

        results = Result.objects.filter(
            student=selected_student,
        ).select_related('subject', 'term').order_by(
            'term__session',
            'term__start_date',
            'subject__name',
        )

        term_map = {}
        for result in results:
            term = result.term
            if term.id not in term_map:
                term_map[term.id] = {
                    'term': term,
                    'results': [],
                    'total_score': 0,
                    'subject_count': 0,
                    'average': 0,
                    'grade': '',
                    'remark': '',
                }
            term_data = term_map[term.id]
            score = float(result.total_score or 0)
            result_grade = _transcript_grade_for_score(school, score)
            term_data['results'].append({
                'subject': result.subject,
                'score': score,
                'grade': result_grade['grade'],
                'remark': result_grade['remark'],
            })
            term_data['total_score'] += score
            term_data['subject_count'] += 1

        all_scores_total = 0
        all_scores_count = 0
        for term_data in term_map.values():
            if term_data['subject_count']:
                term_data['average'] = term_data['total_score'] / term_data['subject_count']
                all_scores_total += term_data['total_score']
                all_scores_count += term_data['subject_count']
                term_grade = _transcript_grade_for_score(school, term_data['average'])
                term_data['grade'] = term_grade['grade']
                term_data['remark'] = term_grade['remark']

        transcript_terms = list(term_map.values())
        if all_scores_count:
            overall_average = all_scores_total / all_scores_count
            overall_grading = _transcript_grade_for_score(school, overall_average)
            overall_grade = overall_grading['grade']
            overall_remark = overall_grading['remark']

        signatory = HeadTeacher.objects.filter(
            teacher__school=school,
            classes=selected_student.school_class,
        ).select_related('teacher__user').first()
        if not signatory:
            signatory = HeadTeacher.objects.filter(
                teacher__school=school,
            ).select_related('teacher__user').order_by('title', 'teacher__user__first_name').first()

    return render(request, 'school_admin/transcripts.html', {
        'school': school,
        'school_settings': school_settings,
        'students': students,
        'selected_student': selected_student,
        'transcript_terms': transcript_terms,
        'overall_average': overall_average,
        'overall_grade': overall_grade,
        'overall_remark': overall_remark,
        'search': search,
        'signatory': signatory,
    })


@login_required
def school_admin_staff(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_teacher = None
    teacher_form = SchoolTeacherForm(school=school)

    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        instance = None
        if teacher_id:
            instance = get_object_or_404(Teacher.all_objects, id=teacher_id, school=school)
            editing_teacher = instance

        teacher_form = SchoolTeacherForm(request.POST, request.FILES, instance=instance, school=school)
        if teacher_form.is_valid():
            teacher = teacher_form.save(commit=False)
            teacher.school = school
            teacher.archived_at = None if teacher.status == 'active' else (teacher.archived_at or timezone.now())
            try:
                teacher.save()
                teacher_form.save_m2m()
                membership = SchoolMembership.objects.filter(school=school, user=teacher.user).first()
                if membership:
                    is_active_teacher = teacher.status == 'active'
                    membership.is_active = is_active_teacher
                    membership.portal_access_enabled = is_active_teacher
                    membership.result_access_enabled = is_active_teacher
                    membership.save(update_fields=[
                        'is_active', 'portal_access_enabled', 'result_access_enabled', 'updated_at',
                    ])
                messages.success(request, 'Staff profile saved successfully.')
                return redirect('core:school_admin_staff')
            except IntegrityError:
                teacher_form.add_error(None, 'This staff profile could not be saved because one of the values already exists.')
    else:
        edit_teacher_id = request.GET.get('teacher')
        if edit_teacher_id:
            editing_teacher = get_object_or_404(Teacher.all_objects, id=edit_teacher_id, school=school)
            teacher_form = SchoolTeacherForm(instance=editing_teacher, school=school)

    teachers = Teacher.all_objects.filter(school=school).select_related('user').order_by('employee_id')
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'active').strip()
    valid_statuses = {value for value, _ in Teacher.STATUS_CHOICES}
    if status_filter != 'all':
        if status_filter not in valid_statuses:
            status_filter = 'active'
        teachers = teachers.filter(status=status_filter)
    if search:
        teachers = teachers.filter(
            Q(employee_id__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    return render(request, 'school_admin/staff.html', {
        'school': school,
        'teachers': teachers,
        'search': search,
        'form': teacher_form,
        'editing_teacher': editing_teacher,
        'status_filter': status_filter,
        'status_choices': Teacher.STATUS_CHOICES,
        'active_count': active_staff(school).count(),
        'archived_count': Teacher.all_objects.filter(school=school).exclude(status='active').count(),
    })


@login_required
def school_admin_academic_setup(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_class = None
    editing_subject = None
    editing_term = None
    class_form = SchoolClassForm(school=school)
    subject_form = SchoolSubjectForm(school=school)
    term_form = SchoolTermForm(school=school)

    if request.method == 'POST':
        action = request.POST.get('action')
        object_id = request.POST.get('object_id')

        if action == 'class':
            editing_class = SchoolClass.all_objects.filter(id=object_id, school=school).first() if object_id else None
            if object_id and not editing_class:
                messages.error(request, 'That class is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            class_form = SchoolClassForm(request.POST, school=school, instance=editing_class)
            if class_form.is_valid():
                school_class = class_form.save(commit=False)
                school_class.school = school
                try:
                    school_class.save()
                    messages.success(request, 'Class saved successfully.')
                    return redirect('core:school_admin_academic_setup')
                except IntegrityError:
                    class_form.add_error(None, 'This class could not be saved because it already exists.')

        elif action == 'delete_class':
            school_class = SchoolClass.all_objects.filter(id=object_id, school=school).first()
            if not school_class:
                messages.error(request, 'That class is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            usage = _related_usage_summary(school_class)
            if usage:
                messages.error(
                    request,
                    f'Cannot delete {school_class} because it is linked to {", ".join(usage[:4])}. '
                    'Move or remove those records first.'
                )
                return redirect('core:school_admin_academic_setup')
            school_class.delete()
            messages.success(request, f'{school_class} deleted successfully.')
            return redirect('core:school_admin_academic_setup')

        elif action == 'subject':
            editing_subject = Subject.all_objects.filter(id=object_id, school=school).first() if object_id else None
            if object_id and not editing_subject:
                messages.error(request, 'That subject is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            subject_form = SchoolSubjectForm(request.POST, school=school, instance=editing_subject)
            if subject_form.is_valid():
                subject = subject_form.save(commit=False)
                subject.school = school
                try:
                    subject.save()
                    messages.success(request, 'Subject saved successfully.')
                    return redirect('core:school_admin_academic_setup')
                except IntegrityError:
                    subject_form.add_error(None, 'This subject could not be saved because it already exists.')

        elif action == 'delete_subject':
            subject = Subject.all_objects.filter(id=object_id, school=school).first()
            if not subject:
                messages.error(request, 'That subject is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            usage = _related_usage_summary(subject)
            if usage:
                messages.error(
                    request,
                    f'Cannot delete {subject} because it is linked to {", ".join(usage[:4])}. '
                    'Move or remove those records first.'
                )
                return redirect('core:school_admin_academic_setup')
            subject.delete()
            messages.success(request, f'{subject} deleted successfully.')
            return redirect('core:school_admin_academic_setup')

        elif action == 'term':
            editing_term = Term.all_objects.filter(id=object_id, school=school).first() if object_id else None
            if object_id and not editing_term:
                messages.error(request, 'That term is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            term_form = SchoolTermForm(request.POST, school=school, instance=editing_term)
            if term_form.is_valid():
                term = term_form.save(commit=False)
                term.school = school
                try:
                    term.save()
                    messages.success(request, 'Term saved successfully.')
                    return redirect('core:school_admin_academic_setup')
                except IntegrityError:
                    term_form.add_error(None, 'This term could not be saved because it already exists.')

        elif action == 'delete_term':
            term = Term.all_objects.filter(id=object_id, school=school).first()
            if not term:
                messages.error(request, 'That term is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            usage = _related_usage_summary(term)
            if usage:
                messages.error(
                    request,
                    f'Cannot delete {term.name} {term.session} because it is linked to {", ".join(usage[:4])}. '
                    'Move or remove those records first.'
                )
                return redirect('core:school_admin_academic_setup')
            term.delete()
            messages.success(request, f'{term.name} {term.session} deleted successfully.')
            return redirect('core:school_admin_academic_setup')
    else:
        class_id = request.GET.get('class')
        subject_id = request.GET.get('subject')
        term_id = request.GET.get('term')
        if class_id:
            editing_class = get_object_or_404(SchoolClass.all_objects, id=class_id, school=school)
            class_form = SchoolClassForm(school=school, instance=editing_class)
        if subject_id:
            editing_subject = get_object_or_404(Subject.all_objects, id=subject_id, school=school)
            subject_form = SchoolSubjectForm(school=school, instance=editing_subject)
        if term_id:
            editing_term = get_object_or_404(Term.all_objects, id=term_id, school=school)
            term_form = SchoolTermForm(school=school, instance=editing_term)

    return render(request, 'school_admin/academic_setup.html', {
        'school': school,
        'classes': SchoolClass.all_objects.filter(school=school).order_by('name', 'stream'),
        'subjects': Subject.all_objects.filter(school=school).order_by('name'),
        'terms': Term.all_objects.filter(school=school).order_by('-start_date'),
        'class_form': class_form,
        'subject_form': subject_form,
        'term_form': term_form,
        'editing_class': editing_class,
        'editing_subject': editing_subject,
        'editing_term': editing_term,
    })


@login_required
def school_admin_assessments(request):
    if not _require_assessment_setup_access(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    teacher = None
    if not _is_school_admin_user(request):
        teacher = Teacher.all_objects.filter(user=request.user, school=school, status='active').first()

    editing_component = None
    form = SchoolResultComponentForm(school=school)
    bulk_form = SchoolBulkResultComponentForm(school=school)
    can_use_bulk_assessments = _is_school_admin_user(request)
    component_queryset = ResultComponent.objects.filter(school_class__school=school)
    teacher_classes = None
    teacher_subjects = None

    if teacher:
        teacher_classes, teacher_subjects = _assessment_scope_for_teacher(teacher, school)
        form.fields['school_class'].queryset = teacher_classes
        form.fields['subject'].queryset = teacher_subjects
        bulk_form.fields['school_class'].queryset = teacher_classes
        component_queryset = component_queryset.filter(
            school_class__in=teacher_classes,
            subject__in=teacher_subjects,
        )
        can_use_bulk_assessments = False

    def apply_teacher_scope(component_form):
        if teacher:
            component_form.fields['school_class'].queryset = teacher_classes
            component_form.fields['subject'].queryset = teacher_subjects
        return component_form

    if request.method == 'POST':
        component_id = request.POST.get('component_id')
        action = request.POST.get('action', 'save')

        if action == 'bulk_save':
            if not can_use_bulk_assessments:
                messages.error(request, 'Bulk assessment setup is only available to school admins.')
                return redirect('core:school_admin_assessments')
            bulk_form = SchoolBulkResultComponentForm(request.POST, school=school)
            if bulk_form.is_valid():
                school_class = bulk_form.cleaned_data['school_class']
                component_name = bulk_form.cleaned_data['component_name']
                weight = bulk_form.cleaned_data['weight']
                max_score = bulk_form.cleaned_data['max_score']
                created_count = 0
                updated_count = 0

                for subject in bulk_form.get_target_subjects():
                    _, created = ResultComponent.objects.update_or_create(
                        school_class=school_class,
                        subject=subject,
                        component_name=component_name,
                        defaults={
                            'weight': weight,
                            'max_score': max_score,
                        },
                    )
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                messages.success(
                    request,
                    f'{component_name} applied to {created_count + updated_count} academic subjects '
                    f'for {school_class}. Created {created_count}, updated {updated_count}.',
                )
                return redirect('core:school_admin_assessments')
        else:
            editing_component = component_queryset.filter(id=component_id).first() if component_id else None

            if component_id and not editing_component:
                messages.error(request, 'That assessment component is not managed under this school.')
                return redirect('core:school_admin_assessments')

            if action == 'bulk_delete':
                component_ids = request.POST.getlist('component_ids')
                if not component_ids:
                    messages.error(request, 'Select at least one assessment component before deleting.')
                    return redirect('core:school_admin_assessments')

                delete_queryset = component_queryset.filter(id__in=component_ids)
                deleted_count = delete_queryset.count()
                if not deleted_count:
                    messages.error(request, 'None of the selected assessment components can be deleted from your scope.')
                    return redirect('core:school_admin_assessments')

                delete_queryset.delete()
                messages.success(request, f'{deleted_count} assessment component{"s" if deleted_count != 1 else ""} deleted successfully.')
                return redirect('core:school_admin_assessments')

            if action == 'delete':
                if not editing_component:
                    messages.error(request, 'Select an assessment component before deleting.')
                    return redirect('core:school_admin_assessments')
                editing_component.delete()
                messages.success(request, 'Assessment component deleted successfully.')
                return redirect('core:school_admin_assessments')

            form = apply_teacher_scope(SchoolResultComponentForm(request.POST, instance=editing_component, school=school))
            if form.is_valid():
                try:
                    form.save()
                    messages.success(request, 'Assessment component saved successfully.')
                    return redirect('core:school_admin_assessments')
                except IntegrityError:
                    form.add_error(None, 'This component already exists for the selected class and subject.')
    else:
        component_id = request.GET.get('component')
        if component_id:
            editing_component = component_queryset.filter(id=component_id).first()
            if not editing_component:
                messages.error(request, 'That assessment component is not managed under this school.')
                return redirect('core:school_admin_assessments')
            form = apply_teacher_scope(SchoolResultComponentForm(instance=editing_component, school=school))

    components = component_queryset.select_related('school_class', 'subject').order_by(
        'school_class__name',
        'school_class__stream',
        'subject__name',
        'component_name',
    )

    component_totals = {}
    for component in components:
        key = (component.school_class_id, component.subject_id)
        label = f'{component.school_class} - {component.subject}'
        if key not in component_totals:
            component_totals[key] = {'label': label, 'weight': 0}
        component_totals[key]['weight'] += component.weight

    return render(request, 'school_admin/assessments.html', {
        'school': school,
        'form': form,
        'bulk_form': bulk_form,
        'components': components,
        'component_totals': component_totals.values(),
        'editing_component': editing_component,
        'can_use_bulk_assessments': can_use_bulk_assessments,
    })


@login_required
def school_admin_class_teachers(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    form = SchoolClassTeacherAssignmentForm(school=school)
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        assignment_id = request.POST.get('assignment_id')

        if action == 'delete':
            if not assignment_id:
                messages.error(request, 'Select a class teacher assignment before deleting.')
                return redirect('core:school_admin_class_teachers')
            assignment = ClassTeacher.objects.filter(
                id=assignment_id,
                school_class__school=school,
            ).first()
            if not assignment:
                messages.error(request, 'That class teacher assignment is not managed under this school.')
                return redirect('core:school_admin_class_teachers')
            assignment.delete()
            messages.success(request, 'Class teacher assignment removed successfully.')
            return redirect('core:school_admin_class_teachers')

        form = SchoolClassTeacherAssignmentForm(request.POST, school=school)
        if form.is_valid():
            school_class = form.cleaned_data['school_class']
            teacher = form.cleaned_data['teacher']
            ClassTeacher.objects.update_or_create(
                teacher=teacher,
                school_class=school_class,
                defaults={
                    'can_assign_parent_wards': form.cleaned_data.get('can_assign_parent_wards', False),
                    'can_print_download_results': form.cleaned_data.get('can_print_download_results', False),
                },
            )
            teacher.classes.add(school_class)
            membership = SchoolMembership.objects.filter(school=school, user=teacher.user).first()
            if membership and 'class_teacher' not in membership.get_all_roles():
                extra_roles = membership.extra_roles or []
                extra_roles.append('class_teacher')
                membership.extra_roles = list(dict.fromkeys(extra_roles))
                membership.save(update_fields=['extra_roles', 'updated_at'])
            messages.success(request, f'{teacher} assigned as class teacher for {school_class}.')
            return redirect('core:school_admin_class_teachers')

    assignments = ClassTeacher.objects.filter(
        school_class__school=school,
        teacher__status='active',
    ).select_related('teacher__user', 'school_class').order_by('school_class__name', 'school_class__stream')

    return render(request, 'school_admin/class_teachers.html', {
        'school': school,
        'form': form,
        'assignments': assignments,
    })


@login_required
def school_admin_head_teachers(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    assignments = HeadTeacher.objects.filter(
        teacher__school=school,
        teacher__status='active',
    ).select_related('teacher__user').prefetch_related('classes').order_by('teacher__user__first_name', 'teacher__user__last_name')

    editing_assignment = None
    form = SchoolHeadTeacherAssignmentForm(school=school)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        assignment_id = request.POST.get('assignment_id')
        editing_assignment = assignments.filter(id=assignment_id).first() if assignment_id else None
        if not assignment_id and not editing_assignment and action == 'save':
            teacher_id = request.POST.get('teacher')
            editing_assignment = assignments.filter(teacher_id=teacher_id).first() if teacher_id else None

        if assignment_id and not editing_assignment:
            messages.error(request, 'That head teacher assignment is not managed under this school.')
            return redirect('core:school_admin_head_teachers')

        if action == 'delete':
            if not editing_assignment:
                messages.error(request, 'Select a head teacher assignment before deleting.')
                return redirect('core:school_admin_head_teachers')
            editing_assignment.delete()
            messages.success(request, 'Head teacher assignment removed successfully.')
            return redirect('core:school_admin_head_teachers')

        form = SchoolHeadTeacherAssignmentForm(request.POST, request.FILES, instance=editing_assignment, school=school)
        if form.is_valid():
            assignment = form.save(commit=False)
            selected_classes = list(form.cleaned_data['classes'])
            conflicting_assignments = HeadTeacher.objects.filter(
                classes__in=selected_classes,
                teacher__school=school,
            ).exclude(pk=assignment.pk).distinct()
            for conflicting_assignment in conflicting_assignments:
                conflicting_assignment.classes.remove(*selected_classes)
                if not conflicting_assignment.classes.exists():
                    conflicting_assignment.delete()
            assignment.save()
            form.save_m2m()
            messages.success(request, f'{assignment.teacher.user.get_full_name() or assignment.teacher.user.username} saved as {assignment.title}.')
            return redirect('core:school_admin_head_teachers')
    else:
        assignment_id = request.GET.get('assignment')
        if assignment_id:
            editing_assignment = assignments.filter(id=assignment_id).first()
            if not editing_assignment:
                messages.error(request, 'That head teacher assignment is not managed under this school.')
                return redirect('core:school_admin_head_teachers')
            form = SchoolHeadTeacherAssignmentForm(instance=editing_assignment, school=school)

    return render(request, 'school_admin/head_teachers.html', {
        'school': school,
        'form': form,
        'assignments': assignments,
        'editing_assignment': editing_assignment,
    })


@login_required
def school_admin_parent_wards(request):
    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    has_access, allowed_class = _parent_ward_assignment_scope(request, school)
    if not has_access:
        messages.error(request, 'You need school admin permission before assigning learners to parent accounts.')
        return redirect('core:dashboard')

    form = SchoolWardParentAssignmentForm(school=school, allowed_class=allowed_class)
    guardians = Guardian.objects.filter(student__school=school).select_related(
        'student__user',
        'student__school_class',
        'user',
    )
    students = Student.all_objects.filter(school=school).select_related('user', 'school_class')

    if allowed_class:
        guardians = guardians.filter(student__school_class=allowed_class)
        students = students.filter(school_class=allowed_class)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        guardian_id = request.POST.get('guardian_id')

        if action == 'delete':
            guardian = guardians.filter(id=guardian_id).first()
            if not guardian:
                messages.error(request, 'That parent-ward link is not managed under your allowed scope.')
                return redirect('core:school_admin_parent_wards')
            guardian.delete()
            messages.success(request, 'Parent-ward link removed successfully.')
            return redirect('core:school_admin_parent_wards')

        form = SchoolWardParentAssignmentForm(request.POST, school=school, allowed_class=allowed_class)
        if form.is_valid():
            student = form.cleaned_data['student']
            parent_user = form.cleaned_data['parent_user']
            relationship = form.cleaned_data['relationship']
            defaults = _guardian_defaults(
                student,
                parent_user,
                relationship,
                form.cleaned_data.get('is_primary_contact', False),
                form.cleaned_data.get('is_emergency_contact', False),
            )
            if defaults['is_primary_contact']:
                Guardian.objects.filter(student=student).exclude(user=parent_user).update(is_primary_contact=False)

            guardian = Guardian.objects.filter(student=student, user=parent_user).first()
            if guardian:
                for field, value in defaults.items():
                    setattr(guardian, field, value)
                guardian.save()
            else:
                Guardian.objects.create(student=student, user=parent_user, **defaults)
            messages.success(request, f'{student.user.get_full_name() or student.user.username} linked to {parent_user.get_full_name() or parent_user.username}.')
            return redirect('core:school_admin_parent_wards')

    search = request.GET.get('search', '').strip()
    if search:
        students = students.filter(
            Q(student_id__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search)
        )
        guardians = guardians.filter(
            Q(student__student_id__icontains=search) |
            Q(student__user__first_name__icontains=search) |
            Q(student__user__last_name__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__username__icontains=search)
        )

    linked_student_ids = set(guardians.exclude(user__isnull=True).values_list('student_id', flat=True))

    return render(request, 'school_admin/parent_wards.html', {
        'school': school,
        'form': form,
        'guardians': guardians.order_by('student__school_class__name', 'student__user__first_name', 'student__user__last_name'),
        'students': students.order_by('school_class__name', 'school_class__stream', 'user__first_name', 'user__last_name'),
        'linked_student_ids': linked_student_ids,
        'allowed_class': allowed_class,
        'search': search,
        'is_school_admin_scope': allowed_class is None,
    })


@login_required
def school_admin_grading(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_grade = None
    form = SchoolGradingSystemForm(school=school)

    if request.method == 'POST':
        grade_id = request.POST.get('grade_id')
        action = request.POST.get('action', 'save')
        editing_grade = GradingSystem.all_objects.filter(id=grade_id, school=school).first() if grade_id else None

        if grade_id and not editing_grade:
            messages.error(request, 'That grade range is not managed under this school.')
            return redirect('core:school_admin_grading')

        if action == 'delete':
            if not editing_grade:
                messages.error(request, 'Select a grade range before deleting.')
                return redirect('core:school_admin_grading')
            editing_grade.delete()
            messages.success(request, 'Grade range deleted successfully.')
            return redirect('core:school_admin_grading')

        form = SchoolGradingSystemForm(request.POST, instance=editing_grade, school=school)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.school = school
            grade.save()
            messages.success(request, 'Grade range saved successfully.')
            return redirect('core:school_admin_grading')
    else:
        grade_id = request.GET.get('grade')
        if grade_id:
            editing_grade = GradingSystem.all_objects.filter(id=grade_id, school=school).first()
            if not editing_grade:
                messages.error(request, 'That grade range is not managed under this school.')
                return redirect('core:school_admin_grading')
            form = SchoolGradingSystemForm(instance=editing_grade, school=school)

    grades = GradingSystem.all_objects.filter(school=school).order_by('-min_score')
    return render(request, 'school_admin/grading.html', {
        'school': school,
        'form': form,
        'grades': grades,
        'editing_grade': editing_grade,
    })


@login_required
def school_admin_exam_schedules(request):
    if not _require_school_admin_or_class_teacher(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    class_teacher_assignment = None if _is_school_admin_user(request) else _get_class_teacher_assignment(request.user, school)
    allowed_class = class_teacher_assignment.school_class if class_teacher_assignment else None
    editing_schedule = None
    form = SchoolExamScheduleForm(school=school, allowed_class=allowed_class)

    if request.method == 'POST':
        schedule_id = request.POST.get('schedule_id')
        action = request.POST.get('action', 'save')
        schedules = ExamSchedule.objects.filter(school_class__school=school)
        if allowed_class:
            schedules = schedules.filter(school_class=allowed_class)
        editing_schedule = schedules.filter(id=schedule_id).select_related('academic_event').first() if schedule_id else None

        if schedule_id and not editing_schedule:
            messages.error(request, 'That exam schedule is not managed under your allowed class.')
            return redirect('core:school_admin_exam_schedules')

        if action == 'delete':
            if not editing_schedule:
                messages.error(request, 'Select an exam schedule before deleting.')
                return redirect('core:school_admin_exam_schedules')
            event = editing_schedule.academic_event
            editing_schedule.delete()
            event.delete()
            messages.success(request, 'Exam schedule deleted successfully.')
            return redirect('core:school_admin_exam_schedules')

        form = SchoolExamScheduleForm(request.POST, school=school, allowed_class=allowed_class, instance=editing_schedule)
        if form.is_valid():
            school_class = form.cleaned_data['school_class']
            subject = form.cleaned_data['subject']
            exam_date = form.cleaned_data['exam_date']
            duration = timedelta(minutes=form.cleaned_data['duration_minutes'])
            academic_year = form.cleaned_data['academic_year']
            end_date = exam_date + duration

            event_was_new = editing_schedule is None
            event = editing_schedule.academic_event if editing_schedule else AcademicEvent(
                event_type='exam',
                created_by=request.user,
            )
            event.school = school
            event.title = f'{school_class} {subject} Exam'
            event.description = f'Exam schedule for {subject} in {school_class}.'
            event.start_date = exam_date
            event.end_date = end_date
            event.academic_year = academic_year
            event.is_recurring = False

            schedule = editing_schedule or ExamSchedule(academic_event=event)
            schedule.subject = subject
            schedule.school_class = school_class
            schedule.exam_date = exam_date
            schedule.duration = duration
            schedule.room = form.cleaned_data.get('room', '')
            schedule.invigilator = form.cleaned_data.get('invigilator')

            try:
                event.full_clean()
                event.save()
                schedule.academic_event = event
                schedule.full_clean()
                schedule.save()
                active_terms = Term.all_objects.filter(
                    school=school,
                    start_date__lte=exam_date.date(),
                    end_date__gte=exam_date.date(),
                )
                event.terms.set(active_terms)
                messages.success(request, 'Exam schedule saved successfully.')
                return redirect('core:school_admin_exam_schedules')
            except ValidationError as exc:
                if event_was_new and event.pk:
                    event.delete()
                form.add_error(None, exc)

    else:
        schedule_id = request.GET.get('schedule')
        if schedule_id:
            schedules = ExamSchedule.objects.filter(school_class__school=school)
            if allowed_class:
                schedules = schedules.filter(school_class=allowed_class)
            editing_schedule = schedules.filter(id=schedule_id).select_related('academic_event').first()
            if not editing_schedule:
                messages.error(request, 'That exam schedule is not managed under your allowed class.')
                return redirect('core:school_admin_exam_schedules')
            form = SchoolExamScheduleForm(school=school, allowed_class=allowed_class, instance=editing_schedule)

    schedules = ExamSchedule.objects.filter(
        school_class__school=school,
    ).select_related('subject', 'school_class', 'invigilator__user', 'academic_event').order_by('exam_date')
    if allowed_class:
        schedules = schedules.filter(school_class=allowed_class)

    return render(request, 'school_admin/exam_schedules.html', {
        'school': school,
        'form': form,
        'schedules': schedules,
        'editing_schedule': editing_schedule,
        'allowed_class': allowed_class,
    })


@login_required
def school_admin_learner_domains(request):
    if not _require_school_admin_or_class_teacher(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    LearnerDomainCriterion.ensure_defaults(school)

    is_school_admin_scope = _is_school_admin_user(request)
    class_teacher_assignments = ClassTeacher.objects.none()
    if not is_school_admin_scope:
        teacher = Teacher.all_objects.filter(user=request.user, school=school, status='active').first()
        class_teacher_assignments = _class_teacher_assignments_for_teacher(teacher, school)
    allowed_class = class_teacher_assignments.first().school_class if class_teacher_assignments.count() == 1 else None
    classes = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')
    if not is_school_admin_scope:
        classes = classes.filter(pk__in=class_teacher_assignments.values_list('school_class_id', flat=True))
    class_scope_available = _learner_domain_criterion_supports_class_scope()

    terms = Term.all_objects.filter(school=school).order_by('-start_date')
    selected_class_id = request.POST.get('school_class') or request.GET.get('school_class')
    selected_term_id = request.POST.get('term') or request.GET.get('term')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_ratings')
        selected_class_for_post = classes.filter(pk=selected_class_id).first() if selected_class_id else None
        if action == 'update_domain_rating_guide':
            if not _is_school_admin_user(request):
                messages.error(request, 'Only school admins can manage domain rating guides.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))
            if not selected_class_for_post:
                messages.error(request, 'Choose a class before updating its rating guide.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))

            settings = _school_report_card_settings(school)
            guide = _clean_domain_rating_guide_from_post(request)
            class_guides = dict(settings.class_domain_rating_guides or {})
            class_key = str(selected_class_for_post.id)
            if guide:
                class_guides[class_key] = guide
                message = f'Rating guide updated for {selected_class_for_post}.'
            else:
                class_guides.pop(class_key, None)
                message = f'{selected_class_for_post} now uses the default rating guide.'
            settings.school = school
            settings.class_domain_rating_guides = class_guides
            settings.save()
            messages.success(request, message)
            return redirect(_domain_redirect(selected_class_for_post.id, selected_term_id))

        if action in ['add_criterion', 'update_criterion', 'delete_criterion']:
            if not _is_school_admin_user(request):
                messages.error(request, 'Only school admins can manage domain criteria.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))

            if action == 'add_criterion':
                domain_type = request.POST.get('domain_type')
                name = request.POST.get('name', '').strip()
                if domain_type not in [LearnerDomainCriterion.DOMAIN_EFFECTIVE, LearnerDomainCriterion.DOMAIN_PSYCHOMOTOR]:
                    messages.error(request, 'Choose a valid domain type.')
                elif not name:
                    messages.error(request, 'Enter a criterion name.')
                else:
                    existing_criterion = _active_criterion_by_name(school, domain_type, name)
                    class_ids = _criterion_class_ids_from_post(request, school, selected_class_id)
                    if existing_criterion:
                        if _make_existing_criterion_available_for_scope(existing_criterion, class_ids):
                            messages.success(request, f'{existing_criterion.name} is now available for the selected class.')
                        else:
                            messages.error(request, f'{existing_criterion.name} already exists in this domain.')
                    else:
                        last_criterion = LearnerDomainCriterion.all_objects.filter(
                            school=school,
                            domain_type=domain_type,
                        ).order_by('-display_order').first()
                        display_order = (last_criterion.display_order + 10) if last_criterion else 10
                        criterion = LearnerDomainCriterion.all_objects.create(
                            school=school,
                            domain_type=domain_type,
                            name=name,
                            display_order=display_order,
                        )
                        if class_scope_available:
                            _set_criterion_classes_for_scope(criterion, class_ids)
                        messages.success(request, f'{name} added successfully.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))

            criterion = LearnerDomainCriterion.all_objects.filter(
                id=request.POST.get('criterion_id'),
                school=school,
            ).first()
            if not criterion:
                messages.error(request, 'That criterion is not managed under this school.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))

            if action == 'delete_criterion':
                criterion.is_active = False
                criterion.save(update_fields=['is_active'])
                messages.success(request, f'{criterion.name} removed successfully.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))

            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, 'Enter a criterion name.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))
            if _criterion_name_exists(school, criterion.domain_type, name, exclude_id=criterion.id):
                messages.error(request, f'{name} already exists in this domain.')
                return redirect(_domain_redirect(selected_class_id, selected_term_id))
            try:
                display_order = int(request.POST.get('display_order', criterion.display_order))
            except (TypeError, ValueError):
                display_order = criterion.display_order
            criterion.name = name
            criterion.display_order = max(0, display_order)
            criterion.save(update_fields=['name', 'display_order'])
            if class_scope_available:
                _set_criterion_classes_for_scope(
                    criterion,
                    _criterion_class_ids_from_post(request, school, selected_class_id),
                )
            messages.success(request, f'{criterion.name} updated successfully.')
            return redirect(_domain_redirect(selected_class_id, selected_term_id))

    selected_class = classes.filter(pk=selected_class_id).first() if selected_class_id else classes.first()
    selected_term = terms.filter(pk=selected_term_id).first() if selected_term_id else terms.filter(is_active=True).first() or terms.first()

    if not selected_class or not selected_term:
        messages.error(request, 'Add a class and term before managing learner domains.')
        return redirect('core:school_admin_dashboard' if _is_school_admin_user(request) else 'core:dashboard')

    students = students_for_term(
        school, selected_class, selected_term,
    ).select_related('user').order_by('user__first_name', 'user__last_name', 'student_id')

    criteria_queryset = _learner_domain_criteria_for_class(school, selected_class)
    if class_scope_available:
        criteria_queryset = criteria_queryset.prefetch_related('classes')
    criteria = list(criteria_queryset)
    _prepare_criterion_class_scope(criteria)
    effective_criteria = [
        criterion for criterion in criteria
        if criterion.domain_type == LearnerDomainCriterion.DOMAIN_EFFECTIVE
    ]
    psychomotor_criteria = [
        criterion for criterion in criteria
        if criterion.domain_type == LearnerDomainCriterion.DOMAIN_PSYCHOMOTOR
    ]
    report_card_settings = _school_report_card_settings(school)
    domain_rating_guide = report_card_settings.active_domain_rating_guide(selected_class)
    class_domain_rating_guides = report_card_settings.class_domain_rating_guides or {}
    class_domain_rating_guide_slots = list(domain_rating_guide)
    while len(class_domain_rating_guide_slots) < 5:
        class_domain_rating_guide_slots.append({'label': '', 'description': ''})
    domain_rating_labels = {
        item['label']
        for item in domain_rating_guide
        if item.get('label')
    }
    can_save_domain_ratings = (
        not is_school_admin_scope
        and bool(selected_class and selected_term)
        and not selected_term.result_published
    )

    if request.method == 'POST':
        if is_school_admin_scope:
            messages.error(request, 'Domain ratings are entered by class teachers. School admins manage the setup and rating guides.')
            return redirect(_domain_redirect(selected_class.id, selected_term.id))
        if selected_term.result_published:
            messages.error(request, 'Results for this term have been published. Ask the school admin to withdraw them before making adjustments.')
            return redirect(_domain_redirect(selected_class.id, selected_term.id))

        for student in students:
            legacy_effective = {field: '' for field in EFFECTIVE_LEGACY_FIELDS}
            legacy_psychomotor = {field: '' for field in PSYCHOMOTOR_LEGACY_FIELDS}

            for criterion in criteria:
                value = request.POST.get(f'rating_{student.id}_{criterion.id}')
                if value is None and criterion.legacy_field:
                    if criterion.domain_type == LearnerDomainCriterion.DOMAIN_EFFECTIVE:
                        value = request.POST.get(f'effective_{student.id}_{criterion.legacy_field}', '')
                    else:
                        value = request.POST.get(f'psychomotor_{student.id}_{criterion.legacy_field}', '')
                value = (value or '').strip()
                if domain_rating_labels and value not in domain_rating_labels:
                    value = ''

                if value:
                    LearnerDomainRating.all_objects.update_or_create(
                        school=school,
                        student=student,
                        term=selected_term,
                        criterion=criterion,
                        defaults={'value': value},
                    )
                else:
                    LearnerDomainRating.all_objects.filter(
                        student=student,
                        term=selected_term,
                        criterion=criterion,
                    ).delete()

                if criterion.domain_type == LearnerDomainCriterion.DOMAIN_EFFECTIVE and criterion.legacy_field in legacy_effective:
                    legacy_effective[criterion.legacy_field] = value
                if criterion.domain_type == LearnerDomainCriterion.DOMAIN_PSYCHOMOTOR and criterion.legacy_field in legacy_psychomotor:
                    legacy_psychomotor[criterion.legacy_field] = value

            EffectiveDomain.objects.update_or_create(
                student=student,
                term=selected_term,
                defaults=legacy_effective,
            )
            Psychomotor.objects.update_or_create(
                student=student,
                term=selected_term,
                defaults=legacy_psychomotor,
            )
        messages.success(request, 'Effective domain and psychomotor ratings saved successfully.')
        return redirect(_domain_redirect(selected_class.id, selected_term.id))

    effective_map = {
        item.student_id: item
        for item in EffectiveDomain.objects.filter(student__in=students, term=selected_term)
    }
    psychomotor_map = {
        item.student_id: item
        for item in Psychomotor.objects.filter(student__in=students, term=selected_term)
    }
    rating_map = {}
    for rating in LearnerDomainRating.all_objects.filter(
        student__in=students,
        term=selected_term,
        criterion__in=criteria,
    ).select_related('criterion'):
        rating_map.setdefault(rating.student_id, {})[rating.criterion_id] = rating.value

    for student in students:
        student_ratings = rating_map.setdefault(student.id, {})
        effective = effective_map.get(student.id)
        psychomotor = psychomotor_map.get(student.id)
        for criterion in criteria:
            if criterion.id in student_ratings or not criterion.legacy_field:
                continue
            if criterion.domain_type == LearnerDomainCriterion.DOMAIN_EFFECTIVE and effective:
                student_ratings[criterion.id] = getattr(effective, criterion.legacy_field, '')
            elif criterion.domain_type == LearnerDomainCriterion.DOMAIN_PSYCHOMOTOR and psychomotor:
                student_ratings[criterion.id] = getattr(psychomotor, criterion.legacy_field, '')

    return render(request, 'school_admin/learner_domains.html', {
        'school': school,
        'classes': classes,
        'terms': terms,
        'selected_class': selected_class,
        'selected_term': selected_term,
        'students': students,
        'effective_map': effective_map,
        'psychomotor_map': psychomotor_map,
        'rating_map': rating_map,
        'effective_criteria': effective_criteria,
        'psychomotor_criteria': psychomotor_criteria,
        'effective_colspan': max(1, len(effective_criteria)),
        'psychomotor_colspan': max(1, len(psychomotor_criteria)),
        'domain_column_count': 1 + max(1, len(effective_criteria)) + max(1, len(psychomotor_criteria)),
        'domain_rating_guide': domain_rating_guide,
        'class_domain_rating_guide_slots': class_domain_rating_guide_slots,
        'selected_class_has_domain_rating_override': str(selected_class.id) in class_domain_rating_guides,
        'scope_classes': SchoolClass.all_objects.filter(school=school).order_by('name', 'stream'),
        'allowed_class': allowed_class,
        'is_school_admin_scope': is_school_admin_scope,
        'can_save_domain_ratings': can_save_domain_ratings,
        'results_locked': bool(selected_term.result_published),
    })


@login_required
def school_admin_event_form(request, event_id=None):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    event = None
    if event_id:
        event = get_object_or_404(AcademicEvent.all_objects, id=event_id, school=school)

    form = AcademicEventForm(request.POST or None, instance=event)
    form.fields['terms'].queryset = Term.all_objects.filter(school=school).order_by('-start_date')

    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        event.school = school
        if not event.pk:
            event.created_by = request.user
        try:
            event.save()
            form.save_m2m()
            messages.success(request, 'Academic event saved successfully.')
            return redirect('academic:calendar')
        except IntegrityError:
            form.add_error(None, 'This academic event could not be saved.')

    return render(request, 'school_admin/form.html', {
        'school': school,
        'title': 'Academic Event',
        'form': form,
        'cancel_href': reverse('academic:calendar'),
    })


@login_required
def school_admin_holiday_form(request, holiday_id=None):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    holiday = None
    if holiday_id:
        holiday = get_object_or_404(Holiday.all_objects, id=holiday_id, school=school)

    form = HolidayForm(request.POST or None, instance=holiday)

    if request.method == 'POST' and form.is_valid():
        holiday = form.save(commit=False)
        holiday.school = school
        try:
            holiday.save()
            messages.success(request, 'Holiday saved successfully.')
            return redirect('academic:calendar')
        except IntegrityError:
            form.add_error(None, 'This holiday could not be saved because it already exists.')

    return render(request, 'school_admin/form.html', {
        'school': school,
        'title': 'Holiday',
        'form': form,
        'cancel_href': reverse('academic:calendar'),
    })
