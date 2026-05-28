from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms_academic import AcademicEventForm, HolidayForm
from .forms_school_admin import (
    SchoolBulkResultComponentForm,
    SchoolClassTeacherAssignmentForm,
    SchoolClassForm,
    SchoolExamScheduleForm,
    SchoolGradingSystemForm,
    SchoolHeadTeacherAssignmentForm,
    SchoolResultComponentForm,
    SchoolStudentForm,
    SchoolSubjectForm,
    SchoolTeacherForm,
    SchoolTermForm,
    SchoolUserForm,
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
    Psychomotor,
    Result,
    ResultComponent,
    SchoolClass,
    SchoolSettings,
    SchoolMembership,
    Student,
    Subject,
    Teacher,
    Term,
)
from .models_biodata import Guardian
from .tenant_permissions import grant_school_admin_permissions

User = get_user_model()


def _is_school_admin_user(request):
    if request.user.is_superuser:
        return True
    if getattr(request.user, 'has_role', None) and request.user.has_role('super_admin'):
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


def _get_class_teacher_assignment(user, school):
    if not school:
        return None
    try:
        teacher = Teacher.all_objects.get(user=user, school=school)
    except Teacher.DoesNotExist:
        return None
    return ClassTeacher.objects.filter(
        teacher=teacher,
        school_class__school=school,
    ).select_related('teacher__user', 'school_class').first()


def _require_school_admin_or_class_teacher(request):
    if _is_school_admin_user(request):
        return True
    school = getattr(request, 'school', None)
    if school and _get_class_teacher_assignment(request.user, school):
        return True
    messages.error(request, 'You do not have permission to access this class management page.')
    return False


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
        'total_students': Student.all_objects.filter(school=school).count(),
        'total_staff': Teacher.all_objects.filter(school=school).count(),
        'total_classes': SchoolClass.all_objects.filter(school=school).count(),
        'total_subjects': Subject.all_objects.filter(school=school).count(),
        'total_assessments': ResultComponent.objects.filter(school_class__school=school).count(),
    }
    return render(request, 'school_admin/dashboard.html', context)


