"""
Permission classes and access control logic for Academic Management System

This module provides centralized role-based access control for all academic
management features, ensuring data security and proper user authorization.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from functools import wraps
from .models import (
    User, Teacher, Student, SchoolClass, Subject, Term,
    Curriculum, LearningObjective, LessonPlan, CurriculumCoverage,
    Assignment, AssignmentSubmission, AcademicEvent, Holiday, ExamSchedule,
    Timetable, TimeSlot, RoomAssignment
)


class AcademicPermissionManager:
    """Central manager for academic management permissions"""
    
    @staticmethod
    def can_view_curriculum(user, curriculum=None):
        """Check if user can view curriculum(s)"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            if curriculum is None:
                return True  # Can view curriculum list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if teaching any subject in the curriculum
                return curriculum.subjects.filter(
                    id__in=teacher.subjects.all()
                ).exists()
        
        return False
    
    @staticmethod
    def can_create_curriculum(user):
        """Check if user can create curricula"""
        return user.has_any_role(['super_admin', 'subject_teacher'])
    
    @staticmethod
    def can_edit_curriculum(user, curriculum):
        """Check if user can edit a specific curriculum"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can edit if they created it or teach subjects in it
                return (curriculum.created_by == user or 
                       curriculum.subjects.filter(
                           id__in=teacher.subjects.all()
                       ).exists())
        
        return False
    
    @staticmethod
    def can_view_lesson_plan(user, lesson_plan=None):
        """Check if user can view lesson plan(s)"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_role('subject_teacher'):
            if lesson_plan is None:
                return True  # Can view lesson plan list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if they created it or teach the subject/class
                return (lesson_plan.teacher == teacher or
                       (teacher.subjects.filter(id=lesson_plan.subject.id).exists() and
                        teacher.classes.filter(id=lesson_plan.school_class.id).exists()))
        
        if user.has_role('class_teacher'):
            if lesson_plan is None:
                return True  # Can view lesson plan list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if it's for their class
                return teacher.classes.filter(id=lesson_plan.school_class.id).exists()
        
        return False
    
    @staticmethod
    def can_create_lesson_plan(user):
        """Check if user can create lesson plans"""
        return user.has_role('subject_teacher')
    
    @staticmethod
    def can_edit_lesson_plan(user, lesson_plan):
        """Check if user can edit a specific lesson plan"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can edit if they created it
                return lesson_plan.teacher == teacher
        
        return False
    
    @staticmethod
    def can_view_coverage_report(user, curriculum=None, school_class=None):
        """Check if user can view coverage reports"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Check curriculum access
                if curriculum and not curriculum.subjects.filter(
                    id__in=teacher.subjects.all()
                ).exists():
                    return False
                
                # Check class access
                if school_class and school_class not in teacher.classes.all():
                    return False
                
                return True
        
        return False
    
    @staticmethod
    def can_view_assignment(user, assignment=None):
        """Check if user can view assignment(s)"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_role('subject_teacher'):
            if assignment is None:
                return True  # Can view assignment list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if they created it or teach the subject
                return (assignment.teacher == teacher or
                       teacher.subjects.filter(id=assignment.subject.id).exists())
        
        if user.has_role('class_teacher'):
            if assignment is None:
                return True  # Can view assignment list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if it's assigned to their class
                return assignment.school_classes.filter(
                    id__in=teacher.classes.all()
                ).exists()
        
        if user.has_role('student'):
            if assignment is None:
                return True  # Can view assignment list
            
            student = getattr(user, 'student', None)
            if student:
                # Can view if assigned to their class
                return assignment.school_classes.filter(
                    id=student.school_class.id
                ).exists()
        
        return False
    
    @staticmethod
    def can_create_assignment(user):
        """Check if user can create assignments"""
        return user.has_role('subject_teacher')
    
    @staticmethod
    def can_edit_assignment(user, assignment):
        """Check if user can edit a specific assignment"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can edit if they created it
                return assignment.teacher == teacher
        
        return False
    
    @staticmethod
    def can_submit_assignment(user, assignment):
        """Check if user can submit to an assignment"""
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Can submit if assigned to their class
                return assignment.school_classes.filter(
                    id=student.school_class.id
                ).exists()
        
        return False
    
    @staticmethod
    def can_view_calendar(user, event=None):
        """Check if user can view calendar events"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            return True  # Teachers can view all calendar events
        
        if user.has_role('student'):
            if event is None:
                return True  # Can view calendar
            
            student = getattr(user, 'student', None)
            if student:
                # Can view events relevant to their class/year
                if event.event_type in ['holiday', 'activity']:
                    return True  # Public events
                
                # For exam events, check if it's for their class
                if hasattr(event, 'examschedule'):
                    return event.examschedule.school_class == student.school_class
        
        return False
    
    @staticmethod
    def can_create_calendar_event(user):
        """Check if user can create calendar events"""
        return user.has_role('super_admin')
    
    @staticmethod
    def can_view_timetable(user, timetable=None):
        """Check if user can view timetable(s)"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_role('subject_teacher'):
            if timetable is None:
                return True  # Can view timetable list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if they're assigned to it
                return timetable.teacher == teacher
        
        if user.has_role('class_teacher'):
            if timetable is None:
                return True  # Can view timetable list
            
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can view if it's for their class
                return teacher.classes.filter(id=timetable.school_class.id).exists()
        
        if user.has_role('student'):
            if timetable is None:
                return True  # Can view timetable list
            
            student = getattr(user, 'student', None)
            if student:
                # Can view if it's for their class
                return timetable.school_class == student.school_class
        
        return False
    
    @staticmethod
    def can_create_timetable(user):
        """Check if user can create timetable entries"""
        return user.has_role('super_admin')


