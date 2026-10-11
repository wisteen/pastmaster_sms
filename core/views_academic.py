"""
Views for Academic Management System
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET, require_POST
from datetime import timedelta
import json

from .models import (
    Curriculum, CurriculumInstallation, LearningObjective, SyllabusContent, LessonPlan, LessonNote, CurriculumCoverage,
    AcademicEvent, Holiday, ExamSchedule, TimeSlot, Timetable, RoomAssignment,
    Assignment, AssignmentSubmission, SubmissionFile,
    Subject, SchoolClass, Teacher, Student, Term, ClassTeacher
)
from .forms_academic import (
    CurriculumForm, CurriculumInstallerForm, LearningObjectiveForm, SyllabusContentForm, LessonPlanForm, LessonNoteForm,
    AcademicEventForm, HolidayForm, TimeSlotForm, TimetableForm,
    AssignmentForm, AssignmentSubmissionForm, SubmissionFileForm, AssignmentGradeForm,
    LearningObjectiveFormSet, SyllabusContentFormSet
)
from .decorators_features import feature_required
from .permissions import AcademicDataFilter, AcademicPermissionManager
from .services_academic import (
    CoverageTracker, CalendarManager, TimetableBuilder, 
    AssignmentTracker, ReportGenerator, ensure_learning_objective,
)
from .services_curriculum_installer import (
    ACADEMIC_YEAR as INSTALLER_ACADEMIC_YEAR,
    CurriculumInstallError,
    SOURCE_LINKS as INSTALLER_SOURCE_LINKS,
    install_curriculum_bundle,
)


CURRICULUM_UNDO_WINDOW = timedelta(hours=3)


def _purge_expired_curriculum_items(curriculum=None):
    cutoff = timezone.now() - CURRICULUM_UNDO_WINDOW
    for model in (LearningObjective, SyllabusContent):
        queryset = model.all_objects.filter(
            pending_deletion_at__isnull=False,
            pending_deletion_at__lte=cutoff,
        )
        if curriculum is not None:
            queryset = queryset.filter(curriculum=curriculum)
        queryset.delete()


def _can_edit_curriculum_record(user, curriculum):
    if user.has_role('super_admin'):
        return True
    return (
        user.has_role('subject_teacher')
        and getattr(user, 'teacher', None) is not None
        and curriculum.created_by_id == user.id
    )


def _can_install_curriculum(user, school):
    if not getattr(user, 'is_authenticated', False) or not school:
        return False
    if user.is_superuser or user.has_role('super_admin'):
        return True
    if not user.has_any_role(['subject_teacher', 'class_teacher']):
        return False
    return Teacher.all_objects.filter(user=user, school=school).exists()


# Curriculum Management Views

@login_required
@feature_required('academic_curriculum')
def curriculum_list(request):
    """List all curricula with filtering options"""

    if not AcademicPermissionManager.can_view_curriculum(request.user):
        messages.error(request, 'You do not have permission to view curricula.')
        return redirect('core:dashboard')

    _purge_expired_curriculum_items()
    curricula = Curriculum.objects.all().prefetch_related('subjects')

    if (
        not request.user.has_role('super_admin')
        and request.user.has_role('subject_teacher')
        and not request.user.has_role('class_teacher')
    ):
        teacher = getattr(request.user, 'teacher', None)
        if teacher:
            curricula = curricula.filter(
                Q(subjects__in=teacher.subjects.all()) | Q(created_by=request.user)
            ).distinct()
        else:
            curricula = curricula.none()
    
    # Search and filter
    search = request.GET.get('search')
    if search:
        curricula = curricula.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    
    academic_year = request.GET.get('academic_year')
    if academic_year:
        curricula = curricula.filter(academic_year=academic_year)
    
    subject_id = request.GET.get('subject')
    if subject_id:
        curricula = curricula.filter(subjects__id=subject_id)
    
    # Pagination
    paginator = Paginator(curricula, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'subjects': Subject.objects.all(),
        'academic_years': Curriculum.objects.values_list('academic_year', flat=True).distinct(),
        'search': search,
        'selected_academic_year': academic_year,
        'selected_subject': subject_id,
        'can_install_curriculum': _can_install_curriculum(request.user, getattr(request, 'school', None)),
    }
    
    return render(request, 'academic/curriculum_list.html', context)


@login_required
@feature_required('academic_curriculum')
def curriculum_installer(request):
    """Tenant-scoped installer for the bundled Federal and Lagos curricula."""

    school = getattr(request, 'school', None)
    if not _can_install_curriculum(request.user, school):
        messages.error(request, 'Only an assigned teacher or school administrator can install curricula.')
        return redirect('core:dashboard')

    form = CurriculumInstallerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            counts = install_curriculum_bundle(
                school=school,
                creator=request.user,
                provider=form.cleaned_data['provider'],
                levels=form.cleaned_data['levels'],
                include_calendar=form.cleaned_data['include_calendar'],
                activate_first_term=form.cleaned_data['activate_first_term'],
            )
        except CurriculumInstallError as exc:
            form.add_error(None, str(exc))
            messages.error(request, 'Nothing was installed. Review the issue shown below.')
        else:
            messages.success(
                request,
                'Curriculum installation completed: '
                f"{counts['curricula_created']} new and {counts['curricula_reused']} existing "
                'curricula were prepared. Existing school edits were preserved.',
            )
            return redirect('academic:curriculum_installer')

    installation_history = CurriculumInstallation.all_objects.filter(
        school=school,
    ).select_related('installed_by').order_by('-installed_at')[:10]
    return render(request, 'academic/curriculum_installer.html', {
        'form': form,
        'academic_year': INSTALLER_ACADEMIC_YEAR,
        'installation_history': installation_history,
        'source_links': INSTALLER_SOURCE_LINKS,
    })


@login_required
def curriculum_detail(request, curriculum_id):
    """View curriculum details with learning objectives and syllabus"""
    
    curriculum = get_object_or_404(Curriculum, id=curriculum_id)
    
    if not AcademicPermissionManager.can_view_curriculum(request.user, curriculum):
        messages.error(request, 'You do not have permission to view this curriculum.')
        return redirect('academic:curriculum_list')
    
    learning_objectives = curriculum.learning_objectives.all().order_by('subject', 'order')
    syllabus_contents = curriculum.syllabus_contents.all().order_by('subject', 'order')
    
    context = {
        'curriculum': curriculum,
        'learning_objectives': learning_objectives,
        'syllabus_contents': syllabus_contents,
    }
    
    return render(request, 'academic/curriculum_detail.html', context)


@login_required
def curriculum_create(request):
    """Create a new curriculum"""
    
    if not AcademicPermissionManager.can_create_curriculum(request.user):
        messages.error(request, 'You do not have permission to create curricula.')
        return redirect('academic:curriculum_list')
    
    if request.method == 'POST':
        form = CurriculumForm(request.POST, user=request.user)
        
        if form.is_valid():
            curriculum = form.save(commit=False)
            curriculum.created_by = request.user
            curriculum.save()
            form.save_m2m()  # Save many-to-many relationships
            
            messages.success(request, 'Curriculum created successfully. You can now add learning objectives and syllabus content.')
            return redirect('academic:curriculum_edit', curriculum_id=curriculum.id)
    else:
        form = CurriculumForm(user=request.user)
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'academic/curriculum_form.html', context)


@login_required
def curriculum_edit(request, curriculum_id):
    """Edit an existing curriculum"""
    
    curriculum = get_object_or_404(Curriculum, id=curriculum_id)
    
    if not _can_edit_curriculum_record(request.user, curriculum):
        messages.error(request, 'You do not have permission to edit this curriculum.')
        return redirect('academic:curriculum_detail', curriculum_id=curriculum.id)

    _purge_expired_curriculum_items(curriculum)

    if request.method == 'POST':
        form = CurriculumForm(request.POST, instance=curriculum, user=request.user)
        objective_formset = LearningObjectiveFormSet(request.POST, instance=curriculum, prefix='objectives')
        syllabus_formset = SyllabusContentFormSet(request.POST, instance=curriculum, prefix='syllabus')
        
        form_is_valid = form.is_valid()
        objectives_are_valid = objective_formset.is_valid()
        syllabus_is_valid = syllabus_formset.is_valid()

        if form_is_valid and objectives_are_valid and form.cleaned_data.get('is_published'):
            remaining_objectives = any(
                objective_form.cleaned_data
                and not objective_form.cleaned_data.get('DELETE')
                and (
                    objective_form.instance.pk
                    or objective_form.cleaned_data.get('title')
                )
                for objective_form in objective_formset.forms
            )
            if not remaining_objectives:
                form.add_error(
                    'is_published',
                    'A published curriculum must keep at least one learning objective.',
                )
                form_is_valid = False

        if form_is_valid and objectives_are_valid and syllabus_is_valid:
            curriculum = form.save()
            objective_formset.save()
            syllabus_formset.save()
            
            messages.success(request, 'Curriculum updated successfully.')
            return redirect('academic:curriculum_detail', curriculum_id=curriculum.id)

        messages.error(
            request,
            'We could not update the curriculum. Review the highlighted fields.',
        )
    else:
        form = CurriculumForm(instance=curriculum, user=request.user)
        objective_formset = LearningObjectiveFormSet(instance=curriculum, prefix='objectives')
        syllabus_formset = SyllabusContentFormSet(instance=curriculum, prefix='syllabus')
    
    context = {
        'form': form,
        'objective_formset': objective_formset,
        'syllabus_formset': syllabus_formset,
        'curriculum': curriculum,
        'action': 'Update',
        'recently_removed_objectives': LearningObjective.all_objects.filter(
            curriculum=curriculum,
            pending_deletion_at__isnull=False,
        ).order_by('-pending_deletion_at'),
        'recently_removed_syllabus': SyllabusContent.all_objects.filter(
            curriculum=curriculum,
            pending_deletion_at__isnull=False,
        ).select_related('subject').order_by('-pending_deletion_at'),
        'undo_window_hours': 3,
    }
    
    return render(request, 'academic/curriculum_form.html', context)


@login_required
@require_POST
def curriculum_item_restore(request, item_type, item_id):
    model = {
        'objective': LearningObjective,
        'syllabus': SyllabusContent,
    }.get(item_type)
    if model is None:
        return JsonResponse({'error': 'Unknown curriculum item type.'}, status=400)

    item = get_object_or_404(
        model.all_objects.select_related('curriculum'),
        pk=item_id,
        pending_deletion_at__isnull=False,
    )
    curriculum = item.curriculum
    if not _can_edit_curriculum_record(request.user, curriculum):
        messages.error(request, 'You do not have permission to restore this item.')
        return redirect('academic:curriculum_detail', curriculum_id=curriculum.id)

    if item.pending_deletion_at <= timezone.now() - CURRICULUM_UNDO_WINDOW:
        model.all_objects.filter(pk=item.pk).delete()
        messages.error(request, 'The three-hour undo window has expired.')
    else:
        item.restore()
        messages.success(request, 'Curriculum item restored successfully.')
    return redirect('academic:curriculum_edit', curriculum_id=curriculum.id)


@login_required
def curriculum_delete(request, curriculum_id):
    curriculum = get_object_or_404(Curriculum, id=curriculum_id)
    if not request.user.has_role('super_admin'):
        messages.error(request, 'Only school administrators can delete curricula.')
        return redirect('academic:curriculum_detail', curriculum_id=curriculum.id)

    linked_lesson_plans = LessonPlan.objects.filter(curriculum=curriculum).count()
    linked_lesson_notes = LessonNote.objects.filter(curriculum=curriculum).count()
    linked_coverage = CurriculumCoverage.objects.filter(curriculum=curriculum).count()
    protected_count = linked_lesson_plans + linked_lesson_notes + linked_coverage

    if request.method == 'POST':
        if protected_count:
            messages.error(
                request,
                'This curriculum is in use. Reassign its teaching records before deleting it.',
            )
            return redirect('academic:curriculum_detail', curriculum_id=curriculum.id)

        title = curriculum.title
        Curriculum.all_objects.filter(
            pk=curriculum.pk,
            school_id=curriculum.school_id,
        ).delete()
        messages.success(request, f'Curriculum "{title}" deleted successfully.')
        return redirect('academic:curriculum_list')

    return render(request, 'academic/curriculum_confirm_delete.html', {
        'curriculum': curriculum,
        'objective_count': curriculum.learning_objectives.count(),
        'syllabus_count': curriculum.syllabus_contents.count(),
        'linked_lesson_plans': linked_lesson_plans,
        'linked_lesson_notes': linked_lesson_notes,
        'linked_coverage': linked_coverage,
        'can_delete': protected_count == 0,
    })


# Lesson Planning Views

@login_required
@feature_required('academic_lesson_plans')
def lesson_plan_list(request):
    """List lesson plans available to teachers or the school administrator."""

    is_school_admin = request.user.has_role('super_admin')
    is_teacher = request.user.has_any_role(['subject_teacher', 'class_teacher'])
    if not is_school_admin and not is_teacher:
        messages.error(request, 'Only teachers and school administrators can access lesson plans.')
        return redirect('core:dashboard')

    teacher = getattr(request.user, 'teacher', None) if is_teacher else None
    if is_teacher and teacher is None and not is_school_admin:
        messages.error(request, 'Your account is not linked to a teacher record.')
        return redirect('core:dashboard')

    lesson_plans = LessonPlan.objects.all().select_related(
        'curriculum', 'subject', 'school_class'
    ).order_by('-created_at')
    if not is_school_admin:
        lesson_plans = AcademicDataFilter.filter_lesson_plans(request.user, lesson_plans)
    
    # Filter options
    curriculum_id = request.GET.get('curriculum')
    if curriculum_id == 'none':
        lesson_plans = lesson_plans.filter(curriculum__isnull=True)
    elif curriculum_id:
        lesson_plans = lesson_plans.filter(curriculum_id=curriculum_id)
    
    subject_id = request.GET.get('subject')
    if subject_id:
        lesson_plans = lesson_plans.filter(subject_id=subject_id)
    
    class_id = request.GET.get('class')
    if class_id:
        lesson_plans = lesson_plans.filter(school_class_id=class_id)
    
    is_completed = request.GET.get('completed')
    if is_completed == 'true':
        lesson_plans = lesson_plans.filter(is_completed=True)
    elif is_completed == 'false':
        lesson_plans = lesson_plans.filter(is_completed=False)
    
    # Pagination
    paginator = Paginator(lesson_plans, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    filter_query = request.GET.copy()
    filter_query.pop('page', None)
    
    if is_school_admin:
        curricula = Curriculum.objects.filter(is_published=True)
        subjects = Subject.objects.all()
        classes = SchoolClass.objects.all()
    else:
        curricula = Curriculum.objects.filter(
            subjects__in=teacher.subjects.all(), is_published=True
        ).distinct()
        subjects = teacher.subjects.all()
        classes = teacher.classes.all()

    context = {
        'page_obj': page_obj,
        'teacher': teacher,
        'curricula': curricula,
        'subjects': subjects,
        'classes': classes,
        'is_school_admin': is_school_admin,
        'can_create_lesson_plan': bool(teacher),
        'filter_query': filter_query.urlencode(),
    }
    
    return render(request, 'academic/lesson_plan_list.html', context)


@login_required
def lesson_plan_create(request):
    """Create a new lesson plan"""
    
    if not AcademicPermissionManager.can_create_lesson_plan(request.user):
        messages.error(request, 'Only teachers can create lesson plans.')
        return redirect('core:dashboard')
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    if request.method == 'POST':
        form = LessonPlanForm(request.POST, user=request.user)
        
        if form.is_valid():
            lesson_plan = form.save(commit=False)
            lesson_plan.teacher = teacher
            lesson_plan.save()
            form.save_m2m()  # Save learning objectives
            
            messages.success(request, 'Lesson plan created successfully.')
            return redirect('academic:lesson_plan_detail', lesson_plan_id=lesson_plan.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LessonPlanForm(user=request.user)
    
    context = {
        'form': form,
        'teacher': teacher,
        'action': 'Create',
    }
    
    return render(request, 'academic/lesson_plan_form.html', context)


@login_required
def lesson_plan_detail(request, lesson_plan_id):
    """View lesson plan details"""
    
    lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id)
    
    if not AcademicPermissionManager.can_view_lesson_plan(request.user, lesson_plan):
        messages.error(request, 'You do not have permission to view this lesson plan.')
        return redirect('academic:lesson_plan_list')
    
    context = {
        'lesson_plan': lesson_plan,
        'can_manage_plan': AcademicPermissionManager.can_edit_lesson_plan(
            request.user, lesson_plan
        ),
        'can_create_lesson_note': (
            getattr(request.user, 'teacher', None) == lesson_plan.teacher
        ),
    }
    
    return render(request, 'academic/lesson_plan_detail.html', context)


@login_required
def lesson_plan_edit(request, lesson_plan_id):
    """Edit an existing lesson plan"""
    
    lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id)
    
    if not AcademicPermissionManager.can_edit_lesson_plan(request.user, lesson_plan):
        messages.error(request, 'Only teachers can edit lesson plans.')
        return redirect('academic:lesson_plan_detail', lesson_plan_id=lesson_plan.id)

    teacher = getattr(request.user, 'teacher', None) or lesson_plan.teacher
    
    if request.method == 'POST':
        form = LessonPlanForm(request.POST, instance=lesson_plan, user=request.user)
        
        if form.is_valid():
            form.save()
            
            messages.success(request, 'Lesson plan updated successfully.')
            return redirect('academic:lesson_plan_detail', lesson_plan_id=lesson_plan.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LessonPlanForm(instance=lesson_plan, user=request.user)
    
    context = {
        'form': form,
        'lesson_plan': lesson_plan,
        'teacher': teacher,
        'action': 'Edit',
    }
    
    return render(request, 'academic/lesson_plan_form.html', context)


@login_required
def lesson_plan_delete(request, lesson_plan_id):
    lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id)
    if not AcademicPermissionManager.can_edit_lesson_plan(request.user, lesson_plan):
        messages.error(request, 'You do not have permission to delete this lesson plan.')
        return redirect('academic:lesson_plan_list')

    note_count = lesson_plan.lesson_notes.count()
    if request.method == 'POST':
        lesson_plan.lesson_notes.all().delete()
        lesson_plan.delete()
        messages.success(request, 'Lesson plan deleted successfully.')
        return redirect('academic:lesson_plan_list')

    return render(request, 'academic/lesson_plan_confirm_delete.html', {
        'lesson_plan': lesson_plan,
        'note_count': note_count,
    })


@login_required
def toggle_lesson_completion(request, lesson_plan_id):
    """Toggle lesson plan completion status"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id)
    
    if not AcademicPermissionManager.can_edit_lesson_plan(request.user, lesson_plan):
        return JsonResponse(
            {'success': False, 'message': 'Permission denied'},
            status=403,
        )
    
    # Toggle completion
    lesson_plan.is_completed = not lesson_plan.is_completed
    lesson_plan.save()
    
    return JsonResponse({
        'success': True,
        'is_completed': lesson_plan.is_completed,
        'completion_date': lesson_plan.completion_date.isoformat() if lesson_plan.completion_date else None
    })


