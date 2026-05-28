"""
Validation utilities for Academic Management System

This module provides comprehensive validation for foreign key relationships,
referential integrity, and data consistency across academic management models.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from datetime import timedelta


class AcademicDataValidator:
    """
    Comprehensive validator for academic management data integrity
    """
    
    @staticmethod
    def validate_curriculum_relationships(curriculum):
        """
        Validate curriculum relationships with existing models
        """
        errors = []
        
        # Validate created_by user exists and has appropriate role - only if saved
        if curriculum.pk and curriculum.created_by_id is None:
            errors.append("Curriculum must have a creator.")
        elif curriculum.pk and curriculum.created_by:
            if not hasattr(curriculum.created_by, 'role'):
                errors.append("Curriculum creator must have a defined role.")
            elif curriculum.created_by.role not in ['super_admin', 'subject_teacher']:
                errors.append("Only super admins and subject teachers can create curricula.")
        
        # Validate subjects exist and are active
        if curriculum.pk:  # Only validate if curriculum is saved (has subjects)
            for subject in curriculum.subjects.all():
                if not subject.pk:
                    errors.append(f"Subject '{subject}' does not exist in the system.")
        
        # Validate academic year format
        if curriculum.academic_year:
            if not AcademicDataValidator._validate_academic_year_format(curriculum.academic_year):
                errors.append("Academic year must be in format 'YYYY-YYYY' (e.g., '2024-2025').")
        
        return errors
    
    @staticmethod
    def validate_learning_objective_relationships(learning_objective):
        """
        Validate learning objective relationships
        """
        errors = []
        
        # Validate curriculum exists
        if not learning_objective.curriculum_id:
            errors.append("Learning objective must be associated with a curriculum.")
        elif learning_objective.curriculum_id and learning_objective.curriculum:
            # Validate subject is part of curriculum's subjects
            if learning_objective.subject and learning_objective.curriculum.pk:
                if learning_objective.subject not in learning_objective.curriculum.subjects.all():
                    errors.append(f"Subject '{learning_objective.subject}' is not part of the curriculum '{learning_objective.curriculum}'.")
        
        # Validate subject exists
        if not learning_objective.subject_id:
            errors.append("Learning objective must be associated with a subject.")
        
        return errors
    
    @staticmethod
    def validate_lesson_plan_relationships(lesson_plan):
        """
        Validate lesson plan relationships and constraints
        """
        errors = []
        
        # Validate curriculum exists
        if not lesson_plan.curriculum_id:
            errors.append("Lesson plan must be associated with a curriculum.")
        
        # Validate subject exists
        if not lesson_plan.subject_id:
            errors.append("Lesson plan must be associated with a subject.")
        
        # Validate school class exists
        if not lesson_plan.school_class_id:
            errors.append("Lesson plan must be associated with a school class.")
        
        # Validate teacher exists and has appropriate permissions
        if not lesson_plan.teacher_id:
            # Only error if this is being saved (has pk) - during form validation teacher isn't set yet
            if lesson_plan.pk:
                errors.append("Lesson plan must be associated with a teacher.")
        elif lesson_plan.teacher_id and lesson_plan.teacher:
            # Check if teacher teaches the subject
            if lesson_plan.subject and lesson_plan.subject not in lesson_plan.teacher.subjects.all():
                errors.append(f"Teacher '{lesson_plan.teacher}' is not authorized to teach '{lesson_plan.subject}'.")
            
            # Check if teacher teaches the class
            if lesson_plan.school_class and lesson_plan.school_class not in lesson_plan.teacher.classes.all():
                errors.append(f"Teacher '{lesson_plan.teacher}' is not assigned to class '{lesson_plan.school_class}'.")
        
        # Validate learning objectives belong to the curriculum
        if lesson_plan.pk and lesson_plan.curriculum:
            for objective in lesson_plan.learning_objectives.all():
                if objective.curriculum != lesson_plan.curriculum:
                    errors.append(f"Learning objective '{objective}' does not belong to curriculum '{lesson_plan.curriculum}'.")
        
        # Validate subject consistency
        if lesson_plan.curriculum_id and lesson_plan.subject_id and lesson_plan.curriculum and lesson_plan.curriculum.pk:
            if lesson_plan.subject not in lesson_plan.curriculum.subjects.all():
                errors.append(f"Subject '{lesson_plan.subject}' is not part of curriculum '{lesson_plan.curriculum}'.")
        
        return errors
    
    @staticmethod
    def validate_academic_event_relationships(academic_event):
        """
        Validate academic event relationships and constraints
        """
        errors = []
        
        # Validate created_by user exists
        if not academic_event.created_by_id:
            errors.append("Academic event must have a creator.")
        
        # Validate terms exist and are consistent with academic year
        if academic_event.pk:  # Only validate if event is saved (has terms)
            for term in academic_event.terms.all():
                if not term.pk:
                    errors.append(f"Term '{term}' does not exist in the system.")
                else:
                    # Validate event dates fall within term dates
                    if (academic_event.start_date.date() < term.start_date or 
                        academic_event.end_date.date() > term.end_date):
                        errors.append(f"Event dates must fall within term '{term}' dates ({term.start_date} to {term.end_date}).")
        
        # Validate academic year format
        if academic_event.academic_year:
            if not AcademicDataValidator._validate_academic_year_format(academic_event.academic_year):
                errors.append("Academic year must be in format 'YYYY-YYYY' (e.g., '2024-2025').")
        
        return errors
    
    @staticmethod
    def validate_exam_schedule_relationships(exam_schedule):
        """
        Validate exam schedule relationships and constraints
        """
        errors = []
        
        # Validate subject exists
        if not exam_schedule.subject_id:
            errors.append("Exam schedule must be associated with a subject.")
        
        # Validate school class exists
        if not exam_schedule.school_class_id:
            errors.append("Exam schedule must be associated with a school class.")
        
        # Validate invigilator is a valid teacher
        if exam_schedule.invigilator_id:
            if not exam_schedule.invigilator.pk:
                errors.append("Invigilator must be a valid teacher.")
            else:
                # Check if invigilator teaches the class or subject
                if (exam_schedule.school_class not in exam_schedule.invigilator.classes.all() and
                    exam_schedule.subject not in exam_schedule.invigilator.subjects.all()):
                    errors.append(f"Invigilator '{exam_schedule.invigilator}' should teach either the subject or the class.")
        
        # Validate academic event exists
        if not exam_schedule.academic_event_id:
            errors.append("Exam schedule must be associated with an academic event.")
        
        return errors
    
    @staticmethod
    def validate_timetable_relationships(timetable):
        """
        Validate timetable relationships and constraints
        """
        errors = []
        
        # Validate time slot exists
        if not timetable.time_slot_id:
            errors.append("Timetable entry must be associated with a time slot.")
        
        # Validate subject exists
        if not timetable.subject_id:
            errors.append("Timetable entry must be associated with a subject.")
        
        # Validate teacher exists and can teach the subject
        if not timetable.teacher_id:
            errors.append("Timetable entry must be associated with a teacher.")
        elif timetable.teacher and timetable.subject:
            if timetable.subject not in timetable.teacher.subjects.all():
                errors.append(f"Teacher '{timetable.teacher}' is not qualified to teach '{timetable.subject}'.")
        
        # Validate school class exists and teacher is assigned to it
        if not timetable.school_class_id:
            errors.append("Timetable entry must be associated with a school class.")
        elif timetable.teacher and timetable.school_class:
            if timetable.school_class not in timetable.teacher.classes.all():
                errors.append(f"Teacher '{timetable.teacher}' is not assigned to class '{timetable.school_class}'.")
        
        # Validate room exists and is available
        if not timetable.room_id:
            errors.append("Timetable entry must be associated with a room.")
        elif timetable.room and not timetable.room.is_available:
            errors.append(f"Room '{timetable.room.room_name}' is not available for scheduling.")
        
        # Validate term exists
        if not timetable.term_id:
            errors.append("Timetable entry must be associated with a term.")
        
        # Validate academic year format
        if timetable.academic_year:
            if not AcademicDataValidator._validate_academic_year_format(timetable.academic_year):
                errors.append("Academic year must be in format 'YYYY-YYYY' (e.g., '2024-2025').")
        
        return errors
    
    @staticmethod
    def validate_assignment_relationships(assignment):
        """
        Validate assignment relationships and constraints
        """
        errors = []
        
        # Validate subject exists
        if not assignment.subject_id:
            errors.append("Assignment must be associated with a subject.")
        
        # Validate teacher exists and can teach the subject - only if saved
        if not assignment.teacher_id:
            if assignment.pk:
                errors.append("Assignment must be associated with a teacher.")
        elif assignment.teacher and assignment.subject:
            if assignment.subject not in assignment.teacher.subjects.all():
                errors.append(f"Teacher '{assignment.teacher}' is not qualified to teach '{assignment.subject}'.")
        
        # Validate school classes exist and teacher is assigned to them
        if assignment.pk:  # Only validate if assignment is saved (has classes)
            for school_class in assignment.school_classes.all():
                if not school_class.pk:
                    errors.append(f"School class '{school_class}' does not exist in the system.")
                elif assignment.teacher and school_class not in assignment.teacher.classes.all():
                    errors.append(f"Teacher '{assignment.teacher}' is not assigned to class '{school_class}'.")
        
        return errors
    
    @staticmethod
    def validate_assignment_submission_relationships(submission):
        """
        Validate assignment submission relationships and constraints
        """
        errors = []
        
        # Only validate if submission is saved (has pk)
        if not submission.pk:
            return errors
        
        # Validate assignment exists
        if not submission.assignment_id:
            errors.append("Submission must be associated with an assignment.")
        
        # Validate student exists
        if not submission.student_id:
            errors.append("Submission must be associated with a student.")
        
        # Validate student is in one of the assignment's target classes
        if submission.assignment_id and submission.student_id and submission.assignment and submission.student:
            student_classes = [submission.student.school_class]
            assignment_classes = list(submission.assignment.school_classes.all())
            
            if not any(cls in assignment_classes for cls in student_classes):
                errors.append(f"Student '{submission.student}' is not in any of the assignment's target classes.")
        
        # Validate submission is not after deadline (unless late submissions allowed)
        if submission.assignment_id and submission.assignment and not submission.assignment.allow_late_submission:
            if submission.submitted_at and submission.submitted_at > submission.assignment.due_date:
                errors.append("Late submissions are not allowed for this assignment.")
        
        return errors
    
    @staticmethod
    def validate_curriculum_coverage_relationships(coverage):
        """
        Validate curriculum coverage relationships and constraints
        """
        errors = []
        
        # Validate curriculum exists
        if not coverage.curriculum_id:
            errors.append("Coverage record must be associated with a curriculum.")
        
        # Validate school class exists
        if not coverage.school_class_id:
            errors.append("Coverage record must be associated with a school class.")
        
        # Validate learning objective exists and belongs to curriculum
        if not coverage.learning_objective_id:
            errors.append("Coverage record must be associated with a learning objective.")
        elif coverage.learning_objective and coverage.curriculum:
            if coverage.learning_objective.curriculum != coverage.curriculum:
                errors.append(f"Learning objective '{coverage.learning_objective}' does not belong to curriculum '{coverage.curriculum}'.")
        
        # Validate completion percentage is within valid range
        if coverage.completion_percentage < 0 or coverage.completion_percentage > 100:
            errors.append("Completion percentage must be between 0 and 100.")
        
        # Validate lesson counts are consistent
        if coverage.completed_lessons > coverage.total_planned_lessons:
            errors.append("Completed lessons cannot exceed total planned lessons.")
        
        return errors
    
    @staticmethod
    def validate_cascade_deletion_safety(model_instance, field_name):
        """
        Validate that cascade deletion is safe and won't cause data loss
        """
        warnings = []
        
        # Get related objects that would be deleted
        related_objects = []
        
        for field in model_instance._meta.get_fields():
            if (hasattr(field, 'related_model') and 
                hasattr(field, 'on_delete') and 
                field.on_delete == models.CASCADE):
                
                related_manager = getattr(model_instance, field.get_accessor_name())
                count = related_manager.count()
                
                if count > 0:
                    related_objects.append({
                        'model': field.related_model.__name__,
                        'count': count,
                        'field': field.name
                    })
        
        if related_objects:
            warnings.append(f"Deleting this {model_instance.__class__.__name__} will also delete:")
            for obj in related_objects:
                warnings.append(f"  - {obj['count']} {obj['model']} record(s)")
        
        return warnings
    
    @staticmethod
    def _validate_academic_year_format(academic_year):
        """
        Validate academic year format (YYYY-YYYY)
        """
        if not academic_year:
            return False
        
        parts = academic_year.split('-')
        if len(parts) != 2:
            return False
        
        try:
            start_year = int(parts[0])
            end_year = int(parts[1])
            
            # End year should be start year + 1
            if end_year != start_year + 1:
                return False
            
            # Years should be reasonable (between 2000 and 2100)
            if start_year < 2000 or start_year > 2100:
                return False
            
            return True
        except ValueError:
            return False


class DataConsistencyChecker:
    """
    Service for checking data consistency across academic management models
    """
    
    @staticmethod
    def check_curriculum_consistency():
        """
        Check consistency across curriculum-related models
        """
        from .models import Curriculum, LearningObjective, LessonPlan, CurriculumCoverage
        
        issues = []
        
        # Check for curricula without learning objectives
        curricula_without_objectives = Curriculum.objects.filter(
            learning_objectives__isnull=True,
            is_published=True
        )
        
        for curriculum in curricula_without_objectives:
            issues.append(f"Published curriculum '{curriculum}' has no learning objectives.")
        
        # Check for learning objectives without associated lesson plans
        objectives_without_lessons = LearningObjective.objects.filter(
            lessonplan__isnull=True
        )
        
        for objective in objectives_without_lessons:
            issues.append(f"Learning objective '{objective}' has no associated lesson plans.")
        
        # Check for coverage records with inconsistent data
        inconsistent_coverage = CurriculumCoverage.objects.filter(
            completed_lessons__gt=models.F('total_planned_lessons')
        )
        
        for coverage in inconsistent_coverage:
            issues.append(f"Coverage record for '{coverage}' has more completed lessons than planned.")
        
        return issues
    
    @staticmethod
    def check_timetable_consistency():
        """
        Check consistency across timetable-related models
        """
        from .models import Timetable, Teacher, Subject, SchoolClass
        
        issues = []
        
        # Check for timetable entries with teachers not qualified for subjects
        invalid_teacher_subjects = Timetable.objects.filter(
            is_active=True
        ).exclude(
            teacher__subjects=models.F('subject')
        )
        
        for entry in invalid_teacher_subjects:
            issues.append(f"Timetable entry '{entry}' assigns teacher '{entry.teacher}' to subject '{entry.subject}' they don't teach.")
        
        # Check for timetable entries with teachers not assigned to classes
        invalid_teacher_classes = Timetable.objects.filter(
            is_active=True
        ).exclude(
            teacher__classes=models.F('school_class')
        )
        
        for entry in invalid_teacher_classes:
            issues.append(f"Timetable entry '{entry}' assigns teacher '{entry.teacher}' to class '{entry.school_class}' they're not assigned to.")
        
        return issues
    
    @staticmethod
    def check_assignment_consistency():
        """
        Check consistency across assignment-related models
        """
        from .models import Assignment, AssignmentSubmission, Student
        
        issues = []
        
        # Check for submissions from students not in target classes
        invalid_submissions = AssignmentSubmission.objects.filter(
            assignment__school_classes__isnull=False
        ).exclude(
            student__school_class__in=models.F('assignment__school_classes')
        )
        
        for submission in invalid_submissions:
            issues.append(f"Submission '{submission}' from student not in assignment's target classes.")
        
        # Check for assignments with teachers not qualified for subjects
        invalid_assignment_teachers = Assignment.objects.exclude(
            teacher__subjects=models.F('subject')
        )
        
        for assignment in invalid_assignment_teachers:
            issues.append(f"Assignment '{assignment}' created by teacher '{assignment.teacher}' who doesn't teach '{assignment.subject}'.")
        
        return issues
    
    @staticmethod
    def run_full_consistency_check():
        """
        Run a comprehensive consistency check across all academic models
        """
        all_issues = []
        
        all_issues.extend(DataConsistencyChecker.check_curriculum_consistency())
        all_issues.extend(DataConsistencyChecker.check_timetable_consistency())
        all_issues.extend(DataConsistencyChecker.check_assignment_consistency())
        
        return {
            'total_issues': len(all_issues),
            'issues': all_issues,
            'timestamp': timezone.now()
        }


class ReferentialIntegrityManager:
    """
    Manager for handling referential integrity operations
    """
    
    @staticmethod
    def safe_delete_with_cascade_check(instance):
        """
        Safely delete an instance after checking cascade implications
        """
        warnings = AcademicDataValidator.validate_cascade_deletion_safety(
            instance, 
            instance._meta.pk.name
        )
        
        if warnings:
            return False, warnings
        
        instance.delete()
        return True, []
    
    @staticmethod
    def update_related_records_on_change(instance, field_name, old_value, new_value):
        """
        Update related records when a foreign key reference changes
        """
        updated_records = []
        
        # This would contain logic to update related records
        # Implementation depends on specific business rules
        
        return updated_records
    
    @staticmethod
    def validate_foreign_key_constraints():
        """
        Validate all foreign key constraints across academic models
        """
        from .models import (
            Curriculum, LearningObjective, LessonPlan, CurriculumCoverage,
            AcademicEvent, ExamSchedule, Timetable, Assignment, AssignmentSubmission
        )
        
        validation_results = {}
        
        # Validate each model type
        models_to_validate = [
            (Curriculum, AcademicDataValidator.validate_curriculum_relationships),
            (LearningObjective, AcademicDataValidator.validate_learning_objective_relationships),
            (LessonPlan, AcademicDataValidator.validate_lesson_plan_relationships),
            (CurriculumCoverage, AcademicDataValidator.validate_curriculum_coverage_relationships),
            (AcademicEvent, AcademicDataValidator.validate_academic_event_relationships),
            (ExamSchedule, AcademicDataValidator.validate_exam_schedule_relationships),
            (Timetable, AcademicDataValidator.validate_timetable_relationships),
            (Assignment, AcademicDataValidator.validate_assignment_relationships),
            (AssignmentSubmission, AcademicDataValidator.validate_assignment_submission_relationships),
        ]
        
        for model_class, validator_func in models_to_validate:
            model_name = model_class.__name__
            validation_results[model_name] = {
                'total_records': 0,
                'invalid_records': 0,
                'errors': []
            }
            
            for instance in model_class.objects.all():
                validation_results[model_name]['total_records'] += 1
                errors = validator_func(instance)
                
                if errors:
                    validation_results[model_name]['invalid_records'] += 1
                    validation_results[model_name]['errors'].extend([
                        f"ID {instance.pk}: {error}" for error in errors
                    ])
        
        return validation_results