"""
Service classes for Academic Management System

These services handle complex business logic and calculations
for the academic management features.
"""

from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from .models import (
    Curriculum, LearningObjective, LessonPlan, CurriculumCoverage,
    Assignment, AssignmentSubmission, Holiday, AcademicEvent, ExamSchedule,
    Timetable, TimeSlot, Subject, SchoolClass, Teacher, Student, Term
)


class CoverageTracker:
    """Service for tracking and calculating curriculum coverage"""
    
    @staticmethod
    def update_coverage_for_objective(curriculum, school_class, learning_objective):
        """Update coverage tracking for a specific learning objective"""
        
        # Get or create coverage record
        coverage, created = CurriculumCoverage.objects.get_or_create(
            curriculum=curriculum,
            school_class=school_class,
            learning_objective=learning_objective,
            defaults={'total_planned_lessons': 1}
        )
        
        # Count total lessons for this objective
        total_lessons = LessonPlan.objects.filter(
            curriculum=curriculum,
            school_class=school_class,
            learning_objectives=learning_objective
        ).count()
        
        # Count completed lessons
        completed_lessons = LessonPlan.objects.filter(
            curriculum=curriculum,
            school_class=school_class,
            learning_objectives=learning_objective,
            is_completed=True
        ).count()
        
        # Update coverage
        coverage.total_planned_lessons = max(total_lessons, 1)  # Avoid division by zero
        coverage.completed_lessons = completed_lessons
        coverage.completion_percentage = (completed_lessons / coverage.total_planned_lessons) * 100
        coverage.save()
        
        return coverage
    
    @staticmethod
    def update_coverage_for_lesson_plan(lesson_plan):
        """Update coverage tracking when a lesson plan is modified"""
        
        for objective in lesson_plan.learning_objectives.all():
            CoverageTracker.update_coverage_for_objective(
                lesson_plan.curriculum,
                lesson_plan.school_class,
                objective
            )
    
    @staticmethod
    def get_coverage_report(curriculum, school_class):
        """Generate a comprehensive coverage report for a curriculum and class"""
        
        coverage_data = []
        
        # Get all learning objectives for this curriculum
        objectives = curriculum.learning_objectives.all().order_by('subject', 'order')
        
        for objective in objectives:
            coverage = CurriculumCoverage.objects.filter(
                curriculum=curriculum,
                school_class=school_class,
                learning_objective=objective
            ).first()
            
            if coverage:
                coverage_info = {
                    'objective': objective,
                    'completed_lessons': coverage.completed_lessons,
                    'total_planned_lessons': coverage.total_planned_lessons,
                    'completion_percentage': coverage.completion_percentage,
                    'is_at_risk': coverage.completion_percentage < 50,  # Less than 50% complete
                    'last_updated': coverage.last_updated
                }
            else:
                # No coverage record means no lessons planned yet
                coverage_info = {
                    'objective': objective,
                    'completed_lessons': 0,
                    'total_planned_lessons': 0,
                    'completion_percentage': 0,
                    'is_at_risk': True,
                    'last_updated': None
                }
            
            coverage_data.append(coverage_info)
        
        return coverage_data
    
    @staticmethod
    def get_at_risk_objectives(curriculum, school_class, threshold=50):
        """Get learning objectives that are at risk (below completion threshold)"""
        
        at_risk_objectives = []
        coverage_records = CurriculumCoverage.objects.filter(
            curriculum=curriculum,
            school_class=school_class,
            completion_percentage__lt=threshold
        )
        
        for coverage in coverage_records:
            at_risk_objectives.append({
                'objective': coverage.learning_objective,
                'completion_percentage': coverage.completion_percentage,
                'completed_lessons': coverage.completed_lessons,
                'total_planned_lessons': coverage.total_planned_lessons
            })
        
        return at_risk_objectives