# Coverage Tracking Views

@login_required
def coverage_report(request):
    """View curriculum coverage reports"""
    
    if not request.user.has_any_role(['subject_teacher', 'class_teacher', 'super_admin']):
        messages.error(request, 'You do not have permission to view coverage reports.')
        return redirect('core:dashboard')
    
    curriculum_id = request.GET.get('curriculum')
    class_id = request.GET.get('class')
    
    if curriculum_id and class_id:
        curriculum = get_object_or_404(Curriculum, id=curriculum_id)
        school_class = get_object_or_404(SchoolClass, id=class_id)
        
        # Check permissions
        if request.user.has_role('subject_teacher'):
            teacher = getattr(request.user, 'teacher', None)
            if teacher:
                if not curriculum.subjects.filter(id__in=teacher.subjects.all()).exists():
                    messages.error(request, 'You do not have permission to view this curriculum.')
                    return redirect('academic:coverage_report')
                if school_class not in teacher.classes.all():
                    messages.error(request, 'You do not have permission to view this class.')
                    return redirect('academic:coverage_report')
        
        report_data = ReportGenerator.generate_curriculum_coverage_report(curriculum, school_class)
        
        context = {
            'report_data': report_data['statistics'],
            'coverage_by_objective': report_data['coverage_data'],
            'objectives_by_subject': report_data['objectives_by_subject'],
            'curriculum': curriculum,
            'school_class': school_class,
            'completed_objectives': report_data['statistics']['completed_objectives'],
            'at_risk_objectives': report_data['statistics']['at_risk_objectives'],
            'total_objectives': report_data['statistics']['total_objectives'],
            'overall_coverage': report_data['statistics']['overall_completion_percentage'],
        }
        
        return render(request, 'academic/coverage_report_detail.html', context)
    
    # Show selection form
    curricula = Curriculum.objects.filter(is_published=True)
    classes = SchoolClass.objects.all()
    
    if request.user.has_role('subject_teacher'):
        teacher = getattr(request.user, 'teacher', None)
        if teacher:
            curricula = curricula.filter(subjects__in=teacher.subjects.all()).distinct()
            classes = teacher.classes.all()
    
    context = {
        'curricula': curricula,
        'classes': classes,
    }
    
    return render(request, 'academic/coverage_report.html', context)


