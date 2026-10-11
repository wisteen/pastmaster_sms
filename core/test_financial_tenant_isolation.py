from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    FeeStructure,
    SchoolClass,
    SchoolMembership,
    SchoolTenant,
    Scholarship,
    ScholarshipRecipient,
    Student,
    StudentFee,
    Term,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense
from .views_financial import record_payment


User = get_user_model()


class FinancialTenantIsolationTests(TestCase):
    host = 'finance-a.testserver'

    def setUp(self):
        self.school_a = self._create_school('Finance A', 'finance-a', self.host)
        self.school_b = self._create_school('Finance B', 'finance-b', 'finance-b.testserver')

        self.admin = User.objects.create_user(username='finance-admin', password='password', role='super_admin')
        SchoolMembership.objects.create(school=self.school_a, user=self.admin, primary_role='super_admin')

        self.client = Client(HTTP_HOST=self.host)
        self.factory = RequestFactory(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='finance-admin', password='password'))

        self.a_fee = self._create_student_fee(
            self.school_a,
            class_name='JSS 1',
            username='alpha-student',
            first_name='Alpha',
            last_name='Student',
            amount=Decimal('1000.00'),
        )
        self.b_fee = self._create_student_fee(
            self.school_b,
            class_name='JSS 2',
            username='beta-student',
            first_name='Beta',
            last_name='Student',
            amount=Decimal('5000.00'),
        )
        self.a_scholarship = Scholarship.all_objects.create(
            school=self.school_a,
            name='Alpha Scholarship',
            scholarship_type='merit',
            amount=Decimal('200.00'),
            max_recipients=2,
            academic_year='2024-2025',
        )
        self.b_scholarship = Scholarship.all_objects.create(
            school=self.school_b,
            name='Beta Scholarship',
            scholarship_type='need',
            amount=Decimal('300.00'),
            max_recipients=2,
            academic_year='2024-2025',
        )
        ScholarshipRecipient.all_objects.create(
            scholarship=self.a_scholarship,
            student=self.a_fee.student,
            awarded_amount=Decimal('100.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )
        ScholarshipRecipient.all_objects.create(
            scholarship=self.b_scholarship,
            student=self.b_fee.student,
            awarded_amount=Decimal('100.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
        )

    def _create_school(self, name, slug, host):
        school = SchoolTenant.objects.create(name=name, slug=slug)
        SchoolDomain.objects.create(school=school, domain=host)
        SystemLicense.all_objects.create(
            school=school,
            school_name=name,
            license_key=f'{slug}-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        return school

    def _create_student_fee(self, school, class_name, username, first_name, last_name, amount):
        user = User.objects.create_user(
            username=username,
            password='password',
            role='student',
            first_name=first_name,
            last_name=last_name,
        )
        school_class = SchoolClass.all_objects.create(school=school, name=class_name)
        term = Term.all_objects.create(
            school=school,
            name='First Term',
            session='2024-2025',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
        )
        student = Student.all_objects.create(
            school=school,
            user=user,
            student_id=f'{username.upper()}-001',
            school_class=school_class,
            date_of_birth=date(2012, 1, 1),
            gender='M',
        )
        fee_structure = FeeStructure.all_objects.create(
            name=f'{class_name} Fees',
            school_class=school_class,
            term=term,
            tuition_fee=amount,
        )
        return StudentFee.all_objects.create(
            student=student,
            fee_structure=fee_structure,
            total_amount=amount,
            due_date=timezone.now().date() + timedelta(days=30),
        )

    def test_financial_dashboard_totals_are_school_scoped_and_scholarship_visible(self):
        response = self.client.get(reverse('financial:financial_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_fees_due'], Decimal('1000.00'))
        self.assertContains(response, reverse('financial:scholarship_management'))
        self.assertContains(response, 'Scholarships')

    def test_fee_management_only_shows_active_school_fees(self):
        response = self.client.get(reverse('financial:fee_management'))

        self.assertEqual(response.status_code, 200)
        fee_ids = {fee.id for fee in response.context['student_fees'].object_list}
        self.assertIn(self.a_fee.id, fee_ids)
        self.assertNotIn(self.b_fee.id, fee_ids)

    def test_record_payment_rejects_other_school_student_fee(self):
        request = self.factory.post(reverse('financial:record_payment'), {
            'student_fee_id': self.b_fee.id,
            'amount': '100.00',
            'payment_method': 'cash',
            'reference_number': 'CROSS-SCHOOL',
            'notes': '',
        })
        request.user = self.admin
        request.school = self.school_a

        with self.assertRaises(Http404):
            record_payment(request)

        self.b_fee.refresh_from_db()
        self.assertEqual(self.b_fee.paid_amount, Decimal('0.00'))

    def test_student_autocomplete_is_school_scoped(self):
        response = self.client.get(reverse('financial:autocomplete_students_ajax'), {'term': 'Student'})

        self.assertEqual(response.status_code, 200)
        names = [item['name'] for item in response.json()['suggestions']]
        self.assertIn('Alpha Student', names)
        self.assertNotIn('Beta Student', names)

    def test_export_financial_report_is_school_scoped(self):
        response = self.client.get(reverse('financial:export_financial_report'))
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Alpha Student', body)
        self.assertNotIn('Beta Student', body)

    def test_scholarship_management_is_school_scoped(self):
        response = self.client.get(reverse('financial:scholarship_management'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Scholarship')
        self.assertNotContains(response, 'Beta Scholarship')
