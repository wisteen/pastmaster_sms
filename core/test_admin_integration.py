"""
Unit tests for Django admin integration of Academic Management models.

Tests admin interface functionality, CKEditor integration, custom admin actions,
and inline editing capabilities.
"""

import uuid
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime, time
from decimal import Decimal

from .models import (
    User, SchoolClass, Subject, Term, Teacher, Student,
    Curriculum, LearningObjective, SyllabusContent, LessonPlan, CurriculumCoverage,
    AcademicEvent, Holiday, ExamSchedule, TimeSlot, RoomAssignment, Timetable,
    Assignment, AssignmentSubmission, SubmissionFile,
    QuestionGroup, QuestionBank, AISubscription, Attendance, Comment
)
from .admin import (
    CurriculumAdmin, LearningObjectiveAdmin, LessonPlanAdmin, CurriculumCoverageAdmin,
    AcademicEventAdmin, HolidayAdmin, ExamScheduleAdmin, TimeSlotAdmin, RoomAssignmentAdmin,
    TimetableAdmin, AssignmentAdmin, AssignmentSubmissionAdmin, SubmissionFileAdmin,
    QuestionGroupAdmin, QuestionBankAdmin, AISubscriptionAdmin, AttendanceAdmin, CommentAdmin
)


class AdminIntegrationTestCase(TestCase):
    """Base test case for admin integration tests."""
    
    def setUp(self):
        """Set up test data for admin tests."""
        unique_id = str(uuid.uuid4())[:8]
        
        # Create test users
        self.admin_user = User.objects.create_superuser(
            username=f'admin_{unique_id}',
            email=f'admin_{unique_id}@test.com',
            password='testpass123',
            role='super_admin'
        )
        
        self.teacher_user = User.objects.create_user(
            username=f'teacher_{unique_id}',
            email=f'teacher_{unique_id}@test.com',
            password='testpass123',
            role='subject_teacher'
        )
        
        self.student_user = User.objects.create_user(
            username=f'student_{unique_id}',
            email=f'student_{unique_id}@test.com',
            password='testpass123',
            role='student'
        )
        
        # Create basic test data
        self.school_class = SchoolClass.objects.create(
            name=f'Class 10A_{unique_id}',
            stream='Science'
        )
        
        self.subject = Subject.objects.create(
            name=f'Mathematics_{unique_id}',
            code=f'MATH_{unique_id}',
            pass_mark=50
        )
        
        self.term = Term.objects.create(
            name=f'Term 1_{unique_id}',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
            is_active=True
        )
        
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id=f'EMP_{unique_id}'
        )
        self.teacher.subjects.add(self.subject)
        self.teacher.classes.add(self.school_class)
        
        self.student = Student.objects.create(
            user=self.student_user,
            student_id=f'STU_{unique_id}',
            school_class=self.school_class,
            date_of_birth=timezone.now().date() - timedelta(days=6000)
        )
        
        # Set up admin client
        self.client = Client()
        self.client.login(username=self.admin_user.username, password='testpass123')
        
        # Create admin site instance for testing
        self.admin_site = AdminSite()


class CurriculumAdminTests(AdminIntegrationTestCase):
    """Test Curriculum admin functionality."""
    
    def setUp(self):
        super().setUp()
        self.curriculum_admin = CurriculumAdmin(Curriculum, self.admin_site)
        
        self.curriculum = Curr