# Assignment Management Views

@login_required
@feature_required('academic_assignments')
def assignment_list(request):
    """List assignments based on user role"""
    
    if request.user.has_role('student'):
        return student_assignment_list(request)
    elif request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return teacher_assignment_list(request)
    else:
        messages.error(request, 'You do not have permission to view assignments.')
        return redirect('core:dashboard')


def student_assignment_list(request):
    """List assignments for students"""
    
    student = get_object_or_404(Student, user=request.user)
    assignment_info = AssignmentTracker.get_student_assignments(student, include_completed=True)
    
    # Filter by status
    status = request.GET.get('status')
    if status == 'pending':
        assignment_info = [info for info in assignment_info if not info['is_submitted']]
    elif status == 'submitted':
        assignment_info = [info for info in assignment_info if info['is_submitted']]
    elif status == 'overdue':
        assignment_info = [info for info in assignment_info if info['is_overdue']]
    
    context = {
        'assignment_info': assignment_info,
        'student': student,
        'status_filter': status,
    }
    
    return render(request, 'academic/student_assignment_list.html', context)


def teacher_assignment_list(request):
    """List assignments for teachers"""
    
    teacher = get_object_or_404(Teacher, user=request.user)
    assignments = Assignment.objects.filter(teacher=teacher).order_by('-created_at')
    
    # Add submission statistics
    assignment_data = []
    for assignment in assignments:
        stats = AssignmentTracker.get_submission_statistics(assignment)
        assignment_data.append({
            'assignment': assignment,
            'stats': stats
        })
    
    context = {
        'assignment_data': assignment_data,
        'teacher': teacher,
    }
    
    return render(request, 'academic/teacher_assignment_list.html', context)