@login_required
def school_admin_users(request):
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_user = None
    form = SchoolUserForm()

    if request.method == 'POST':
        form = SchoolUserForm(request.POST)
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
                password = form.cleaned_data.get('password')

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

                if password:
                    user.set_password(password)
                elif not user.pk:
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
                        },
                    )
                    grant_school_admin_permissions(user)
                    messages.success(request, f'{user.get_full_name() or user.username} saved successfully.')
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
                'is_active': membership.is_active,
            })
        elif edit_user_id:
            messages.error(request, 'That user is not managed under this school.')
            return redirect('core:school_admin_users')

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
            try:
                student.save()
                messages.success(request, 'Student profile saved successfully.')
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
            try:
                teacher.save()
                teacher_form.save_m2m()
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
    class_form = SchoolClassForm()
    subject_form = SchoolSubjectForm()
    term_form = SchoolTermForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        object_id = request.POST.get('object_id')

        if action == 'class':
            editing_class = SchoolClass.all_objects.filter(id=object_id, school=school).first() if object_id else None
            if object_id and not editing_class:
                messages.error(request, 'That class is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            class_form = SchoolClassForm(request.POST, instance=editing_class)
            if class_form.is_valid():
                school_class = class_form.save(commit=False)
                school_class.school = school
                try:
                    school_class.save()
                    messages.success(request, 'Class saved successfully.')
                    return redirect('core:school_admin_academic_setup')
                except IntegrityError:
                    class_form.add_error(None, 'This class could not be saved because it already exists.')

        elif action == 'subject':
            editing_subject = Subject.all_objects.filter(id=object_id, school=school).first() if object_id else None
            if object_id and not editing_subject:
                messages.error(request, 'That subject is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            subject_form = SchoolSubjectForm(request.POST, instance=editing_subject)
            if subject_form.is_valid():
                subject = subject_form.save(commit=False)
                subject.school = school
                try:
                    subject.save()
                    messages.success(request, 'Subject saved successfully.')
                    return redirect('core:school_admin_academic_setup')
                except IntegrityError:
                    subject_form.add_error(None, 'This subject could not be saved because it already exists.')

        elif action == 'term':
            editing_term = Term.all_objects.filter(id=object_id, school=school).first() if object_id else None
            if object_id and not editing_term:
                messages.error(request, 'That term is not managed under this school.')
                return redirect('core:school_admin_academic_setup')
            term_form = SchoolTermForm(request.POST, instance=editing_term)
            if term_form.is_valid():
                term = term_form.save(commit=False)
                term.school = school
                try:
                    term.save()
                    messages.success(request, 'Term saved successfully.')
                    return redirect('core:school_admin_academic_setup')
                except IntegrityError:
                    term_form.add_error(None, 'This term could not be saved because it already exists.')
    else:
        class_id = request.GET.get('class')
        subject_id = request.GET.get('subject')
        term_id = request.GET.get('term')
        if class_id:
            editing_class = get_object_or_404(SchoolClass.all_objects, id=class_id, school=school)
            class_form = SchoolClassForm(instance=editing_class)
        if subject_id:
            editing_subject = get_object_or_404(Subject.all_objects, id=subject_id, school=school)
            subject_form = SchoolSubjectForm(instance=editing_subject)
        if term_id:
            editing_term = get_object_or_404(Term.all_objects, id=term_id, school=school)
            term_form = SchoolTermForm(instance=editing_term)

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
    if not _require_school_admin(request):
        return redirect('core:dashboard')

    school = _active_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    editing_component = None
    form = SchoolResultComponentForm(school=school)
    bulk_form = SchoolBulkResultComponentForm(school=school)

    if request.method == 'POST':
        component_id = request.POST.get('component_id')
        action = request.POST.get('action', 'save')

        if action == 'bulk_save':
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
            editing_component = ResultComponent.objects.filter(
                id=component_id,
                school_class__school=school,
            ).first() if component_id else None

            if component_id and not editing_component:
                messages.error(request, 'That assessment component is not managed under this school.')
                return redirect('core:school_admin_assessments')

            if action == 'delete':
                if not editing_component:
                    messages.error(request, 'Select an assessment component before deleting.')
                    return redirect('core:school_admin_assessments')
                editing_component.delete()
                messages.success(request, 'Assessment component deleted successfully.')
                return redirect('core:school_admin_assessments')

            form = SchoolResultComponentForm(request.POST, instance=editing_component, school=school)
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
            editing_component = ResultComponent.objects.filter(
                id=component_id,
                school_class__school=school,
            ).first()
            if not editing_component:
                messages.error(request, 'That assessment component is not managed under this school.')
                return redirect('core:school_admin_assessments')
            form = SchoolResultComponentForm(instance=editing_component, school=school)

    components = ResultComponent.objects.filter(
        school_class__school=school,
    ).select_related('school_class', 'subject').order_by(
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
                school_class=school_class,
                defaults={
                    'teacher': teacher,
                    'can_assign_parent_wards': form.cleaned_data.get('can_assign_parent_wards', False),
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
            academic_year = form.cleaned_data.get('academic_year') or f'{exam_date.year}-{exam_date.year + 1}'
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

    class_teacher_assignment = None if _is_school_admin_user(request) else _get_class_teacher_assignment(request.user, school)
    allowed_class = class_teacher_assignment.school_class if class_teacher_assignment else None
    classes = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')
    if allowed_class:
        classes = classes.filter(pk=allowed_class.pk)

    terms = Term.all_objects.filter(school=school).order_by('-start_date')
    selected_class_id = request.POST.get('school_class') or request.GET.get('school_class')
    selected_term_id = request.POST.get('term') or request.GET.get('term')
    selected_class = classes.filter(pk=selected_class_id).first() if selected_class_id else classes.first()
    selected_term = terms.filter(pk=selected_term_id).first() if selected_term_id else terms.filter(is_active=True).first() or terms.first()

    if not selected_class or not selected_term:
        messages.error(request, 'Add a class and term before managing learner domains.')
        return redirect('core:dashboard')

    students = Student.all_objects.filter(
        school=school,
        school_class=selected_class,
    ).select_related('user').order_by('user__first_name', 'user__last_name', 'student_id')

    if request.method == 'POST':
        for student in students:
            EffectiveDomain.objects.update_or_create(
                student=student,
                term=selected_term,
                defaults={
                    'punctuality': request.POST.get(f'effective_{student.id}_punctuality', '').strip(),
                    'neatness': request.POST.get(f'effective_{student.id}_neatness', '').strip(),
                    'attentiveness': request.POST.get(f'effective_{student.id}_attentiveness', '').strip(),
                    'politeness': request.POST.get(f'effective_{student.id}_politeness', '').strip(),
                    'relationship_with_others': request.POST.get(f'effective_{student.id}_relationship_with_others', '').strip(),
                },
            )
            Psychomotor.objects.update_or_create(
                student=student,
                term=selected_term,
                defaults={
                    'sports_games': request.POST.get(f'psychomotor_{student.id}_sports_games', '').strip(),
                    'handwriting': request.POST.get(f'psychomotor_{student.id}_handwriting', '').strip(),
                    'drawing_painting': request.POST.get(f'psychomotor_{student.id}_drawing_painting', '').strip(),
                    'crafts': request.POST.get(f'psychomotor_{student.id}_crafts', '').strip(),
                    'music_drama': request.POST.get(f'psychomotor_{student.id}_music_drama', '').strip(),
                },
            )
        messages.success(request, 'Effective domain and psychomotor ratings saved successfully.')
        return redirect(f'{reverse("core:school_admin_learner_domains")}?school_class={selected_class.id}&term={selected_term.id}')

    effective_map = {
        item.student_id: item
        for item in EffectiveDomain.objects.filter(student__in=students, term=selected_term)
    }
    psychomotor_map = {
        item.student_id: item
        for item in Psychomotor.objects.filter(student__in=students, term=selected_term)
    }

    return render(request, 'school_admin/learner_domains.html', {
        'school': school,
        'classes': classes,
        'terms': terms,
        'selected_class': selected_class,
        'selected_term': selected_term,
        'students': students,
        'effective_map': effective_map,
        'psychomotor_map': psychomotor_map,
        'allowed_class': allowed_class,
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
