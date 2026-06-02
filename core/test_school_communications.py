from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import (
    FeeStructure,
    PayrollStructure,
    Result,
    SchoolClass,
    SchoolMembership,
    SchoolTenant,
    StaffPayroll,
    Student,
    StudentFee,
    Subject,
    Teacher,
    Term,
)
from .models_biodata import Guardian
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SchoolCommunicationTests(TestCase):
    host = 'communication.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Communication School', slug='communication-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='communication-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = self._create_member('admin', 'super_admin', 'admin@example.com')
        self.student_user = self._create_member('student', 'student', 'student@example.com')
        self.parent = self._create_member('parent', 'parent', 'parent@example.com')
        self.teacher_user = self._create_member('teacher', 'subject_teacher', 'teacher@example.com')
        self.school_class = SchoolClass.all_objects.create(school=self.school, name='JSS 1', stream='A')
        self.term = Term.all_objects.create(
            school=self.school,
            name='First Term',
            session='2025-2026',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 15),
        )
        self.subject = Subject.all_objects.create(school=self.school, name='Mathematics', code='MTH')
        self.student = Student.all_objects.create(
            school=self.school,
            user=self.student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )
        Guardian.objects.create(
            student=self.student,
            user=self.parent,
            relationship='father',
            title='Mr',
            first_name='Test',
            last_name='Parent',
            phone_number='08012345678',
            email='parent@example.com',
            occupation='Parent',
            home_address='Home',
        )
        self.teacher = Teacher.all_objects.create(
            school=self.school,
            user=self.teacher_user,
            employee_id='TCH001',
        )
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='admin', password='password'))

    def _create_member(self, username, role, email):
        user = User.objects.create_user(username=username, password='password', role=role, email=email)
        SchoolMembership.objects.create(school=self.school, user=user, primary_role=role)
        return user

    def test_admin_can_publish_and_email_result_to_student_and_parent(self):
        Result.all_objects.create(
            student=self.student,
            subject=self.subject,
            term=self.term,
            total_score=75,
            grade='B',
            grade_point=3,
            remark='Very Good',
        )

        response = self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'result',
            'student': self.student.id,
            'term': self.term.id,
        })

        self.assertRedirects(response, reverse('core:school_admin_communications'))
        self.term.refresh_from_db()
        self.assertTrue(self.term.result_published)
        self.assertEqual({email.to[0] for email in mail.outbox}, {'student@example.com', 'parent@example.com'})
        self.assertIn('Mathematics', mail.outbox[0].alternatives[0][0])

    def test_admin_can_email_fee_statement_with_outstanding_balance(self):
        structure = FeeStructure.objects.create(
            name='First Term Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('1000.00'),
        )
        StudentFee.objects.create(
            student=self.student,
            fee_structure=structure,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('300.00'),
            discount_amount=Decimal('100.00'),
            due_date=self.term.end_date,
        )

        self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'fee_statement',
            'student': self.student.id,
        })

        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('600.00', mail.outbox[0].alternatives[0][0])

    def test_admin_can_email_teacher_payslip(self):
        structure = PayrollStructure.all_objects.create(
            school=self.school,
            name='Teachers',
            basic_salary=Decimal('1000.00'),
        )
        payroll = StaffPayroll.objects.create(
            teacher=self.teacher,
            payroll_structure=structure,
            month=date(2026, 6, 1),
            gross_salary=Decimal('1000.00'),
            net_salary=Decimal('1000.00'),
        )

        self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'payslip',
            'payroll': payroll.id,
        })

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['teacher@example.com'])
        self.assertIn('Payslip for June 2026', mail.outbox[0].subject)

    def test_admin_can_send_general_information_to_everyone_without_duplicate_parent_email(self):
        response = self.client.post(reverse('core:school_admin_communications'), {
            'message_type': 'announcement',
            'audience': 'everyone',
            'subject': 'School Reopens Monday',
            'message': 'Please check the portal for the updated calendar.',
        })

        self.assertRedirects(response, reverse('core:school_admin_communications'))
        self.assertEqual(
            {email.to[0] for email in mail.outbox},
            {'student@example.com', 'parent@example.com', 'teacher@example.com'},
        )
