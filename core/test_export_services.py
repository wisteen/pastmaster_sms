"""
Tests for Export Services

This module contains tests for the export functionality including
PDF, Excel, and CSV exports, as well as receipt and payroll slip generation.
"""

import os
import tempfile
from decimal import Decimal
from datetime import datetime, date
from django.test import TestCase
from django.utils import timezone
from django.http import HttpResponse

from .models import (
    User, SchoolClass, Term, Student, Teacher, FeeStructure, StudentFee, 
    FeePayment, PayrollStructure, StaffPayroll, Scholarship, 
    ScholarshipRecipient, FinancialTransaction
)
from .services_export import (
    ExportService, FinancialExportService, ReceiptGenerator, 
    PayrollSlipGenerator, export_student_fees, generate_payment_receipt
)


class ExportServiceTestCase(TestCase):
    """Test cases for the main ExportService class"""
    
    def setUp(self):
        """Set up test data"""
        self.export_service = ExportService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.export_service.set_user(self.user)
        
        # Sample data for testing
        self.test_data = [
            {'name': 'John Doe', 'amount': Decimal('100.50'), 'date': '2024-01-15'},
            {'name': 'Jane Smith', 'amount': Decimal('200.75'), 'date': '2024-01-16'},
            {'name': 'Bob Johnson', 'amount': None, 'date': '2024-01-17'},
        ]
        
        self.headers = ['name', 'amount', 'date']
    
    def test_csv_export(self):
        """Test CSV export functionality"""
        response = self.export_service.export_data(
            data=self.test_data,
            export_format='csv',
            filename='test_export',
            headers=self.headers,
            title='Test CSV Export'
        )
        
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('test_export_', response['Content-Disposition'])
        
        # Check content
        content = response.content.decode('utf-8')
        self.assertIn('Test CSV Export', content)
        self.assertIn('John Doe', content)
        self.assertIn('100.5', content)  # Decimal converted to float
    
    def test_csv_export_empty_data(self):
        """Test CSV export with empty data"""
        response = self.export_service.export_data(
            data=[],
            export_format='csv',
            filename='empty_test',
            headers=self.headers,
            title='Empty Test'
        )
        
        content = response.content.decode('utf-8')
        self.assertIn('No data available', content)
    
    def test_excel_export_without_openpyxl(self):
        """Test Excel export when openpyxl is not available"""
        # Temporarily disable openpyxl
        import core.services_export as export_module
        original_openpyxl = export_module.OPENPYXL_AVAILABLE
        export_module.OPENPYXL_AVAILABLE = False
        
        try:
            with self.assertRaises(ImportError):
                self.export_service.export_data(
                    data=self.test_data,
                    export_format='excel',
                    filename='test_excel',
                    headers=self.headers
                )
        finally:
            export_module.OPENPYXL_AVAILABLE = original_openpyxl
    
    def test_pdf_export_without_reportlab(self):
        """Test PDF export when reportlab is not available"""
        # Temporarily disable reportlab
        import core.services_export as export_module
        original_reportlab = export_module.REPORTLAB_AVAILABLE
        export_module.REPORTLAB_AVAILABLE = False
        
        try:
            with self.assertRaises(ImportError):
                self.export_service.export_data(
                    data=self.test_data,
                    export_format='pdf',
                    filename='test_pdf',
                    headers=self.headers
                )
        finally:
            export_module.REPORTLAB_AVAILABLE = original_reportlab
    
    def test_unsupported_format(self):
        """Test export with unsupported format"""
        with self.assertRaises(ValueError):
            self.export_service.export_data(
                data=self.test_data,
                export_format='xml',
                filename='test_xml',
                headers=self.headers
            )


