"""
Access control utilities for Academic Management System

This module provides utilities for implementing role-based access control
and data filtering across the academic management system.
"""

from django.db.models import Q
from django.core.exceptions import PermissionDenied
from .models import (
    User, Teacher, Student, SchoolClass, Subject, Term,
    Curriculum, LearningObjective, LessonPlan, CurriculumCoverage,
    Assignment, AssignmentSubmission, AcademicEvent, Holiday, ExamSchedule,
    Timetable, TimeSlot, RoomAssignment
)


class AccessControlService:
    """Service for managing access control across academic features"""
    
    @staticmethod
    def get_user_accessible_curricula(user):
        """Get all curricula accessible to the user"""
        if user.has_role('super_admin'):
            return Curriculum.objects.all()
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Curriculum.objects.filter(
                    subjects__in=teacher.subjects.all()
                ).distinct()
        
        return Curriculum.objects.none()
    
    @staticmethod
    def get_user_accessible_lesson_plans(user):
        """Get all lesson plans accessible to the user"""
        if user.has_role('super_admin'):
            return LessonPlan.objects.all()
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return LessonPlan.objects.filter(
                    Q(teacher=teacher) |
                    (Q(subject__in=teacher.subjects.all()) & 
                     Q(school_class__in=teacher.classes.all()))
                ).distinct()
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return LessonPlan.objects.filter(
                    school_class__in=teacher.classes.all()
                ).distinct()
        
        return LessonPlan.objects.none()
    
    @staticmethod
    def get_user_accessible_assignments(user):
        """Get all assignments accessible to the user"""
        if user.has_role('super_admin'):
            return Assignment.objects.all()
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Assignment.objects.filter(
                    Q(teacher=teacher) |
                    Q(subject__in=teacher.subjects.all())
                ).distinct()
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Assignment.objects.filter(
                    school_classes__in=teacher.classes.all()
                ).distinct()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                return Assignment.objects.filter(
                    school_classes=student.school_class
                ).distinct()
        
        return Assignment.objects.none()
    
    @staticmethod
    def get_user_accessible_calendar_events(user):
        """Get all calendar events accessible to the user"""
        if user.has_role('super_admin'):
            return AcademicEvent.objects.all()
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            # Teachers can see all events
            return AcademicEvent.objects.all()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Students see public events and events for their class
                return AcademicEvent.objects.filter(
                    Q(event_type__in=['holiday', 'activity']) |
                    Q(examschedule__school_class=student.school_class)
                ).distinct()
        
        return AcademicEvent.objects.none()
    
    @staticmethod
    def get_user_accessible_timetables(user):
        """Get all timetables accessible to the user"""
        if user.has_role('super_admin'):
            return Timetable.objects.all()
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Timetable.objects.filter(teacher=teacher)
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Timetable.objects.filter(
                    school_class__in=teacher.classes.all()
                ).distinct()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                return Timetable.objects.filter(school_class=student.school_class)
        
        return Timetable.objects.none()
    
    @staticmethod
    def get_user_accessible_classes(user):
        """Get all classes accessible to the user"""
        if user.has_role('super_admin'):
            return SchoolClass.objects.all()
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return teacher.classes.all()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                return SchoolClass.objects.filter(id=student.school_class.id)
        
        return SchoolClass.objects.none()
    
    @staticmethod
    def get_user_accessible_subjects(user):
        """Get all subjects accessible to the user"""
        if user.has_role('super_admin'):
            return Subject.objects.all()
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return teacher.subjects.all()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Get subjects taught in their class
                return Subject.objects.filter(
                    timetable__school_class=student.school_class
                ).distinct()
        
        return Subject.objects.none()
    
    @staticmethod
    def filter_assignment_submissions(user, queryset):
        """Filter assignment submissions based on user role"""
        if user.has_role('super_admin'):
            return queryset
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to submissions for assignments they created or teach
                return queryset.filter(
                    Q(assignment__teacher=teacher) |
                    Q(assignment__subject__in=teacher.subjects.all())
                ).distinct()
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Filter to submissions for assignments in their classes
                return queryset.filter(
                    assignment__school_classes__in=teacher.classes.all()
                ).distinct()
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                # Filter to their own submissions
                return queryset.filter(student=student)
        
        return queryset.none()
    
    @staticmethod
    def can_access_student_data(user, student):
        """Check if user can access specific student's data"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Can access if student is in their classes
                return teacher.classes.filter(id=student.school_class.id).exists()
        
        if user.has_role('student'):
            student_user = getattr(user, 'student', None)
            if student_user:
                # Can only access their own data
                return student_user == student
        
        return False
    
    @staticmethod
    def can_access_teacher_data(user, teacher):
        """Check if user can access specific teacher's data"""
        if user.has_role('super_admin'):
            return True
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            user_teacher = getattr(user, 'teacher', None)
            if user_teacher:
                # Can access if they share classes or subjects
                shared_classes = user_teacher.classes.filter(
                    id__in=teacher.classes.all()
                ).exists()
                shared_subjects = user_teacher.subjects.filter(
                    id__in=teacher.subjects.all()
                ).exists()
                
                return shared_classes or shared_subjects or user_teacher == teacher
        
        return False
    
    @staticmethod
    def get_coverage_accessible_data(user):
        """Get curricula and classes accessible for coverage reports"""
        if user.has_role('super_admin'):
            return Curriculum.objects.all(), SchoolClass.objects.all()
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                curricula = Curriculum.objects.filter(
                    subjects__in=teacher.subjects.all()
                ).distinct()
                classes = teacher.classes.all()
                return curricula, classes
        
        return Curriculum.objects.none(), SchoolClass.objects.none()
    
    @staticmethod
    def validate_assignment_access(user, assignment, action='view'):
        """Validate user access to assignment with specific action"""
        if user.has_role('super_admin'):
            return True
        
        if action == 'view':
            if user.has_role('subject_teacher'):
                teacher = getattr(user, 'teacher', None)
                if teacher:
                    return (assignment.teacher == teacher or
                           teacher.subjects.filter(id=assignment.subject.id).exists())
            
            elif user.has_role('class_teacher'):
                teacher = getattr(user, 'teacher', None)
                if teacher:
                    return assignment.school_classes.filter(
                        id__in=teacher.classes.all()
                    ).exists()
            
            elif user.has_role('student'):
                student = getattr(user, 'student', None)
                if student:
                    return assignment.school_classes.filter(
                        id=student.school_class.id
                    ).exists()
        
        elif action == 'edit':
            if user.has_role('subject_teacher'):
                teacher = getattr(user, 'teacher', None)
                if teacher:
                    return assignment.teacher == teacher
        
        elif action == 'submit':
            if user.has_role('student'):
                student = getattr(user, 'student', None)
                if student:
                    return assignment.school_classes.filter(
                        id=student.school_class.id
                    ).exists()
        
        return False
    
    @staticmethod
    def validate_curriculum_access(user, curriculum, action='view'):
        """Validate user access to curriculum with specific action"""
        if user.has_role('super_admin'):
            return True
        
        if action == 'view':
            if user.has_any_role(['subject_teacher', 'class_teacher']):
                teacher = getattr(user, 'teacher', None)
                if teacher:
                    return curriculum.subjects.filter(
                        id__in=teacher.subjects.all()
                    ).exists()
        
        elif action in ['create', 'edit']:
            if user.has_role('subject_teacher'):
                if action == 'create':
                    return True
                else:  # edit
                    teacher = getattr(user, 'teacher', None)
                    if teacher:
                        return (curriculum.created_by == user or
                               curriculum.subjects.filter(
                                   id__in=teacher.subjects.all()
                               ).exists())
        
        return False
    
    @staticmethod
    def validate_lesson_plan_access(user, lesson_plan, action='view'):
        """Validate user access to lesson plan with specific action"""
        if user.has_role('super_admin'):
            return True
        
        if action == 'view':
            if user.has_role('subject_teacher'):
                teacher = getattr(user, 'teacher', None)
                if teacher:
                    return (lesson_plan.teacher == teacher or
                           (teacher.subjects.filter(id=lesson_plan.subject.id).exists() and
                            teacher.classes.filter(id=lesson_plan.school_class.id).exists()))
            
            elif user.has_role('class_teacher'):
                teacher = getattr(user, 'teacher', None)
                if teacher:
                    return teacher.classes.filter(id=lesson_plan.school_class.id).exists()
        
        elif action in ['create', 'edit']:
            if user.has_role('subject_teacher'):
                if action == 'create':
                    return True
                else:  # edit
                    teacher = getattr(user, 'teacher', None)
                    if teacher:
                        return lesson_plan.teacher == teacher
        
        return False
    
    @staticmethod
    def get_user_dashboard_data(user):
        """Get dashboard data appropriate for user role"""
        user_roles = user.get_all_roles()
        dashboard_data = {
            'role': user_roles[0] if user_roles else '',
            'roles': user_roles,
            'can_access_curricula': False,
            'can_access_lesson_plans': False,
            'can_access_assignments': False,
            'can_access_calendar': False,
            'can_access_timetables': False,
            'can_access_coverage_reports': False,
        }
        
        if user.has_role('super_admin'):
            dashboard_data.update({
                'can_access_curricula': True,
                'can_access_lesson_plans': True,
                'can_access_assignments': True,
                'can_access_calendar': True,
                'can_access_timetables': True,
                'can_access_coverage_reports': True,
            })
        
        elif user.has_role('subject_teacher'):
            dashboard_data.update({
                'can_access_curricula': True,
                'can_access_lesson_plans': True,
                'can_access_assignments': True,
                'can_access_calendar': True,
                'can_access_timetables': True,
                'can_access_coverage_reports': True,
            })
        
        elif user.has_role('class_teacher'):
            dashboard_data.update({
                'can_access_curricula': True,
                'can_access_lesson_plans': True,
                'can_access_assignments': True,
                'can_access_calendar': True,
                'can_access_timetables': True,
                'can_access_coverage_reports': True,
            })
        
        elif user.has_role('student'):
            dashboard_data.update({
                'can_access_assignments': True,
                'can_access_calendar': True,
                'can_access_timetables': True,
            })
        
        return dashboard_data