@login_required
@feature_required('academic_assignments')
@transaction.atomic
def assignment_create(request):
    """Create a new assignment"""
    
    if not AcademicPermissionManager.can_create_assignment(request.user):
        messages.error(request, 'Only teachers can create assignments.')
        return redirect('core:dashboard')
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.teacher = teacher
            assignment.save()
            form.save_m2m()  # Save school classes
            
            messages.success(request, 'Assignment created successfully.')
            return redirect('academic:assignment_detail', assignment_id=assignment.id)
    else:
        form = AssignmentForm(user=request.user)
    
    context = {
        'form': form,
        'teacher': teacher,
        'action': 'Create',
    }
    
    return render(request, 'academic/assignment_form.html', context)


@login_required
@feature_required('academic_assignments')
@transaction.atomic
def assignment_edit(request, assignment_id):
    """Edit an existing assignment"""
    
    assignment = get_object_or_404(Assignment.objects.select_for_update(), id=assignment_id)
    
    if not AcademicPermissionManager.can_edit_assignment(request.user, assignment):
        messages.error(request, 'Only teachers can edit assignments.')
        return redirect('core:dashboard')
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    if assignment.teacher != teacher and not request.user.has_role('super_admin'):
        messages.error(request, 'You can only edit your own assignments.')
        return redirect('academic:assignment_detail', assignment_id=assignment.id)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES, instance=assignment, user=request.user)
        
        if form.is_valid():
            form.save()
            
            messages.success(request, 'Assignment updated successfully.')
            return redirect('academic:assignment_detail', assignment_id=assignment.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AssignmentForm(instance=assignment, user=request.user)
    
    context = {
        'form': form,
        'assignment': assignment,
        'teacher': teacher,
        'action': 'Edit',
    }
    
    return render(request, 'academic/assignment_form.html', context)


@login_required
@feature_required('academic_assignments')
def assignment_detail(request, assignment_id):
    """View assignment details"""
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Check permissions and get appropriate context
    if request.user.has_role('student'):
        student = get_object_or_404(Student, user=request.user)
        
        # Check if student is in assigned classes
        if student.school_class not in assignment.school_classes.all():
            messages.error(request, 'You are not assigned to this assignment.')
            return redirect('academic:assignment_list')
        
        # Get submission if exists
        try:
            submission = AssignmentSubmission.objects.get(assignment=assignment, student=student)
        except AssignmentSubmission.DoesNotExist:
            submission = None
        
        context = {
            'assignment': assignment,
            'submission': submission,
            'student': student,
            'can_submit': (not submission or not submission.is_graded) and (not assignment.is_overdue() or assignment.allow_late_submission),
        }
        
        return render(request, 'academic/student_assignment_detail.html', context)
    
    elif request.user.has_any_role(['subject_teacher', 'class_teacher']):
        teacher = get_object_or_404(Teacher, user=request.user, status='active')
        if assignment.teacher != teacher:
            messages.error(request, 'You can only view your own assignments.')
            return redirect('academic:assignment_list')
        
        stats = AssignmentTracker.get_submission_statistics(assignment)
        submissions = AssignmentSubmission.objects.filter(assignment=assignment).select_related('student__user')
        
        context = {
            'assignment': assignment,
            'stats': stats,
            'submissions': submissions,
            'teacher': teacher,
        }
        
        return render(request, 'academic/teacher_assignment_detail.html', context)
    
    else:
        messages.error(request, 'You do not have permission to view this assignment.')
        return redirect('core:dashboard')


@login_required
@feature_required('academic_assignments')
@transaction.atomic
def submit_assignment(request, assignment_id):
    """Submit an assignment (for students)"""
    
    if not request.user.has_role('student'):
        messages.error(request, 'Only students can submit assignments.')
        return redirect('core:dashboard')
    
    assignment = get_object_or_404(Assignment.objects.select_for_update(), id=assignment_id)
    student = get_object_or_404(Student, user=request.user, status='active')
    
    # Check if student is in assigned classes
    if student.school_class not in assignment.school_classes.all():
        messages.error(request, 'You are not assigned to this assignment.')
        return redirect('academic:assignment_list')
    
    # Check if assignment is overdue and late submissions not allowed
    if assignment.is_overdue() and not assignment.allow_late_submission:
        messages.error(request, 'This assignment is overdue and late submissions are not allowed.')
        return redirect('academic:assignment_detail', assignment_id=assignment.id)
    
    # Check if already submitted and graded
    existing_submission = AssignmentSubmission.objects.select_for_update().filter(
        assignment=assignment, student=student
    ).first()
    
    if existing_submission and existing_submission.is_graded:
        messages.error(request, 'This assignment has been graded. You cannot edit your submission.')
        return redirect('academic:assignment_detail', assignment_id=assignment.id)
    
    file_form = SubmissionFileForm(request.POST if request.method == 'POST' else None, request.FILES or None)
    if request.method == 'POST':
        form = AssignmentSubmissionForm(request.POST, assignment=assignment, instance=existing_submission)
        form_valid, file_valid = form.is_valid(), file_form.is_valid()
        if form_valid and file_valid:
            from .forms_quiz import content_present
            has_text = content_present(form.cleaned_data.get('submission_text', ''))
            has_file = file_form.cleaned_data.get('file')
            retained_files = existing_submission and existing_submission.files.exists()
            
            if not has_text and not has_file and not retained_files:
                form.add_error(None, 'Please provide either a text response or upload a file.')
            else:
                submission = form.save(commit=False)
                if not existing_submission:
                    submission.assignment = assignment
                    submission.student = student
                submission.is_late = assignment.is_overdue()
                submission.save()
                
                # Handle file uploads
                if has_file:
                    SubmissionFile.objects.create(
                        submission=submission,
                        file=has_file,
                        original_filename=has_file.name
                    )
                
                messages.success(request, 'Assignment submitted successfully.')
                return redirect('academic:assignment_detail', assignment_id=assignment.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AssignmentSubmissionForm(assignment=assignment, instance=existing_submission)
    
    context = {
        'assignment': assignment,
        'form': form,
        'file_form': file_form,
        'existing_submission': existing_submission,
        'student': student,
    }
    
    return render(request, 'academic/submit_assignment.html', context)


# Academic Calendar Views

@login_required
def academic_calendar(request):
    """View academic calendar"""
    
    # Get current academic year or from request
    current_year = timezone.now().year
    academic_year = request.GET.get('year', f"{current_year}-{current_year + 1}")
    
    # Get events for the academic year
    events = AcademicEvent.objects.filter(academic_year=academic_year).order_by('start_date')
    holidays = Holiday.objects.filter(academic_year=academic_year).order_by('date')
    
    # Filter by user role
    if request.user.has_role('student'):
        student = getattr(request.user, 'student', None)
        if student:
            # Show events relevant to student's class
            events = events.filter(
                Q(terms__in=Term.objects.filter(is_active=True)) |
                Q(event_type='holiday')
            )
    
    context = {
        'events': events,
        'holidays': holidays,
        'academic_year': academic_year,
        'available_years': AcademicEvent.objects.values_list('academic_year', flat=True).distinct(),
    }
    
    return render(request, 'academic/calendar.html', context)


# AJAX Views

@login_required
@require_GET
def get_learning_objectives(request):
    """Get learning objectives for a curriculum and subject (AJAX)"""
    
    curriculum_id = request.GET.get('curriculum_id')
    subject_id = request.GET.get('subject_id')
    
    if curriculum_id and subject_id:
        curriculum = get_object_or_404(Curriculum, id=curriculum_id)
        if not AcademicPermissionManager.can_view_curriculum(request.user, curriculum):
            return JsonResponse({'error': 'Permission denied.'}, status=403)
        objectives = curriculum.learning_objectives.filter(
            subject_id=subject_id
        ).values('id', 'title', 'description')
        return JsonResponse({'objectives': list(objectives)})
    
    return JsonResponse({'objectives': []})


def _can_manage_learning_objectives(user, curriculum, subject):
    if user.has_role('super_admin'):
        return True, None
    if user.has_role('subject_teacher'):
        teacher = getattr(user, 'teacher', None)
        if not teacher:
            return False, 'A teacher profile is required.'
        if not teacher.subjects.filter(pk=subject.pk).exists():
            return False, 'You can only add objectives for subjects you teach.'
        if not curriculum.subjects.filter(pk=subject.pk).exists():
            return False, 'That subject is not part of the selected curriculum.'
        return True, None
    return False, 'You do not have permission to create learning objectives.'


@login_required
@require_POST
def create_learning_objective(request):
    title = (request.POST.get('title') or '').strip()
    curriculum_id = request.POST.get('curriculum_id')
    subject_id = request.POST.get('subject_id')
    grade_level = (request.POST.get('grade_level') or '').strip()

    if not title:
        return JsonResponse({'error': 'Enter a behavioural/learning objective.'}, status=400)
    if not curriculum_id or not subject_id:
        return JsonResponse(
            {'error': 'Select a curriculum and subject first.'},
            status=400,
        )

    curriculum = get_object_or_404(Curriculum, id=curriculum_id)
    subject = get_object_or_404(Subject, id=subject_id)
    allowed, error = _can_manage_learning_objectives(
        request.user, curriculum, subject
    )
    if not allowed:
        return JsonResponse({'error': error}, status=403)

    objective, created = ensure_learning_objective(
        curriculum,
        subject,
        title,
        grade_level=grade_level,
    )
    return JsonResponse({
        'id': objective.id,
        'title': objective.title,
        'description': objective.description,
        'created': created,
    })


@login_required
@require_GET
def lesson_plan_context(request, lesson_plan_id):
    lesson_plan = get_object_or_404(
        LessonPlan.objects.select_related(
            'curriculum', 'subject', 'school_class', 'teacher__user'
        ).prefetch_related('learning_objectives'),
        id=lesson_plan_id,
    )
    if not AcademicPermissionManager.can_view_lesson_plan(request.user, lesson_plan):
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    return JsonResponse({
        'id': lesson_plan.id,
        'curriculum': lesson_plan.curriculum.title if lesson_plan.curriculum else '',
        'curriculum_id': lesson_plan.curriculum_id,
        'topic': lesson_plan.title,
        'subject': lesson_plan.subject.name,
        'school_class': str(lesson_plan.school_class),
        'week_number': lesson_plan.week_number,
        'average_age': lesson_plan.average_age,
        'previous_knowledge': lesson_plan.previous_knowledge,
        'behavioural_objectives': [
            {'title': objective.title, 'description': objective.description}
            for objective in lesson_plan.learning_objectives.all()
        ],
        'reference_book': lesson_plan.reference_book,
        'resources': lesson_plan.resources,
        'estimated_duration_minutes': lesson_plan.estimated_duration_minutes,
    })


@login_required
def student_curriculum_view(request):
    """View curriculum for students"""
    
    if not request.user.has_role('student'):
        messages.error(request, 'Only students can access this page.')
        return redirect('core:dashboard')
    
    student = get_object_or_404(Student, user=request.user)
    
    # Get published curricula
    curricula = Curriculum.objects.filter(
        is_published=True
    ).distinct().prefetch_related('subjects', 'learning_objectives')
    
    context = {
        'curricula': curricula,
        'student': student,
    }
    
    return render(request, 'academic/student_curriculum_list.html', context)


@login_required
def student_lesson_plans_view(request):
    """View lesson plans for students"""
    
    if not request.user.has_role('student'):
        messages.error(request, 'Only students can access this page.')
        return redirect('core:dashboard')
    
    student = get_object_or_404(Student, user=request.user)
    
    # Get lesson plans for student's class
    lesson_plans = LessonPlan.objects.filter(
        school_class=student.school_class
    ).select_related('curriculum', 'subject', 'teacher').order_by('-created_at')
    
    context = {
        'lesson_plans': lesson_plans,
        'student': student,
    }
    
    return render(request, 'academic/student_lesson_plans.html', context)


@login_required
def student_lesson_notes_view(request):
    if not request.user.has_role('student'):
        messages.error(request, 'Only students can access this page.')
        return redirect('core:dashboard')

    student = get_object_or_404(Student, user=request.user)
    lesson_notes = LessonNote.objects.filter(
        lesson_plan__school_class=student.school_class
    ).select_related(
        'lesson_plan', 'lesson_plan__subject', 'lesson_plan__school_class',
        'teacher', 'teacher__user', 'curriculum',
    ).order_by('-date_taught')

    return render(request, 'academic/student_lesson_notes.html', {
        'lesson_notes': lesson_notes,
        'student': student,
    })


@login_required
@feature_required('academic_assignments')
@transaction.atomic
def grade_submission(request, submission_id):
    """Grade a student submission"""
    
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        messages.error(request, 'Only teachers can grade submissions.')
        return redirect('core:dashboard')
    
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)
    teacher = get_object_or_404(Teacher, user=request.user, status='active')
    
    if submission.assignment.teacher != teacher:
        messages.error(request, 'You can only grade submissions for your own assignments.')
        return redirect('academic:assignment_list')
    
    assignment = Assignment.objects.select_for_update().get(pk=submission.assignment_id)
    submission = AssignmentSubmission.objects.select_for_update().get(pk=submission.pk)
    form = AssignmentGradeForm(
        request.POST if request.method == 'POST' else None,
        assignment=assignment,
        initial={'score': submission.raw_score if submission.raw_score is not None else submission.score, 'feedback': submission.feedback},
    )
    if request.method == 'POST' and form.is_valid():
        submission.raw_score = form.cleaned_data['score']
        submission.score = submission.raw_score
        if submission.is_late and submission.score is not None:
            submission.score = (submission.raw_score * (Decimal('100') - assignment.late_penalty_percentage) / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        submission.feedback = form.cleaned_data['feedback']
        submission.graded_at = timezone.now()
        submission.save()
        
        messages.success(request, 'Submission graded successfully.')
        return redirect('academic:assignment_detail', assignment_id=submission.assignment.id)
    
    context = {
        'submission': submission,
        'form': form,
    }
    
    return render(request, 'academic/grade_submission.html', context)


# Timetable Management Views

@login_required
def timetable_list(request):
    """List timetables for teachers to manage"""
    
    if not request.user.has_any_role(['subject_teacher', 'class_teacher', 'super_admin']):
        messages.error(request, 'You do not have permission to manage timetables.')
        return redirect('core:dashboard')
    
    # Get current active term
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found. Please set an active term first.')
        return redirect('core:dashboard')
    
    # Filter timetables based on user role
    timetables = Timetable.objects.filter(term=active_term, is_active=True).select_related(
        'time_slot', 'subject', 'teacher', 'school_class', 'room'
    ).order_by('school_class__name', 'time_slot__day_of_week', 'time_slot__start_time')
    
    if request.user.has_role('subject_teacher'):
        teacher = getattr(request.user, 'teacher', None)
        if teacher:
            timetables = timetables.filter(teacher=teacher)
    
    # Group timetables by class
    timetables_by_class = {}
    for timetable in timetables:
        class_name = str(timetable.school_class)
        if class_name not in timetables_by_class:
            timetables_by_class[class_name] = []
        timetables_by_class[class_name].append(timetable)
    
    context = {
        'timetables_by_class': timetables_by_class,
        'active_term': active_term,
        'can_create': can_manage_timetable(request.user),
    }
    
    return render(request, 'academic/timetable_list.html', context)


def can_manage_timetable(user):
    """Check if user can manage timetables"""
    if user.has_any_role(['super_admin']):
        return True
    if user.has_role('class_teacher'):
        return True
    if user.has_role('subject_teacher'):
        try:
            teacher = getattr(user, 'teacher', None)
            return teacher and ClassTeacher.objects.filter(teacher=teacher).exists()
        except:
            return False
    return False


@login_required
def timetable_create(request):
    """Create timetable entries for a class"""
    
    if not can_manage_timetable(request.user):
        messages.error(request, 'Only class teachers and admins can create timetables.')
        return redirect('academic:timetable_list')
    
    # Get current active term
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found. Please set an active term first.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        time_slot_id = request.POST.get('time_slot')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')
        class_id = request.POST.get('school_class')
        room_id = request.POST.get('room')
        
        # Validate required fields
        if not all([time_slot_id, subject_id, teacher_id, class_id, room_id]):
            messages.error(request, 'All fields are required.')
        else:
            try:
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                subject = Subject.objects.get(id=subject_id)
                teacher = Teacher.objects.get(id=teacher_id)
                school_class = SchoolClass.objects.get(id=class_id)
                room = RoomAssignment.objects.get(id=room_id)
                
                # Check for conflicts
                conflicts = Timetable.objects.filter(
                    time_slot=time_slot,
                    term=active_term,
                    is_active=True
                ).filter(
                    Q(teacher=teacher) | Q(room=room) | Q(school_class=school_class)
                )
                
                if conflicts.exists():
                    conflict = conflicts.first()
                    if conflict.teacher == teacher:
                        messages.error(request, f'Teacher {teacher} is already assigned during {time_slot}.')
                    elif conflict.room == room:
                        messages.error(request, f'Room {room.room_name} is already booked during {time_slot}.')
                    elif conflict.school_class == school_class:
                        messages.error(request, f'Class {school_class} already has a subject during {time_slot}.')
                else:
                    # Create timetable entry
                    Timetable.objects.create(
                        time_slot=time_slot,
                        subject=subject,
                        teacher=teacher,
                        school_class=school_class,
                        room=room,
                        term=active_term,
                        academic_year=f"{active_term.start_date.year}-{active_term.end_date.year}"
                    )
                    
                    messages.success(request, 'Timetable entry created successfully.')
                    return redirect('academic:timetable_list')
                    
            except Exception as e:
                messages.error(request, f'Error creating timetable entry: {str(e)}')
    
    # Get available options
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('day_of_week', 'start_time')
    subjects = Subject.objects.all()
    teachers = Teacher.objects.all()
    classes = SchoolClass.objects.all()
    rooms = RoomAssignment.objects.filter(is_available=True)
    
    # Filter based on user role
    if request.user.has_role('class_teacher'):
        try:
            class_ids = ClassTeacher.objects.filter(
                teacher=request.user.teacher
            ).values_list('school_class_id', flat=True)
            classes = SchoolClass.objects.filter(id__in=class_ids)
        except:
            classes = SchoolClass.objects.none()
    
    context = {
        'time_slots': time_slots,
        'subjects': subjects,
        'teachers': teachers,
        'classes': classes,
        'rooms': rooms,
        'active_term': active_term,
    }
    
    return render(request, 'academic/timetable_create.html', context)


@login_required
def timetable_edit(request, timetable_id):
    """Edit a timetable entry"""
    
    if not can_manage_timetable(request.user):
        messages.error(request, 'Only class teachers and admins can edit timetables.')
        return redirect('academic:timetable_list')
    
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')
        room_id = request.POST.get('room')
        
        # Validate required fields
        if not all([subject_id, teacher_id, room_id]):
            messages.error(request, 'All fields are required.')
        else:
            try:
                subject = Subject.objects.get(id=subject_id)
                teacher = Teacher.objects.get(id=teacher_id)
                room = RoomAssignment.objects.get(id=room_id)
                
                # Check for conflicts (excluding current timetable)
                conflicts = Timetable.objects.filter(
                    time_slot=timetable.time_slot,
                    term=timetable.term,
                    is_active=True
                ).filter(
                    Q(teacher=teacher) | Q(room=room)
                ).exclude(id=timetable.id)
                
                if conflicts.exists():
                    conflict = conflicts.first()
                    if conflict.teacher == teacher:
                        messages.error(request, f'Teacher {teacher} is already assigned during {timetable.time_slot}.')
                    elif conflict.room == room:
                        messages.error(request, f'Room {room.room_name} is already booked during {timetable.time_slot}.')
                else:
                    # Update timetable entry
                    timetable.subject = subject
                    timetable.teacher = teacher
                    timetable.room = room
                    timetable.save()
                    
                    messages.success(request, 'Timetable entry updated successfully.')
                    return redirect('academic:timetable_list')
                    
            except Exception as e:
                messages.error(request, f'Error updating timetable entry: {str(e)}')
    
    context = {
        'timetable': timetable,
        'subjects': Subject.objects.all(),
        'teachers': Teacher.objects.all(),
        'rooms': RoomAssignment.objects.filter(is_available=True),
    }
    
    return render(request, 'academic/timetable_edit.html', context)


@login_required
def timetable_delete(request, timetable_id):
    """Delete a timetable entry"""
    
    if not can_manage_timetable(request.user):
        messages.error(request, 'Only class teachers and admins can delete timetables.')
        return redirect('academic:timetable_list')
    
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    if request.method == 'POST':
        timetable.delete()
        messages.success(request, 'Timetable entry deleted successfully.')
        return redirect('academic:timetable_list')
    
    context = {
        'timetable': timetable,
    }
    
    return render(request, 'academic/timetable_delete.html', context)


@login_required
def view_class_timetable(request, class_id):
    """View timetable for a specific class"""
    
    school_class = get_object_or_404(SchoolClass, id=class_id)
    active_term = Term.objects.filter(is_active=True).first()
    
    if not active_term:
        messages.error(request, 'No active term found.')
        return redirect('core:dashboard')
    
    # Get timetable entries for the class
    timetables = Timetable.objects.filter(
        school_class=school_class,
        term=active_term,
        is_active=True
    ).select_related('time_slot', 'subject', 'teacher', 'room').order_by(
        'time_slot__day_of_week', 'time_slot__start_time'
    )
    
    # Organize timetable by day and time
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    timetable_grid = {}
    for day_num, day_name in enumerate(days):
        timetable_grid[day_name] = {}
        for time_slot in time_slots.filter(day_of_week=day_num):
            timetable_entry = timetables.filter(time_slot=time_slot).first()
            timetable_grid[day_name][str(time_slot)] = timetable_entry
    
    context = {
        'school_class': school_class,
        'timetable_grid': timetable_grid,
        'time_slots': time_slots,
        'days': days,
        'active_term': active_term,
    }
    
    return render(request, 'academic/class_timetable.html', context)


@login_required
def enhanced_timetable_create(request):
    """Enhanced timetable creation with better UX"""
    
    if not can_manage_timetable(request.user):
        messages.error(request, 'Only class teachers and admins can create timetables.')
        return redirect('academic:timetable_list')
    
    # Get current active term
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found. Please set an active term first.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        time_slot_id = request.POST.get('time_slot')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher')
        class_id = request.POST.get('school_class')
        room_id = request.POST.get('room')
        
        # Validate required fields
        if not all([time_slot_id, subject_id, teacher_id, class_id, room_id]):
            messages.error(request, 'All fields are required.')
        else:
            try:
                time_slot = TimeSlot.objects.get(id=time_slot_id)
                subject = Subject.objects.get(id=subject_id)
                teacher = Teacher.objects.get(id=teacher_id)
                school_class = SchoolClass.objects.get(id=class_id)
                room = RoomAssignment.objects.get(id=room_id)
                
                # Check for conflicts
                conflicts = Timetable.objects.filter(
                    time_slot=time_slot,
                    term=active_term,
                    is_active=True
                ).filter(
                    Q(teacher=teacher) | Q(room=room) | Q(school_class=school_class)
                )
                
                if conflicts.exists():
                    conflict = conflicts.first()
                    if conflict.teacher == teacher:
                        messages.error(request, f'Teacher {teacher} is already assigned during {time_slot}.')
                    elif conflict.room == room:
                        messages.error(request, f'Room {room.room_name} is already booked during {time_slot}.')
                    elif conflict.school_class == school_class:
                        messages.error(request, f'Class {school_class} already has a subject during {time_slot}.')
                else:
                    # Create timetable entry
                    Timetable.objects.create(
                        time_slot=time_slot,
                        subject=subject,
                        teacher=teacher,
                        school_class=school_class,
                        room=room,
                        term=active_term,
                        academic_year=f"{active_term.start_date.year}-{active_term.end_date.year}"
                    )
                    
                    messages.success(request, 'Timetable entry created successfully.')
                    return redirect('academic:timetable_list')
                    
            except Exception as e:
                messages.error(request, f'Error creating timetable entry: {str(e)}')
    
    # Get available options
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('day_of_week', 'start_time')
    subjects = Subject.objects.all()
    teachers = Teacher.objects.all()
    classes = SchoolClass.objects.all()
    rooms = RoomAssignment.objects.filter(is_available=True)
    
    # Filter based on user role
    if request.user.has_role('class_teacher'):
        try:
            class_ids = ClassTeacher.objects.filter(
                teacher=request.user.teacher
            ).values_list('school_class_id', flat=True)
            classes = SchoolClass.objects.filter(id__in=class_ids)
        except:
            classes = SchoolClass.objects.none()
    
    context = {
        'time_slots': time_slots,
        'subjects': subjects,
        'teachers': teachers,
        'classes': classes,
        'rooms': rooms,
        'active_term': active_term,
    }
    
    return render(request, 'academic/enhanced_timetable_create.html', context)


@login_required
def student_timetable_view(request):
    """View timetable for students"""
    
    if not request.user.has_role('student'):
        messages.error(request, 'Only students can access this page.')
        return redirect('core:dashboard')
    
    student = get_object_or_404(Student, user=request.user)
    return view_class_timetable(request, student.school_class.id)


@login_required
def timetable_conflicts_check(request):
    """AJAX endpoint to check for timetable conflicts"""
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    time_slot_id = request.GET.get('time_slot')
    teacher_id = request.GET.get('teacher')
    room_id = request.GET.get('room')
    class_id = request.GET.get('class')
    subject_id = request.GET.get('subject')
    
    if not time_slot_id:
        return JsonResponse({'error': 'Time slot is required'}, status=400)
    
    try:
        time_slot = TimeSlot.objects.get(id=time_slot_id)
        
        # Get current active term
        active_term = Term.objects.filter(is_active=True).first()
        if not active_term:
            return JsonResponse({'error': 'No active term found'}, status=400)
        
        conflicts = []
        
        # Get subject type if provided
        subject_type = 'academic'  # default
        if subject_id:
            try:
                subject = Subject.objects.get(id=subject_id)
                subject_type = subject.subject_type
            except Subject.DoesNotExist:
                pass
        
        # For special subjects (break, assembly, closing), different rules apply
        if subject_type in ['break', 'assembly', 'closing']:
            # Special subjects can be scheduled for multiple classes at the same time
            # But still check room conflicts if room is specified
            if room_id:
                try:
                    room = RoomAssignment.objects.get(id=room_id)
                    room_conflict = Timetable.objects.filter(
                        time_slot=time_slot,
                        room=room,
                        term=active_term,
                        is_active=True
                    ).first()
                    
                    if room_conflict:
                        conflicts.append({
                            'type': 'room',
                            'message': f'Room {room.room_name} is already booked for {room_conflict.subject} during {time_slot}'
                        })
                except RoomAssignment.DoesNotExist:
                    pass
        else:
            # Regular academic subjects - apply normal conflict rules
            
            # Check teacher conflict if teacher is provided
            if teacher_id:
                try:
                    teacher = Teacher.objects.get(id=teacher_id)
                    teacher_conflict = Timetable.objects.filter(
                        time_slot=time_slot,
                        teacher=teacher,
                        term=active_term,
                        is_active=True
                    ).first()
                    
                    if teacher_conflict:
                        conflicts.append({
                            'type': 'teacher',
                            'message': f'Teacher {teacher} is already assigned to {teacher_conflict.subject} for {teacher_conflict.school_class} during {time_slot}'
                        })
                except Teacher.DoesNotExist:
                    pass
            
            # Check room conflict if room is provided
            if room_id:
                try:
                    room = RoomAssignment.objects.get(id=room_id)
                    room_conflict = Timetable.objects.filter(
                        time_slot=time_slot,
                        room=room,
                        term=active_term,
                        is_active=True
                    ).first()
                    
                    if room_conflict:
                        conflicts.append({
                            'type': 'room',
                            'message': f'Room {room.room_name} is already booked for {room_conflict.subject} with {room_conflict.teacher} during {time_slot}'
                        })
                except RoomAssignment.DoesNotExist:
                    pass
            
            # Check class conflict if class is provided (same class can't have multiple subjects at same time)
            if class_id:
                try:
                    school_class = SchoolClass.objects.get(id=class_id)
                    class_conflict = Timetable.objects.filter(
                        time_slot=time_slot,
                        school_class=school_class,
                        term=active_term,
                        is_active=True
                    ).first()
                    
                    if class_conflict:
                        conflicts.append({
                            'type': 'class',
                            'message': f'Class {school_class} already has {class_conflict.subject} with {class_conflict.teacher} during {time_slot}'
                        })
                except SchoolClass.DoesNotExist:
                    pass
        
        return JsonResponse({
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts
        })
        
    except TimeSlot.DoesNotExist:
        return JsonResponse({'error': 'Invalid time slot'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)



# Lesson Note Management Views

@login_required
def lesson_note_list(request):
    """List accessible notes for teachers or the school administrator."""

    is_school_admin = request.user.has_role('super_admin')
    is_teacher = request.user.has_any_role(['subject_teacher', 'class_teacher'])
    if not is_school_admin and not is_teacher:
        messages.error(request, 'Only teachers and school administrators can access lesson notes.')
        return redirect('core:dashboard')

    teacher = getattr(request.user, 'teacher', None) if is_teacher else None
    if is_teacher and teacher is None and not is_school_admin:
        messages.error(request, 'Your account is not linked to a teacher record.')
        return redirect('core:dashboard')

    lesson_notes = LessonNote.objects.all().select_related(
        'lesson_plan', 'curriculum', 'lesson_plan__subject', 'lesson_plan__school_class'
    ).order_by('-date_taught')
    if not is_school_admin:
        accessible_plans = AcademicDataFilter.filter_lesson_plans(
            request.user, LessonPlan.objects.all()
        )
        lesson_notes = lesson_notes.filter(lesson_plan__in=accessible_plans)
    
    # Filter options
    lesson_plan_id = request.GET.get('lesson_plan')
    if lesson_plan_id:
        lesson_notes = lesson_notes.filter(lesson_plan_id=lesson_plan_id)
    
    curriculum_id = request.GET.get('curriculum')
    if curriculum_id == 'none':
        lesson_notes = lesson_notes.filter(curriculum__isnull=True)
    elif curriculum_id:
        lesson_notes = lesson_notes.filter(curriculum_id=curriculum_id)
    
    engagement = request.GET.get('engagement')
    if engagement:
        lesson_notes = lesson_notes.filter(student_engagement=engagement)
    
    date_from = request.GET.get('date_from')
    if date_from:
        lesson_notes = lesson_notes.filter(date_taught__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        lesson_notes = lesson_notes.filter(date_taught__lte=date_to)
    
    # Pagination
    paginator = Paginator(lesson_notes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    filter_query = request.GET.copy()
    filter_query.pop('page', None)
    
    if is_school_admin:
        lesson_plans = LessonPlan.objects.all()
        curricula = Curriculum.objects.filter(is_published=True)
    else:
        lesson_plans = AcademicDataFilter.filter_lesson_plans(
            request.user, LessonPlan.objects.all()
        )
        curricula = Curriculum.objects.filter(
            subjects__in=teacher.subjects.all(),
            is_published=True,
        ).distinct()

    context = {
        'page_obj': page_obj,
        'teacher': teacher,
        'lesson_plans': lesson_plans,
        'curricula': curricula,
        'engagement_choices': LessonNote._meta.get_field('student_engagement').choices,
        'is_school_admin': is_school_admin,
        'can_create_lesson_note': bool(teacher),
        'filter_query': filter_query.urlencode(),
    }
    
    return render(request, 'academic/lesson_note_list.html', context)


@login_required
def lesson_note_create(request):
    """Create a new lesson note"""
    
    if not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        messages.error(request, 'Only teachers can create lesson notes.')
        return redirect('core:dashboard')
    
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # Get lesson_plan_id from query params if provided
    lesson_plan_id = request.GET.get('lesson_plan')
    initial_data = {}
    
    if lesson_plan_id:
        lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id, teacher=teacher)
        initial_data = {
            'lesson_plan': lesson_plan,
            'curriculum': lesson_plan.curriculum,
            'date_taught': timezone.now().date()
        }
    
    if request.method == 'POST':
        form = LessonNoteForm(request.POST, user=request.user)
        
        if form.is_valid():
            lesson_note = form.save(commit=False)
            lesson_note.teacher = teacher
            if not lesson_note.curriculum_id:
                lesson_note.curriculum = lesson_note.lesson_plan.curriculum
            lesson_note.save()
            
            messages.success(request, 'Lesson note created successfully.')
            return redirect('academic:lesson_note_detail', lesson_note_id=lesson_note.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LessonNoteForm(user=request.user, initial=initial_data)
    
    context = {
        'form': form,
        'teacher': teacher,
        'action': 'Create',
    }
    
    return render(request, 'academic/lesson_note_form.html', context)


@login_required
def lesson_note_detail(request, lesson_note_id):
    """View lesson note details"""
    
    lesson_note = get_object_or_404(LessonNote, id=lesson_note_id)
    
    if not AcademicPermissionManager.can_view_lesson_plan(
        request.user, lesson_note.lesson_plan
    ):
        messages.error(request, 'You do not have permission to view this lesson note.')
        return redirect('academic:lesson_note_list')
    
    context = {
        'lesson_note': lesson_note,
        'can_manage_note': (
            request.user.has_role('super_admin')
            or lesson_note.teacher.user_id == request.user.id
        ),
    }
    
    return render(request, 'academic/lesson_note_detail.html', context)


@login_required
def lesson_note_edit(request, lesson_note_id):
    """Edit an existing lesson note"""
    
    lesson_note = get_object_or_404(LessonNote, id=lesson_note_id)
    
    is_school_admin = request.user.has_role('super_admin')
    is_teacher = request.user.has_any_role(['subject_teacher', 'class_teacher'])
    if not is_school_admin and not is_teacher:
        messages.error(request, 'Only teachers and school administrators can edit lesson notes.')
        return redirect('core:dashboard')

    teacher = getattr(request.user, 'teacher', None) if is_teacher else None
    if not is_school_admin and lesson_note.teacher != teacher:
        messages.error(request, 'You can only edit your own lesson notes.')
        return redirect('academic:lesson_note_detail', lesson_note_id=lesson_note.id)
    
    if request.method == 'POST':
        form = LessonNoteForm(request.POST, instance=lesson_note, user=request.user)
        
        if form.is_valid():
            lesson_note = form.save(commit=False)
            if is_school_admin:
                lesson_note.teacher = lesson_note.lesson_plan.teacher
            lesson_note.save()
            
            messages.success(request, 'Lesson note updated successfully.')
            return redirect('academic:lesson_note_detail', lesson_note_id=lesson_note.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LessonNoteForm(instance=lesson_note, user=request.user)
    
    context = {
        'form': form,
        'lesson_note': lesson_note,
        'teacher': teacher,
        'action': 'Edit',
    }
    
    return render(request, 'academic/lesson_note_form.html', context)


@login_required
def lesson_note_delete(request, lesson_note_id):
    """Delete a lesson note"""
    
    lesson_note = get_object_or_404(LessonNote, id=lesson_note_id)
    
    is_school_admin = request.user.has_role('super_admin')
    is_teacher = request.user.has_any_role(['subject_teacher', 'class_teacher'])
    if not is_school_admin and not is_teacher:
        messages.error(request, 'Only teachers and school administrators can delete lesson notes.')
        return redirect('core:dashboard')

    teacher = getattr(request.user, 'teacher', None) if is_teacher else None
    if not is_school_admin and lesson_note.teacher != teacher:
        messages.error(request, 'You can only delete your own lesson notes.')
        return redirect('academic:lesson_note_detail', lesson_note_id=lesson_note.id)
    
    if request.method == 'POST':
        lesson_note.delete()
        messages.success(request, 'Lesson note deleted successfully.')
        return redirect('academic:lesson_note_list')
    
    context = {
        'lesson_note': lesson_note,
    }
    
    return render(request, 'academic/lesson_note_confirm_delete.html', context)


@login_required
def lesson_plan_notes(request, lesson_plan_id):
    """View all notes for a specific lesson plan"""
    
    lesson_plan = get_object_or_404(LessonPlan, id=lesson_plan_id)
    
    if not AcademicPermissionManager.can_view_lesson_plan(request.user, lesson_plan):
        messages.error(request, 'You do not have permission to view these notes.')
        return redirect('academic:lesson_plan_list')
    
    lesson_notes = LessonNote.objects.filter(lesson_plan=lesson_plan).order_by('-date_taught')
    
    context = {
        'lesson_plan': lesson_plan,
        'lesson_notes': lesson_notes,
    }
    
    return render(request, 'academic/lesson_plan_notes.html', context)