class CalendarManager:
    """Service for managing academic calendar events and validation"""
    
    @staticmethod
    def is_holiday(date, academic_year=None):
        """Check if a given date is a holiday"""
        
        if academic_year is None:
            # Determine academic year from date
            year = date.year
            if date.month >= 9:  # September onwards is next academic year
                academic_year = f"{year}-{year + 1}"
            else:
                academic_year = f"{year - 1}-{year}"
        
        return Holiday.objects.filter(
            date=date,
            academic_year=academic_year
        ).exists()
    
    @staticmethod
    def is_instructional_day(date, academic_year=None):
        """Check if a given date is an instructional day (not holiday/weekend)"""
        
        # Check if it's a weekend (Saturday=5, Sunday=6)
        if date.weekday() >= 5:
            return False
        
        # Check if it's a holiday
        if CalendarManager.is_holiday(date, academic_year):
            return False
        
        return True
    
    @staticmethod
    def get_next_instructional_day(date, academic_year=None):
        """Get the next instructional day after the given date"""
        
        next_date = date + timedelta(days=1)
        
        while not CalendarManager.is_instructional_day(next_date, academic_year):
            next_date += timedelta(days=1)
            
            # Prevent infinite loop (max 30 days ahead)
            if (next_date - date).days > 30:
                break
        
        return next_date
    
    @staticmethod
    def validate_assignment_due_date(due_date):
        """Validate that an assignment due date is on an instructional day"""
        
        academic_year = CalendarManager._get_academic_year_from_date(due_date)
        
        if not CalendarManager.is_instructional_day(due_date.date(), academic_year):
            return False, "Assignment due date cannot be on a holiday or weekend."
        
        return True, ""
    
    @staticmethod
    def validate_exam_schedule(exam_schedule_data):
        """Validate exam schedule for conflicts and constraints"""
        
        errors = []
        exam_date = exam_schedule_data['exam_date']
        duration = exam_schedule_data['duration']
        room = exam_schedule_data.get('room')
        invigilator = exam_schedule_data.get('invigilator')
        school_class = exam_schedule_data['school_class']
        exclude_exam = exam_schedule_data.get('exclude_exam')
        
        # Check if exam date is on a holiday
        if CalendarManager.is_holiday(exam_date.date()):
            errors.append("Exam cannot be scheduled on a holiday.")
        
        # Check for room conflicts
        if room:
            if CalendarManager.check_exam_room_conflict(exam_date, duration, room, exclude_exam):
                errors.append(f"Room {room} is already booked for another exam during this time.")
        
        # Check for invigilator conflicts
        if invigilator:
            if CalendarManager.check_invigilator_conflict(exam_date, duration, invigilator, exclude_exam):
                errors.append(f"Invigilator {invigilator} is already assigned to another exam during this time.")
        
        # Check for class conflicts
        if CalendarManager.check_class_exam_conflict(exam_date, duration, school_class, exclude_exam):
            errors.append(f"Class {school_class} already has an exam scheduled during this time.")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def check_exam_room_conflict(exam_date, duration, room, exclude_exam=None):
        """Check if a room has an exam conflict at the given time"""
        
        exam_end_time = exam_date + duration
        
        conflict_query = ExamSchedule.objects.filter(
            room=room,
            exam_date__lt=exam_end_time,
            exam_date__gte=exam_date - duration
        )
        
        if exclude_exam:
            conflict_query = conflict_query.exclude(pk=exclude_exam.pk)
        
        return conflict_query.exists()
    
    @staticmethod
    def check_invigilator_conflict(exam_date, duration, invigilator, exclude_exam=None):
        """Check if an invigilator has an exam conflict at the given time"""
        
        exam_end_time = exam_date + duration
        
        conflict_query = ExamSchedule.objects.filter(
            invigilator=invigilator,
            exam_date__lt=exam_end_time,
            exam_date__gte=exam_date - duration
        )
        
        if exclude_exam:
            conflict_query = conflict_query.exclude(pk=exclude_exam.pk)
        
        return conflict_query.exists()
    
    @staticmethod
    def check_class_exam_conflict(exam_date, duration, school_class, exclude_exam=None):
        """Check if a class has an exam conflict at the given time"""
        
        exam_end_time = exam_date + duration
        
        conflict_query = ExamSchedule.objects.filter(
            school_class=school_class,
            exam_date__lt=exam_end_time,
            exam_date__gte=exam_date - duration
        )
        
        if exclude_exam:
            conflict_query = conflict_query.exclude(pk=exclude_exam.pk)
        
        return conflict_query.exists()
    
    @staticmethod
    def generate_recurring_events(base_event):
        """Generate recurring event instances based on pattern"""
        
        if not base_event.is_recurring or not base_event.recurrence_pattern:
            return []
        
        events = []
        current_date = base_event.start_date
        
        # Calculate end of academic year
        academic_year_parts = base_event.academic_year.split('-')
        end_year = int(academic_year_parts[1])
        end_of_year = timezone.datetime(
            year=end_year,
            month=8,
            day=31,
            hour=23,
            minute=59,
            second=59,
            tzinfo=current_date.tzinfo
        )
        
        # Generate events for the academic year (limit to prevent infinite loops)
        max_events = 100
        event_count = 0
        
        while current_date <= end_of_year and event_count < max_events:
            # Move to next occurrence
            if base_event.recurrence_pattern == 'daily':
                current_date += timedelta(days=1)
            elif base_event.recurrence_pattern == 'weekly':
                current_date += timedelta(weeks=1)
            elif base_event.recurrence_pattern == 'monthly':
                # Add one month (handle month boundaries)
                try:
                    if current_date.month == 12:
                        current_date = current_date.replace(year=current_date.year + 1, month=1)
                    else:
                        current_date = current_date.replace(month=current_date.month + 1)
                except ValueError:
                    # Handle cases like Jan 31 -> Feb 31 (doesn't exist)
                    if current_date.month == 12:
                        current_date = current_date.replace(year=current_date.year + 1, month=1, day=28)
                    else:
                        current_date = current_date.replace(month=current_date.month + 1, day=28)
            elif base_event.recurrence_pattern == 'yearly':
                try:
                    current_date = current_date.replace(year=current_date.year + 1)
                except ValueError:
                    # Handle leap year edge case (Feb 29)
                    current_date = current_date.replace(year=current_date.year + 1, day=28)
            
            if current_date <= end_of_year:
                # Calculate end date for this instance
                duration = base_event.end_date - base_event.start_date
                end_date = current_date + duration
                
                events.append({
                    'title': base_event.title,
                    'description': base_event.description,
                    'event_type': base_event.event_type,
                    'start_date': current_date,
                    'end_date': end_date,
                    'academic_year': base_event.academic_year,
                    'created_by': base_event.created_by
                })
                
                event_count += 1
        
        return events
    
    @staticmethod
    def _get_academic_year_from_date(date):
        """Helper method to determine academic year from a date"""
        year = date.year
        if date.month >= 9:  # September onwards is next academic year
            return f"{year}-{year + 1}"
        else:
            return f"{year - 1}-{year}"


