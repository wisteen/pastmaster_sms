"""
Unit Tests for Financial Reconciliation Services

Tests the reconciliation service classes including payment verification,
payroll validation, scholarship application checks, and balance verification.
"""

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    FeeStructure, StudentFee, FeePayment, Student, Teacher,
    StaffPayroll, PayrollStructure, Scholarship, ScholarshipRecipient,
    FinancialTransaction, SchoolClass, Term, Subject
)
from .services_reconciliation import (
    ReconciliationService, DiscrepancyDetector, ReconciliationReporter,
    ReconciliationScheduler
)

User = get_user_model()


class ReconciliationServiceTestCase(TestCase):
    """Test cases for ReconciliationService"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            role='super_admin'
        )
        
        self.teacher_user = User.objects.create_user(
            username='teacher1',
            email='teacher@test.com',
            password='testpass123',
            role='subject_teacher'
        )
        
        self.student_user = User.objects.create_user(
            username='student1',
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        
        # Create school class
        self.school_class = SchoolClass.objects.create(
            name='Grade 10',
            stream='A'
        )
        
        # Create term
        self.term = Term.objects.create(
            name='Term 1 2024',
            start_date=timezone.now().date() - timedelta(days=60),
            end_date=timezone.now().date() + timedelta(days=30),
            is_active=True
        )
        
        # Create student
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=timezone.now().date() - timedelta(days=365*15)
        )
        
        # Create teacher
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='TCH001'
        )
        
        # Create fee structure
        self.fee_structure = FeeStructure.objects.create(
            name='Standard Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('10000.00'),
            development_fee=Decimal('2000.00'),
            exam_fee=Decimal('1000.00'),
            library_fee=Decimal('500.00'),
            sports_fee=Decimal('500.00'),
            other_fees=Decimal('0.00')
        )
        
        # Create student fee
        self.student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            total_amount=self.fee_structure.total_fee,
            due_date=timezone.now().date() + timedelta(days=30)
        )
        
        # Create payroll structure
        self.payroll_structure = PayrollStructure.objects.create(
            name='Standard Payroll',
            basic_salary=Decimal('50000.00'),
            house_allowance=Decimal('10000.00'),
            transport_allowance=Decimal('5000.00'),
            medical_allowance=Decimal('3000.00'),
            other_allowances=Decimal('2000.00'),
            tax_rate=Decimal('10.00'),
            pension_rate=Decimal('5.00')
        )
        
        # Create payroll
        self.payroll = StaffPayroll.objects.create(
            teacher=self.teacher,
            payroll_structure=self.payroll_structure,
            month=timezone.now().date().replace(day=1),
            gross_salary=self.payroll_structure.gross_salary,
            net_salary=Decimal('0.00')
        )
        self.payroll.calculate_net_salary()
        
    def test_payment_collection_reconciliation_balanced(self):
        """Test payment collection reconciliation with balanced accounts"""
        # Create payment
        payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('5000.00'),
            payment_method='cash',
            received_by=self.admin_user
        )
        
        # Run reconciliation
        result = ReconciliationService.reconcile_payment_collections()
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.reconciliation_type, 'payment_collections')
        self.assertTrue(result.is_balanced)
        self.assertEqual(result.total_discrepancies, 0)
        
    def test_payment_collection_reconciliation_with_discrepancy(self):
        """Test payment collection reconciliation with discrepancy"""
        # Create payment
        payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('5000.00'),
            payment_method='cash',
            received_by=self.admin_user
        )
        
        # Manually create discrepancy by changing paid_amount
        self.student_fee.paid_amount = Decimal('4000.00')
        self.student_fee.save()
        
        # Run reconciliation
        result = ReconciliationService.reconcile_payment_collections()
        
        # Verify discrepancy detected
        self.assertFalse(result.is_balanced)
        self.assertGreater(result.total_discrepancies, 0)
        self.assertGreater(len(result.discrepancies), 0)
        
    def test_payroll_calculation_reconciliation_correct(self):
        """Test payroll calculation reconciliation with correct calculations"""
        # Run reconciliation
        result = ReconciliationService.reconcile_payroll_calculations()
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.reconciliation_type, 'payroll_calculations')
        self.assertTrue(result.is_balanced)
        self.assertEqual(result.total_discrepancies, 0)
        
    def test_payroll_calculation_reconciliation_with_error(self):
        """Test payroll calculation reconciliation with calculation error"""
        # Manually create calculation error
        self.payroll.net_salary = Decimal('50000.00')  # Incorrect value
        self.payroll.save()
        
        # Run reconciliation
        result = ReconciliationService.reconcile_payroll_calculations()
        
        # Verify discrepancy detected
        self.assertFalse(result.is_balanced)
        self.assertGreater(result.total_discrepancies, 0)
        
    def test_scholarship_application_reconciliation(self):
        """Test scholarship application reconciliation"""
        # Create scholarship
        scholarship = Scholarship.objects.create(
            name='Merit Scholarship',
            scholarship_type='merit',
            amount=Decimal('2000.00'),
            max_recipients=10,
            academic_year='2024-2025'
        )
        
        # Create scholarship recipient
        recipient = ScholarshipRecipient.objects.create(
            scholarship=scholarship,
            student=self.student,
            awarded_amount=Decimal('2000.00'),
            start_date=self.term.start_date,
            end_date=self.term.end_date,
            status='active'
        )
        
        # Apply discount to student fee
        self.student_fee.discount_amount = Decimal('2000.00')
        self.student_fee.save()
        
        # Run reconciliation
        result = ReconciliationService.reconcile_scholarship_applications('2024-2025')
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.reconciliation_type, 'scholarship_applications')
        self.assertTrue(result.is_balanced)
        
    def test_balance_verification(self):
        """Test balance verification reconciliation"""
        # Create payment
        payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('7000.00'),
            payment_method='bank_transfer',
            received_by=self.admin_user
        )
        
        # Run reconciliation
        result = ReconciliationService.reconcile_balance_verification(self.term)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.reconciliation_type, 'balance_verification')
        self.assertTrue(result.is_balanced)
        self.assertIn('summary', result.details)
        
    def test_comprehensive_reconciliation(self):
        """Test comprehensive reconciliation"""
        # Create some financial data
        payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('5000.00'),
            payment_method='cash',
            received_by=self.admin_user
        )
        
        # Run comprehensive reconciliation
        results = ReconciliationService.run_comprehensive_reconciliation()
        
        # Verify results
        self.assertIsNotNone(results)
        self.assertIn('reconciliations', results)
        self.assertIn('overall_status', results)
        self.assertIn('payment_collections', results['reconciliations'])
        self.assertIn('payroll_calculations', results['reconciliations'])
        self.assertIn('scholarship_applications', results['reconciliations'])
        self.assertIn('balance_verification', results['reconciliations'])


class DiscrepancyDetectorTestCase(TestCase):
    """Test cases for DiscrepancyDetector"""
    
    def setUp(self):
        """Set up test data"""
        # Create minimal test data
        self.admin_user = User.objects.create_user(
            username='admin',
            password='testpass123',
            role='super_admin'
        )
        
        self.teacher_user = User.objects.create_user(
            username='teacher1',
            password='testpass123',
            role='subject_teacher'
        )
        
        self.student_user = User.objects.create_user(
            username='student1',
            password='testpass123',
            role='student'
        )
        
        self.school_class = SchoolClass.objects.create(name='Grade 10', stream='A')
        self.term = Term.objects.create(
            name='Term 1',
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=90),
            is_active=True
        )
        
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=timezone.now().date() - timedelta(days=365*15)
        )
        
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='TCH001'
        )
        
        self.fee_structure = FeeStructure.objects.create(
            name='Standard Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('10000.00')
        )
        
        self.student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            total_amount=Decimal('10000.00'),
            due_date=timezone.now().date() + timedelta(days=30)
        )
        
    def test_detect_overpayment_anomaly(self):
        """Test detection of overpayment anomaly"""
        # Create overpayment
        self.student_fee.paid_amount = Decimal('12000.00')
        self.student_fee.save()
        
        # Detect anomalies
        anomalies = DiscrepancyDetector.detect_payment_anomalies(self.student_fee)
        
        # Verify overpayment detected
        self.assertGreater(len(anomalies), 0)
        overpayment_found = any(a['type'] == 'overpayment' for a in anomalies)
        self.assertTrue(overpayment_found)
        
    def test_detect_long_overdue_anomaly(self):
        """Test detection of long overdue fees"""
        # Set due date to 100 days ago
        self.student_fee.due_date = timezone.now().date() - timedelta(days=100)
        self.student_fee.status = 'overdue'
        self.student_fee.save()
        
        # Detect anomalies
        anomalies = DiscrepancyDetector.detect_payment_anomalies(self.student_fee)
        
        # Verify long overdue detected
        self.assertGreater(len(anomalies), 0)
        overdue_found = any(a['type'] == 'long_overdue' for a in anomalies)
        self.assertTrue(overdue_found)
        
    def test_detect_payroll_anomalies(self):
        """Test detection of payroll anomalies"""
        payroll_structure = PayrollStructure.objects.create(
            name='Test Payroll',
            basic_salary=Decimal('50000.00'),
            tax_rate=Decimal('30.00'),  # High tax rate
            pension_rate=Decimal('25.00')  # High pension rate
        )
        
        payroll = StaffPayroll.objects.create(
            teacher=self.teacher,
            payroll_structure=payroll_structure,
            month=timezone.now().date().replace(day=1),
            gross_salary=Decimal('50000.00'),
            net_salary=Decimal('0.00')
        )
        payroll.calculate_net_salary()
        
        # Detect anomalies
        anomalies = DiscrepancyDetector.detect_payroll_anomalies(payroll)
        
        # Verify excessive deductions detected
        self.assertGreater(len(anomalies), 0)
        excessive_found = any(a['type'] == 'excessive_deductions' for a in anomalies)
        self.assertTrue(excessive_found)


class ReconciliationReporterTestCase(TestCase):
    """Test cases for ReconciliationReporter"""
    
    def test_generate_discrepancy_report(self):
        """Test generation of discrepancy report"""
        from .services_reconciliation import ReconciliationResult
        
        # Create a result with discrepancies
        result = ReconciliationResult('payment_collections')
        result.add_discrepancy(
            description='Test discrepancy',
            expected=Decimal('100.00'),
            actual=Decimal('90.00'),
            item_id=1,
            severity='error'
        )
        result.add_warning('Test warning')
        
        # Generate report
        report = ReconciliationReporter.generate_discrepancy_report(result)
        
        # Verify report structure
        self.assertIsNotNone(report)
        self.assertEqual(report['report_type'], 'discrepancy_report')
        self.assertIn('summary', report)
        self.assertIn('discrepancies', report)
        self.assertIn('recommendations', report)
        self.assertGreater(len(report['recommendations']), 0)
        
    def test_generate_comprehensive_report(self):
        """Test generation of comprehensive report"""
        # Create mock comprehensive results
        results = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': {
                'all_balanced': False,
                'total_discrepancies': 5,
                'requires_attention': True
            },
            'reconciliations': {
                'payment_collections': {
                    'is_balanced': False,
                    'total_checked': 10,
                    'total_discrepancies': 3,
                    'discrepancies': [
                        {
                            'description': 'Test discrepancy 1',
                            'expected': 100.0,
                            'actual': 90.0
                        }
                    ]
                }
            }
        }
        
        # Generate report
        report_text = ReconciliationReporter.generate_comprehensive_report(results)
        
        # Verify report content
        self.assertIsNotNone(report_text)
        self.assertIn('COMPREHENSIVE FINANCIAL RECONCILIATION REPORT', report_text)
        self.assertIn('OVERALL STATUS', report_text)
        self.assertIn('PAYMENT COLLECTIONS', report_text)
