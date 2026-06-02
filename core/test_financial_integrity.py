from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import Client, TestCase
from django.urls import reverse

from .models import (
    FeeStructure,
    PayrollStructure,
    Scholarship,
    ScholarshipFeeApplication,
    ScholarshipRecipient,
    SchoolClass,
    StaffPayroll,
    Student,
    StudentFee,
    Subject,
    Teacher,
    Term,
)
from .models_loans import PayrollDeduction, TeacherLoan
from .forms_school_admin import SchoolTermForm
from .services_financial_integrity import (
    clear_scholarship_fee_applications,
    sync_scholarship_fee_applications,
)
from .services_reports import ReportService


User = get_user_model()


class FinancialIntegrityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='finance-admin',
            email='finance@example.com',
            password='password',
            role='super_admin',
        )
        self.teacher_user = User.objects.create_user(
            username='teacher',
            password='password',
            role='subject_teacher',
        )
        self.student_user = User.objects.create_user(
            username='student',
            password='password',
            role='student',
        )
        self.school_class = SchoolClass.all_objects.create(name='JSS 1', stream='A')
        self.subject = Subject.all_objects.create(name='Mathematics', code='MTH')
        self.teacher = Teacher.all_objects.create(user=self.teacher_user, employee_id='TCH001')
        self.student = Student.all_objects.create(
            user=self.student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=date(2012, 1, 1),
        )

    def _create_student_fee(self, term_name, total_amount, manual_discount=Decimal('0')):
        term = Term.all_objects.create(
            name=term_name,
            session='2025-2026',
            start_date=date(2025, 9, 1) if term_name == 'First Term' else date(2026, 1, 1),
            end_date=date(2025, 12, 15) if term_name == 'First Term' else date(2026, 4, 15),
        )
        structure = FeeStructure.objects.create(
            name=f'{term_name} Fees',
            school_class=self.school_class,
            term=term,
            tuition_fee=total_amount,
        )
        return StudentFee.objects.create(
            student=self.student,
            fee_structure=structure,
            total_amount=total_amount,
            discount_amount=manual_discount,
            due_date=term.end_date,
        )

    def test_scholarship_allocates_fixed_award_once_and_revokes_only_its_own_discount(self):
        first_fee = self._create_student_fee('First Term', Decimal('200.00'))
        second_fee = self._create_student_fee('Second Term', Decimal('500.00'), Decimal('50.00'))
        scholarship = Scholarship.all_objects.create(
            name='Support Award',
            scholarship_type='need',
            amount=Decimal('300.00'),
            max_recipients=1,
            academic_year='2025-2026',
        )
        recipient = ScholarshipRecipient.objects.create(
            scholarship=scholarship,
            student=self.student,
            awarded_amount=Decimal('300.00'),
            start_date=date(2025, 9, 1),
            end_date=date(2026, 4, 30),
        )

        applications = sync_scholarship_fee_applications(recipient)
        first_fee.refresh_from_db()
        second_fee.refresh_from_db()
        self.assertEqual(len(applications), 2)
        self.assertEqual(first_fee.discount_amount, Decimal('200.00'))
        self.assertEqual(second_fee.discount_amount, Decimal('150.00'))
        self.assertEqual(
            ScholarshipFeeApplication.objects.filter(recipient=recipient).aggregate(total=Sum('amount'))['total'],
            Decimal('300.00'),
        )

        clear_scholarship_fee_applications(recipient)
        first_fee.refresh_from_db()
        second_fee.refresh_from_db()
        self.assertEqual(first_fee.discount_amount, Decimal('0.00'))
        self.assertEqual(second_fee.discount_amount, Decimal('50.00'))

    def test_loan_balance_changes_only_when_payroll_is_paid_and_final_payment_is_capped(self):
        structure = PayrollStructure.all_objects.create(name='Teachers', basic_salary=Decimal('1000.00'))
        loan = TeacherLoan.objects.create(
            teacher=self.teacher,
            amount=Decimal('150.00'),
            monthly_deduction=Decimal('100.00'),
            balance=Decimal('150.00'),
            start_date=date.today(),
        )
        payroll = StaffPayroll.objects.create(
            teacher=self.teacher,
            payroll_structure=structure,
            month=date.today().replace(day=1),
            gross_salary=structure.gross_salary,
            net_salary=Decimal('0.00'),
        )
        payroll.calculate_net_salary()
        loan.refresh_from_db()
        self.assertEqual(loan.balance, Decimal('150.00'))
        self.assertEqual(payroll.net_salary, Decimal('900.00'))

        client = Client()
        self.assertTrue(client.login(username='finance-admin', password='password'))
        response = client.post(reverse('financial:mark_payroll_paid', args=[payroll.id]))
        self.assertRedirects(response, reverse('financial:payroll_management'))
        loan.refresh_from_db()
        self.assertEqual(loan.balance, Decimal('50.00'))
        self.assertEqual(PayrollDeduction.objects.get(payroll=payroll, loan=loan).amount, Decimal('100.00'))

        next_payroll = StaffPayroll.objects.create(
            teacher=self.teacher,
            payroll_structure=structure,
            month=(date.today().replace(day=1) + timedelta(days=35)).replace(day=1),
            gross_salary=structure.gross_salary,
            net_salary=Decimal('0.00'),
        )
        next_payroll.calculate_net_salary()
        self.assertEqual(next_payroll.net_salary, Decimal('950.00'))
        client.post(reverse('financial:mark_payroll_paid', args=[next_payroll.id]))
        loan.refresh_from_db()
        self.assertEqual(loan.balance, Decimal('0.00'))
        self.assertEqual(loan.status, 'paid')

    def test_scholarship_report_excludes_completed_awards_and_keeps_renderable_dates(self):
        scholarship = Scholarship.all_objects.create(
            name='Merit Award',
            scholarship_type='merit',
            amount=Decimal('100.00'),
            max_recipients=2,
            academic_year='2025-2026',
        )
        ScholarshipRecipient.objects.create(
            scholarship=scholarship,
            student=self.student,
            awarded_amount=Decimal('100.00'),
            start_date=date(2025, 9, 1),
            end_date=date(2026, 4, 30),
        )
        report = ReportService.generate_scholarship_distribution_report(academic_year='2025-2026')
        self.assertEqual(report['summary']['total_recipients'], 1)
        self.assertIsInstance(report['recent_awards'][0]['start_date'], date)

    def test_scholarship_recipient_limit_is_enforced_by_model(self):
        scholarship = Scholarship.all_objects.create(
            name='Two Learner Award',
            scholarship_type='need',
            amount=Decimal('100.00'),
            max_recipients=2,
            academic_year='2025/2026',
        )
        second_user = User.objects.create_user(username='student-2', password='password')
        third_user = User.objects.create_user(username='student-3', password='password')
        second_student = Student.all_objects.create(
            user=second_user,
            student_id='STU002',
            school_class=self.school_class,
            date_of_birth=date(2012, 2, 1),
        )
        third_student = Student.all_objects.create(
            user=third_user,
            student_id='STU003',
            school_class=self.school_class,
            date_of_birth=date(2012, 3, 1),
        )
        recipient_data = {
            'scholarship': scholarship,
            'awarded_amount': Decimal('100.00'),
            'start_date': date(2025, 9, 1),
            'end_date': date(2026, 4, 30),
        }
        ScholarshipRecipient.objects.create(student=self.student, **recipient_data)
        ScholarshipRecipient.objects.create(student=second_student, **recipient_data)

        with self.assertRaises(ValidationError):
            ScholarshipRecipient.objects.create(student=third_student, **recipient_data)

        scholarship.refresh_from_db()
        self.assertEqual(scholarship.academic_year, '2025-2026')
        self.assertEqual(scholarship.scholarshiprecipient_set.filter(status='active').count(), 2)

    def test_scholarship_recipient_amount_cannot_exceed_award(self):
        scholarship = Scholarship.all_objects.create(
            name='Capped Award',
            scholarship_type='need',
            amount=Decimal('100.00'),
            max_recipients=1,
            academic_year='2025-2026',
        )

        with self.assertRaises(ValidationError):
            ScholarshipRecipient.objects.create(
                scholarship=scholarship,
                student=self.student,
                awarded_amount=Decimal('101.00'),
                start_date=date(2025, 9, 1),
                end_date=date(2026, 4, 30),
            )

    def test_term_setup_uses_dropdowns_and_normalizes_legacy_session_format(self):
        term = Term.all_objects.create(
            name='First Term',
            session='2026/2027',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15),
        )
        form = SchoolTermForm()

        self.assertEqual(term.session, '2026-2027')
        self.assertEqual(form.fields['name'].widget.__class__.__name__, 'Select')
        self.assertEqual(form.fields['session'].widget.__class__.__name__, 'Select')