class AcademicDataFilter:
    """Filters for role-based data access"""
    
    @staticmethod
    def filter_curricula(user, queryset):
        """Filter curricula based on user role"""
        if user.has_role('super_admin'):
            return queryset
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to curricula containing subjects they teach
                return queryset.filter(
                    subjects__in=teacher.subjects.all()
                ).distinct()
        
        return queryset.none()
    
    @staticmethod
    def filter_lesson_plans(user, queryset):
        """Filter lesson plans based on user role"""
        if user.has_role('super_admin'):
            return queryset
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to lesson plans they created or for subjects/classes they teach
                return queryset.filter(
                    Q(teacher=teacher) |
                    (Q(subject__in=teacher.subjects.all()) & 
                     Q(school_class__in=teacher.classes.all()))
                ).distinct()
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to lesson plans for their classes
                return queryset.filter(
                    school_class__in=teacher.classes.all()
                ).distinct()
        
        return queryset.none()
    
    @staticmethod
    def filter_assignments(user, queryset):
        """Filter assignments based on user role"""
        if user.has_role('super_admin'):
            return queryset
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to assignments they created or for subjects they teach
                return queryset.filter(
                    Q(teacher=teacher) |
                    Q(subject__in=teacher.subjects.all())
                ).distinct()
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to assignments for their classes
                return queryset.filter(
                    school_classes__in=teacher.classes.all()
                ).distinct()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Filter to assignments for their class
                return queryset.filter(
                    school_classes=student.school_class
                ).distinct()
        
        return queryset.none()
    
    @staticmethod
    def filter_calendar_events(user, queryset):
        """Filter calendar events based on user role"""
        if user.has_role('super_admin'):
            return queryset
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            # Teachers can see all events
            return queryset
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Students see public events and events for their class
                return queryset.filter(
                    Q(event_type__in=['holiday', 'activity']) |
                    Q(examschedule__school_class=student.school_class)
                ).distinct()
        
        return queryset.none()
    
    @staticmethod
    def filter_timetables(user, queryset):
        """Filter timetables based on user role"""
        if user.has_role('super_admin'):
            return queryset
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to timetables they're assigned to
                return queryset.filter(teacher=teacher)
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to timetables for their classes
                return queryset.filter(
                    school_class__in=teacher.classes.all()
                ).distinct()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Filter to timetables for their class
                return queryset.filter(school_class=student.school_class)
        
        return queryset.none()
    
    @staticmethod
    def filter_coverage_reports(user, curriculum_queryset, class_queryset):
        """Filter coverage report data based on user role"""
        if user.has_role('super_admin'):
            return curriculum_queryset, class_queryset
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter curricula to those with subjects they teach
                filtered_curricula = curriculum_queryset.filter(
                    subjects__in=teacher.subjects.all()
                ).distinct()
                
                # Filter classes to those they teach
                filtered_classes = class_queryset.filter(
                    id__in=teacher.classes.all()
                ).distinct()
                
                return filtered_curricula, filtered_classes
        
        return curriculum_queryset.none(), class_queryset.none()