class TimetableBuilder:
    """Service for building and validating timetables"""
    
    @staticmethod
    def check_teacher_conflict(teacher, time_slot, term, academic_year, exclude_timetable=None):
        """Check if a teacher has a conflict at the given time slot"""
        
        conflict_query = Timetable.objects.filter(
            teacher=teacher,
            time_slot=time_slot,
            term=term,
            academic_year=academic_year,
            is_active=True
        )
        
        if exclude_timetable:
            conflict_query = conflict_query.exclude(pk=exclude_timetable.pk)
        
        return conflict_query.exists()
    
    @staticmethod
    def check_room_conflict(room, time_slot, term, academic_year, exclude_timetable=None):
        """Check if a room has a conflict at the given time slot"""
        
        conflict_query = Timetable.objects.filter(
            room=room,
            time_slot=time_slot,
            term=term,
            academic_year=academic_year,
            is_active=True
        )
        
        if exclude_timetable:
            conflict_query = conflict_query.exclude(pk=exclude_timetable.pk)
        
        return conflict_query.exists()
    
    @staticmethod
    def validate_timetable_entry(timetable_data):
        """Validate a timetable entry for conflicts"""
        
        errors = []
        
        # Check teacher conflict
        if TimetableBuilder.check_teacher_conflict(
            timetable_data['teacher'],
            timetable_data['time_slot'],
            timetable_data['term'],
            timetable_data['academic_year'],
            timetable_data.get('exclude_timetable')
        ):
            errors.append(f"Teacher {timetable_data['teacher']} is already assigned during {timetable_data['time_slot']}")
        
        # Check room conflict
        if TimetableBuilder.check_room_conflict(
            timetable_data['room'],
            timetable_data['time_slot'],
            timetable_data['term'],
            timetable_data['academic_year'],
            timetable_data.get('exclude_timetable')
        ):
            errors.append(f"Room {timetable_data['room'].room_name} is already booked during {timetable_data['time_slot']}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_teacher_schedule(teacher, term, academic_year):
        """Get a teacher's complete schedule for a term"""
        
        schedule = Timetable.objects.filter(
            teacher=teacher,
            term=term,
            academic_year=academic_year,
            is_active=True
        ).select_related('time_slot', 'subject', 'school_class', 'room').order_by(
            'time_slot__day_of_week', 'time_slot__start_time'
        )
        
        return schedule
    
    @staticmethod
    def get_class_schedule(school_class, term, academic_year):
        """Get a class's complete schedule for a term"""
        
        schedule = Timetable.objects.filter(
            school_class=school_class,
            term=term,
            academic_year=academic_year,
            is_active=True
        ).select_related('time_slot', 'subject', 'teacher', 'room').order_by(
            'time_slot__day_of_week', 'time_slot__start_time'
        )
        
        return schedule


class AssignmentTracker:
    """Service for tracking assignment submissions and deadlines"""
    
    @staticmethod
    def get_submission_statistics(assignment):
        """Get submission statistics for an assignment"""
        
        total_students = 0
        for school_class in assignment.school_classes.all():
            total_students += Student.objects.filter(school_class=school_class).count()
        
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)
        submitted_count = submissions.count()
        late_submissions = submissions.filter(is_late=True).count()
        on_time_submissions = submitted_count - late_submissions
        
        return {
            'total_students': total_students,
            'submitted_count': submitted_count,
            'on_time_submissions': on_time_submissions,
            'late_submissions': late_submissions,
            'submission_rate': (submitted_count / total_students * 100) if total_students > 0 else 0,
            'pending_submissions': total_students - submitted_count
        }
    
    @staticmethod
    def get_upcoming_deadlines(teacher, days_ahead=7):
        """Get upcoming assignment deadlines for a teacher"""
        
        cutoff_date = timezone.now() + timedelta(days=days_ahead)
        
        assignments = Assignment.objects.filter(
            teacher=teacher,
            due_date__gte=timezone.now(),
            due_date__lte=cutoff_date
        ).order_by('due_date')
        
        deadline_info = []
        for assignment in assignments:
            stats = AssignmentTracker.get_submission_statistics(assignment)
            deadline_info.append({
                'assignment': assignment,
                'days_remaining': (assignment.due_date.date() - timezone.now().date()).days,
                'submission_stats': stats
            })
        
        return deadline_info
    
    @staticmethod
    def get_student_assignments(student, include_completed=False):
        """Get assignments for a specific student"""
        
        assignments = Assignment.objects.filter(
            school_classes=student.school_class
        ).order_by('due_date')
        
        assignment_info = []
        for assignment in assignments:
            try:
                submission = AssignmentSubmission.objects.get(
                    assignment=assignment,
                    student=student
                )
                is_submitted = True
                submission_date = submission.submitted_at
                is_late = submission.is_late
            except AssignmentSubmission.DoesNotExist:
                is_submitted = False
                submission_date = None
                is_late = False
            
            # Skip completed assignments if not requested
            if is_submitted and not include_completed:
                continue
            
            assignment_info.append({
                'assignment': assignment,
                'is_submitted': is_submitted,
                'submission_date': submission_date,
                'is_late': is_late,
                'is_overdue': assignment.is_overdue() and not is_submitted,
                'time_remaining': assignment.time_remaining()
            })
        
        return assignment_info