class RoleBasedQueryManager:
    """Manager for creating role-based database queries"""
    
    @staticmethod
    def get_curriculum_query_for_user(user):
        """Get Q object for filtering curricula by user role"""
        if user.has_role('super_admin'):
            return Q()  # No filtering needed
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Q(subjects__in=teacher.subjects.all())
        
        return Q(pk__in=[])  # Empty queryset
    
    @staticmethod
    def get_assignment_query_for_user(user):
        """Get Q object for filtering assignments by user role"""
        if user.has_role('super_admin'):
            return Q()  # No filtering needed
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Q(teacher=teacher) | Q(subject__in=teacher.subjects.all())
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Q(school_classes__in=teacher.classes.all())
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                return Q(school_classes=student.school_class)
        
        return Q(pk__in=[])  # Empty queryset
    
    @staticmethod
    def get_lesson_plan_query_for_user(user):
        """Get Q object for filtering lesson plans by user role"""
        if user.has_role('super_admin'):
            return Q()  # No filtering needed
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return (Q(teacher=teacher) |
                       (Q(subject__in=teacher.subjects.all()) & 
                        Q(school_class__in=teacher.classes.all())))
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Q(school_class__in=teacher.classes.all())
        
        return Q(pk__in=[])  # Empty queryset
    
    @staticmethod
    def get_timetable_query_for_user(user):
        """Get Q object for filtering timetables by user role"""
        if user.has_role('super_admin'):
            return Q()  # No filtering needed
        
        if user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Q(teacher=teacher)
        
        if user.has_role('class_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                return Q(school_class__in=teacher.classes.all())
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                return Q(school_class=student.school_class)
        
        return Q(pk__in=[])  # Empty queryset
    
    @staticmethod
    def get_calendar_event_query_for_user(user):
        """Get Q object for filtering calendar events by user role"""
        if user.has_role('super_admin'):
            return Q()  # No filtering needed
        
        if user.has_any_role(['subject_teacher', 'class_teacher']):
            return Q()  # Teachers can see all events
        
        if user.has_role('student'):
            student = getattr(user, 'student', None)
            if student:
                return (Q(event_type__in=['holiday', 'activity']) |
                       Q(examschedule__school_class=student.school_class))
        
        return Q(pk__in=[])  # Empty queryset
