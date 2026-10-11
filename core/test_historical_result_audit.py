from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .models import (
    ComponentResult,
    Result,
    ResultComponent,
    SchoolClass,
    SchoolTenant,
    Student,
    StudentTermPlacement,
    Subject,
    Term,
)


User = get_user_model()


class HistoricalResultAuditTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Audit School', slug='audit-school')
        self.old_class = SchoolClass.all_objects.create(school=self.school, name='Basic 4')
        self.new_class = SchoolClass.all_objects.create(school=self.school, name='Basic 5')
        user = User.objects.create_user(username='audit-student', role='student')
        self.student = Student.all_objects.create(
            school=self.school,
            user=user,
            student_id='AUD-1',
            school_class=self.new_class,
            promoted_from=self.old_class,
            promoted_to=self.new_class,
            is_promoted=True,
            date_of_birth=date(2013, 1, 1),
        )
        self.term = Term.all_objects.create(
            school=self.school,
            name='Third Term',
            session='2025-2026',
            start_date=date(2026, 4, 1),
            end_date=date(2026, 7, 1),
        )
        self.subject = Subject.all_objects.create(
            school=self.school,
            name='Mathematics',
            code='MTH',
        )
        Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=self.term,
            total_score=60,
        )

    def test_audit_reports_missing_placement_without_changing_data(self):
        output = StringIO()

        call_command('audit_historical_results', school='audit-school', stdout=output)

        self.assertIn('Promoted result terms without placements: 1', output.getvalue())
        self.assertFalse(StudentTermPlacement.all_objects.exists())

    def test_audit_reports_mark_outside_recorded_class(self):
        StudentTermPlacement.all_objects.create(
            student=self.student,
            term=self.term,
            school_class=self.old_class,
        )
        component = ResultComponent.all_objects.create(
            school_class=self.new_class,
            subject=self.subject,
            component_name='Exam',
            weight=70,
            max_score=70,
        )
        ComponentResult.all_objects.create(
            student=self.student,
            term=self.term,
            component=component,
            score=50,
        )
        output = StringIO()

        call_command('audit_historical_results', school='audit-school', stdout=output)

        self.assertIn('Component marks outside recorded placements: 1', output.getvalue())