class FinancialExportServiceTestCase(TestCase):
    """Test cases for the FinancialExportService class"""
    
    def setUp(self):
        """Set up test data"""
        self.financial_service = FinancialExportService()
        
        # Create test user
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            first_name='Admin',
            last_name='User'
        )
        self.financial_service.set_user(self.user)
        
        # Create test data
        self.school_class = SchoolClass.objects.create(name='Grade 10', stream='A')
        self.term = Term.objects.create(
            name='First Term',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 30),
            is_active=True
        )
        
        # Create student
        student_user = User.objects.create_user(
            username='student1',
            first_name='John',
            last_name='Doe'
        )
        self.student = Student.objects.create(
            user=student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=date(2005, 1, 1)
        )
        
        # Create fee structure
        self.fee_structure = FeeStructure.objects.create(
            name='Term 1 Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('500.00'),
            development_fee=Decimal('100.00')
        )
        
        # Create student fee
        self.student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            total_amount=Decimal('600.00'),
            due_date=date(2024, 2, 1)
        )
        
        # Create payment
        self.payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('300.00'),
            payment_method='cash',
            reference_number='PAY001',
            received_by=self.user
        )
    
    def test_export_student_fees_csv(self):
        """Test exporting student fees to CSV"""
        response = self.financial_service.export_student_fees(export_format='csv')
        
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        content = response.content.decode('utf-8')
        self.assertIn('John Doe', content)
        self.assertIn('STU001', content)
        self.assertIn('600.0', content)  # Total amount
    
    def test_export_fee_payments_csv(self):
        """Test exporting fee payments to CSV"""
        response = self.financial_service.export_fee_payments(export_format='csv')
        
        self.assertIsInstance(response, HttpResponse)
        content = response.content.decode('utf-8')
        self.assertIn('John Doe', content)
        self.assertIn('300.0', content)  # Payment amount
        self.assertIn('PAY001', content)  # Reference number
    
    def test_export_with_filters(self):
        """Test exporting with filters applied"""
        filters = {
            'class_id': self.school_class.id,
            'status': 'partial'
        }
        
        response = self.financial_service.export_student_fees(
            export_format='csv',
            filters=filters
        )
        
        self.assertIsInstance(response, HttpResponse)
        content = response.content.decode('utf-8')
        self.assertIn('John Doe', content)
    
    def test_generate_payment_receipt_invalid_id(self):
        """Test generating receipt with invalid payment ID"""
        with self.assertRaises(ValueError):
            self.financial_service.generate_payment_receipt(99999)


class ReceiptGeneratorTestCase(TestCase):
    """Test cases for the ReceiptGenerator class"""
    
    def setUp(self):
        """Set up test data"""
        self.receipt_generator = ReceiptGenerator()
        
        # Create minimal test data
        self.user = User.objects.create_user(username='admin', first_name='Admin', last_name='User')
        self.school_class = SchoolClass.objects.create(name='Grade 10')
        self.term = Term.objects.create(
            name='First Term',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 30)
        )
        
        student_user = User.objects.create_user(username='student', first_name='John', last_name='Doe')
        self.student = Student.objects.create(
            user=student_user,
            student_id='STU001',
            school_class=self.school_class,
            date_of_birth=date(2005, 1, 1)
        )
        
        self.fee_structure = FeeStructure.objects.create(
            name='Term Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('500.00')
        )
        
        self.student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            total_amount=Decimal('500.00'),
            due_date=date(2024, 2, 1)
        )
        
        self.payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('500.00'),
            payment_method='cash',
            received_by=self.user
        )
    
    def test_generate_html_receipt(self):
        """Test generating HTML receipt"""
        response = self.receipt_generator.generate_payment_receipt(self.payment, 'html')
        
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'text/html')
        
        content = response.content.decode('utf-8')
        self.assertIn('PAYMENT RECEIPT', content)
        self.assertIn('John Doe', content)
        self.assertIn('STU001', content)
    
    def test_generate_receipt_unsupported_format(self):
        """Test generating receipt with unsupported format"""
        with self.assertRaises(ValueError):
            self.receipt_generator.generate_payment_receipt(self.payment, 'xml')


class UtilityFunctionsTestCase(TestCase):
    """Test cases for utility functions"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(username='testuser')
        self.school_class = SchoolClass.objects.create(name='Test Class')
        self.term = Term.objects.create(
            name='Test Term',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 30)
        )
        
        student_user = User.objects.create_user(username='student', first_name='Test', last_name='Student')
        self.student = Student.objects.create(
            user=student_user,
            student_id='TEST001',
            school_class=self.school_class,
            date_of_birth=date(2005, 1, 1)
        )
        
        self.fee_structure = FeeStructure.objects.create(
            name='Test Fees',
            school_class=self.school_class,
            term=self.term,
            tuition_fee=Decimal('100.00')
        )
        
        self.student_fee = StudentFee.objects.create(
            student=self.student,
            fee_structure=self.fee_structure,
            total_amount=Decimal('100.00'),
            due_date=date(2024, 2, 1)
        )
        
        self.payment = FeePayment.objects.create(
            student_fee=self.student_fee,
            amount=Decimal('100.00'),
            payment_method='cash',
            received_by=self.user
        )
    
    def test_export_student_fees_utility(self):
        """Test the export_student_fees utility function"""
        response = export_student_fees(export_format='csv', user=self.user)
        
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response['Content-Type'], 'text/csv')
    
    def test_generate_payment_receipt_utility(self):
        """Test the generate_payment_receipt utility function"""
        response = generate_payment_receipt(self.payment.id, 'html')
        
        self.assertIsInstance(response, HttpResponse)
        content = response.content.decode('utf-8')
        self.assertIn('Test Student', content)