def require_academic_permission(permission_check):
    """Decorator to require specific academic permissions"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not permission_check(request.user, *args, **kwargs):
                raise PermissionDenied("You don't have permission to access this resource.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(*allowed_roles):
    """Decorator to require specific user roles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.user.has_any_role(allowed_roles):
                raise PermissionDenied(f"Access restricted to: {', '.join(allowed_roles)}")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class AcademicPermissionMixin:
    """Mixin for class-based views to handle academic permissions"""
    
    permission_required = None
    role_required = None
    
    def dispatch(self, request, *args, **kwargs):
        # Check role requirement
        if self.role_required and not request.user.has_any_role(self.role_required):
            raise PermissionDenied(f"Access restricted to: {', '.join(self.role_required)}")
        
        # Check specific permission
        if self.permission_required:
            if not self.permission_required(request.user, *args, **kwargs):
                raise PermissionDenied("You don't have permission to access this resource.")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Override to apply role-based filtering"""
        queryset = super().get_queryset()
        
        # Apply appropriate filter based on model
        model_name = queryset.model.__name__.lower()
        
        if model_name == 'curriculum':
            return AcademicDataFilter.filter_curricula(self.request.user, queryset)
        elif model_name == 'lessonplan':
            return AcademicDataFilter.filter_lesson_plans(self.request.user, queryset)
        elif model_name == 'assignment':
            return AcademicDataFilter.filter_assignments(self.request.user, queryset)
        elif model_name == 'academicevent':
            return AcademicDataFilter.filter_calendar_events(self.request.user, queryset)
        elif model_name == 'timetable':
            return AcademicDataFilter.filter_timetables(self.request.user, queryset)
        
        return queryset


# Convenience functions for common permission checks
def can_access_curriculum(user, curriculum_id=None):
    """Check if user can access curriculum functionality"""
    if curriculum_id:
        try:
            curriculum = Curriculum.objects.get(id=curriculum_id)
            return AcademicPermissionManager.can_view_curriculum(user, curriculum)
        except Curriculum.DoesNotExist:
            return False
    return AcademicPermissionManager.can_view_curriculum(user)


def can_access_lesson_plans(user, lesson_plan_id=None):
    """Check if user can access lesson plan functionality"""
    if lesson_plan_id:
        try:
            lesson_plan = LessonPlan.objects.get(id=lesson_plan_id)
            return AcademicPermissionManager.can_view_lesson_plan(user, lesson_plan)
        except LessonPlan.DoesNotExist:
            return False
    return AcademicPermissionManager.can_view_lesson_plan(user)


def can_access_assignments(user, assignment_id=None):
    """Check if user can access assignment functionality"""
    if assignment_id:
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            return AcademicPermissionManager.can_view_assignment(user, assignment)
        except Assignment.DoesNotExist:
            return False
    return AcademicPermissionManager.can_view_assignment(user)


def can_access_calendar(user):
    """Check if user can access calendar functionality"""
    return AcademicPermissionManager.can_view_calendar(user)


def can_access_timetables(user):
    """Check if user can access timetable functionality"""
    return AcademicPermissionManager.can_view_timetable(user)