class ReportGenerator:
    """Service for generating various academic reports"""
    
    @staticmethod
    def generate_curriculum_coverage_report(curriculum, school_class, at_risk_threshold=50):
        """Generate a detailed curriculum coverage report with at-risk identification"""
        
        coverage_data = CoverageTracker.get_coverage_report(curriculum, school_class)
        
        # Enhanced coverage data with completion dates and remaining objectives
        enhanced_coverage_data = []
        for item in coverage_data:
            objective = item['objective']
            
            # Get completion dates for lessons related to this objective
            completed_lessons = LessonPlan.objects.filter(
                curriculum=curriculum,
                school_class=school_class,
                learning_objectives=objective,
                is_completed=True
            ).order_by('completion_date')
            
            # Get remaining (incomplete) lessons
            remaining_lessons = LessonPlan.objects.filter(
                curriculum=curriculum,
                school_class=school_class,
                learning_objectives=objective,
                is_completed=False
            ).order_by('created_at')
            
            # Calculate estimated completion date based on current progress
            estimated_completion_date = None
            if remaining_lessons.exists() and completed_lessons.exists():
                # Calculate average time between lesson completions
                if completed_lessons.count() > 1:
                    completion_dates = [lesson.completion_date for lesson in completed_lessons if lesson.completion_date]
                    if len(completion_dates) > 1:
                        total_days = (completion_dates[-1] - completion_dates[0]).days
                        avg_days_per_lesson = total_days / (len(completion_dates) - 1)
                        
                        # Estimate completion date for remaining lessons
                        last_completion = completion_dates[-1]
                        remaining_count = remaining_lessons.count()
                        estimated_completion_date = last_completion + timedelta(days=avg_days_per_lesson * remaining_count)
            
            enhanced_item = {
                **item,
                'completed_lesson_dates': [lesson.completion_date for lesson in completed_lessons if lesson.completion_date],
                'remaining_lessons': list(remaining_lessons.values('id', 'title', 'created_at')),
                'remaining_lessons_count': remaining_lessons.count(),
                'estimated_completion_date': estimated_completion_date,
                'is_at_risk': item['completion_percentage'] < at_risk_threshold,
                'risk_level': ReportGenerator._calculate_risk_level(item['completion_percentage'], at_risk_threshold)
            }
            enhanced_coverage_data.append(enhanced_item)
        
        # Calculate overall statistics
        total_objectives = len(enhanced_coverage_data)
        completed_objectives = sum(1 for item in enhanced_coverage_data if item['completion_percentage'] >= 100)
        at_risk_objectives = sum(1 for item in enhanced_coverage_data if item['is_at_risk'])
        high_risk_objectives = sum(1 for item in enhanced_coverage_data if item['risk_level'] == 'high')
        
        overall_completion = sum(item['completion_percentage'] for item in enhanced_coverage_data) / total_objectives if total_objectives > 0 else 0
        
        # Identify objectives by subject for better organization
        objectives_by_subject = {}
        for item in enhanced_coverage_data:
            subject_name = item['objective'].subject.name
            if subject_name not in objectives_by_subject:
                objectives_by_subject[subject_name] = []
            objectives_by_subject[subject_name].append(item)
        
        return {
            'curriculum': curriculum,
            'school_class': school_class,
            'coverage_data': enhanced_coverage_data,
            'objectives_by_subject': objectives_by_subject,
            'statistics': {
                'total_objectives': total_objectives,
                'completed_objectives': completed_objectives,
                'at_risk_objectives': at_risk_objectives,
                'high_risk_objectives': high_risk_objectives,
                'overall_completion_percentage': round(overall_completion, 2),
                'at_risk_threshold': at_risk_threshold
            },
            'generated_at': timezone.now()
        }
    
    @staticmethod
    def _calculate_risk_level(completion_percentage, threshold):
        """Calculate risk level based on completion percentage"""
        if completion_percentage >= 100:
            return 'completed'
        elif completion_percentage >= threshold:
            return 'on_track'
        elif completion_percentage >= threshold * 0.5:
            return 'medium'
        else:
            return 'high'
    
    @staticmethod
    def generate_at_risk_objectives_report(curriculum, school_class, threshold=50):
        """Generate a focused report on at-risk learning objectives"""
        
        at_risk_objectives = CoverageTracker.get_at_risk_objectives(curriculum, school_class, threshold)
        
        # Enhanced at-risk data with actionable insights
        enhanced_at_risk_data = []
        for item in at_risk_objectives:
            objective = item['objective']
            
            # Get lessons that should be completed but aren't
            overdue_lessons = LessonPlan.objects.filter(
                curriculum=curriculum,
                school_class=school_class,
                learning_objectives=objective,
                is_completed=False,
                created_at__lt=timezone.now() - timedelta(days=7)  # Created more than a week ago
            )
            
            # Get the most recent lesson activity
            latest_lesson = LessonPlan.objects.filter(
                curriculum=curriculum,
                school_class=school_class,
                learning_objectives=objective
            ).order_by('-updated_at').first()
            
            enhanced_item = {
                **item,
                'overdue_lessons_count': overdue_lessons.count(),
                'overdue_lessons': list(overdue_lessons.values('id', 'title', 'created_at')),
                'latest_lesson_activity': latest_lesson.updated_at if latest_lesson else None,
                'days_since_activity': (timezone.now() - latest_lesson.updated_at).days if latest_lesson else None,
                'urgency_score': ReportGenerator._calculate_urgency_score(item['completion_percentage'], overdue_lessons.count())
            }
            enhanced_at_risk_data.append(enhanced_item)
        
        # Sort by urgency score (highest first)
        enhanced_at_risk_data.sort(key=lambda x: x['urgency_score'], reverse=True)
        
        return {
            'curriculum': curriculum,
            'school_class': school_class,
            'at_risk_objectives': enhanced_at_risk_data,
            'threshold': threshold,
            'total_at_risk': len(enhanced_at_risk_data),
            'generated_at': timezone.now()
        }
    
    @staticmethod
    def _calculate_urgency_score(completion_percentage, overdue_lessons_count):
        """Calculate urgency score for prioritizing at-risk objectives"""
        # Lower completion percentage = higher urgency
        completion_urgency = (100 - completion_percentage) / 100
        
        # More overdue lessons = higher urgency
        overdue_urgency = min(overdue_lessons_count / 5, 1)  # Cap at 1.0
        
        # Combine factors (weighted)
        urgency_score = (completion_urgency * 0.7) + (overdue_urgency * 0.3)
        
        return round(urgency_score * 100, 2)  # Return as percentage
    
    @staticmethod
    def generate_assignment_submission_statistics(teacher=None, school_class=None, term=None, subject=None):
        """Generate comprehensive assignment submission statistics"""
        
        # Build query based on filters
        assignments_query = Assignment.objects.all()
        
        if teacher:
            assignments_query = assignments_query.filter(teacher=teacher)
        if school_class:
            assignments_query = assignments_query.filter(school_classes=school_class)
        if subject:
            assignments_query = assignments_query.filter(subject=subject)
        if term:
            assignments_query = assignments_query.filter(
                due_date__gte=term.start_date,
                due_date__lte=term.end_date
            )
        
        assignments = assignments_query.order_by('-created_at')
        
        # Calculate detailed statistics
        assignment_statistics = []
        total_assignments = 0
        total_students_affected = 0
        total_submissions = 0
        total_late_submissions = 0
        total_on_time_submissions = 0
        
        for assignment in assignments:
            stats = AssignmentTracker.get_submission_statistics(assignment)
            
            # Calculate additional metrics
            late_submission_rate = (stats['late_submissions'] / stats['total_students'] * 100) if stats['total_students'] > 0 else 0
            on_time_rate = (stats['on_time_submissions'] / stats['total_students'] * 100) if stats['total_students'] > 0 else 0
            
            # Get submission timeline data
            submissions = AssignmentSubmission.objects.filter(assignment=assignment).order_by('submitted_at')
            submission_timeline = []
            for submission in submissions:
                days_before_due = (assignment.due_date - submission.submitted_at).days
                submission_timeline.append({
                    'student_id': submission.student.id,
                    'student_name': submission.student.user.get_full_name(),
                    'submitted_at': submission.submitted_at,
                    'days_before_due': days_before_due,
                    'is_late': submission.is_late
                })
            
            assignment_data = {
                'assignment': assignment,
                'statistics': {
                    **stats,
                    'late_submission_rate': round(late_submission_rate, 2),
                    'on_time_rate': round(on_time_rate, 2),
                    'completion_rate': stats['submission_rate']
                },
                'submission_timeline': submission_timeline,
                'is_overdue': assignment.is_overdue(),
                'days_since_due': (timezone.now() - assignment.due_date).days if assignment.is_overdue() else None
            }
            assignment_statistics.append(assignment_data)
            
            # Aggregate totals
            total_assignments += 1
            total_students_affected += stats['total_students']
            total_submissions += stats['submitted_count']
            total_late_submissions += stats['late_submissions']
            total_on_time_submissions += stats['on_time_submissions']
        
        # Calculate overall statistics
        overall_submission_rate = (total_submissions / total_students_affected * 100) if total_students_affected > 0 else 0
        overall_late_rate = (total_late_submissions / total_submissions * 100) if total_submissions > 0 else 0
        overall_on_time_rate = (total_on_time_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        # Identify patterns and insights
        insights = ReportGenerator._generate_submission_insights(assignment_statistics)
        
        return {
            'filters': {
                'teacher': teacher,
                'school_class': school_class,
                'term': term,
                'subject': subject
            },
            'assignments': assignment_statistics,
            'summary': {
                'total_assignments': total_assignments,
                'total_students_affected': total_students_affected,
                'total_submissions': total_submissions,
                'total_late_submissions': total_late_submissions,
                'total_on_time_submissions': total_on_time_submissions,
                'overall_submission_rate': round(overall_submission_rate, 2),
                'overall_late_rate': round(overall_late_rate, 2),
                'overall_on_time_rate': round(overall_on_time_rate, 2)
            },
            'insights': insights,
            'generated_at': timezone.now()
        }
    
    @staticmethod
    def _generate_submission_insights(assignment_statistics):
        """Generate insights from assignment submission patterns"""
        
        insights = []
        
        if not assignment_statistics:
            return insights
        
        # Identify assignments with low submission rates
        low_submission_assignments = [
            item for item in assignment_statistics 
            if item['statistics']['submission_rate'] < 70
        ]
        
        if low_submission_assignments:
            insights.append({
                'type': 'low_submission_rate',
                'message': f"{len(low_submission_assignments)} assignment(s) have submission rates below 70%",
                'assignments': [item['assignment'].title for item in low_submission_assignments[:3]]  # Show top 3
            })
        
        # Identify assignments with high late submission rates
        high_late_assignments = [
            item for item in assignment_statistics 
            if item['statistics']['late_submission_rate'] > 30
        ]
        
        if high_late_assignments:
            insights.append({
                'type': 'high_late_rate',
                'message': f"{len(high_late_assignments)} assignment(s) have late submission rates above 30%",
                'assignments': [item['assignment'].title for item in high_late_assignments[:3]]
            })
        
        # Identify overdue assignments with pending submissions
        overdue_with_pending = [
            item for item in assignment_statistics 
            if item['is_overdue'] and item['statistics']['pending_submissions'] > 0
        ]
        
        if overdue_with_pending:
            insights.append({
                'type': 'overdue_pending',
                'message': f"{len(overdue_with_pending)} overdue assignment(s) still have pending submissions",
                'assignments': [item['assignment'].title for item in overdue_with_pending[:3]]
            })
        
        # Calculate average submission rates by subject
        subject_stats = {}
        for item in assignment_statistics:
            subject_name = item['assignment'].subject.name
            if subject_name not in subject_stats:
                subject_stats[subject_name] = {'total_rate': 0, 'count': 0}
            subject_stats[subject_name]['total_rate'] += item['statistics']['submission_rate']
            subject_stats[subject_name]['count'] += 1
        
        # Find subjects with consistently low submission rates
        low_performing_subjects = []
        for subject, stats in subject_stats.items():
            avg_rate = stats['total_rate'] / stats['count']
            if avg_rate < 75 and stats['count'] >= 2:  # At least 2 assignments
                low_performing_subjects.append((subject, round(avg_rate, 2)))
        
        if low_performing_subjects:
            insights.append({
                'type': 'subject_performance',
                'message': f"Subjects with low average submission rates: {', '.join([f'{s[0]} ({s[1]}%)' for s in low_performing_subjects[:3]])}"
            })
        
        return insights
    
    @staticmethod
    def generate_assignment_summary_report(teacher, term=None):
        """Generate an assignment summary report for a teacher"""
        
        assignments_query = Assignment.objects.filter(teacher=teacher)
        
        if term:
            # Filter by term dates
            assignments_query = assignments_query.filter(
                due_date__gte=term.start_date,
                due_date__lte=term.end_date
            )
        
        assignments = assignments_query.order_by('-created_at')
        
        assignment_data = []
        total_submissions = 0
        total_students = 0
        
        for assignment in assignments:
            stats = AssignmentTracker.get_submission_statistics(assignment)
            assignment_data.append({
                'assignment': assignment,
                'statistics': stats
            })
            total_submissions += stats['submitted_count']
            total_students += stats['total_students']
        
        overall_submission_rate = (total_submissions / total_students * 100) if total_students > 0 else 0
        
        return {
            'teacher': teacher,
            'term': term,
            'assignments': assignment_data,
            'summary': {
                'total_assignments': len(assignment_data),
                'total_students': total_students,
                'total_submissions': total_submissions,
                'overall_submission_rate': round(overall_submission_rate, 2)
            }
        }