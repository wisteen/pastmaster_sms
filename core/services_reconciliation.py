"""
Financial Reconciliation Service Classes

This module provides comprehensive financial reconciliation capabilities including
payment vs collection verification, payroll calculation validation, scholarship
application verification, and balance verification functionality.

Validates: Requirements 11.1, 11.2, 11.3, 11.5
"""

from django.db import models
from django.db.models import Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import json
from typing import Dict, List, Tuple, Optional

from .models import (
    FeeStructure, StudentFee, FeePayment, Student, Teacher,
    StaffPayroll, PayrollStructure, Scholarship, ScholarshipRecipient,
    FinancialTransaction, SchoolClass, Term
)

logger = logging.getLogger(__name__)


class ReconciliationResult:
    """Container for reconciliation results with detailed reporting"""
    
    def __init__(self, reconciliation_type: str):
        self.reconciliation_type = reconciliation_type
        self.is_balanced = True
        self.discrepancies = []
        self.warnings = []
        self.total_checked = 0
        self.total_discrepancies = 0
        self.timestamp = timezone.now()
        self.details = {}
        
    def add_discrepancy(self, description: str, expected: Decimal, actual: Decimal, 
                       item_id: Optional[int] = None, severity: str = 'error'):
        """Add a discrepancy to the reconciliation result"""
        self.is_balanced = False
        self.total_discrepancies += 1
        
        discrepancy = {
            'description': description,
            'expected': float(expected),
            'actual': float(actual),
            'difference': float(actual - expected),
            'item_id': item_id,
            'severity': severity,
            'timestamp': timezone.now()
        }
        self.discrepancies.append(discrepancy)
        
    def add_warning(self, message: str):
        """Add a warning message"""
        self.warnings.append({
            'message': message,
            'timestamp': timezone.now()
        })
        
    def get_summary(self) -> Dict:
        """Get a summary of the reconciliation"""
        return {
            'reconciliation_type': self.reconciliation_type,
            'is_balanced': self.is_balanced,
            'total_checked': self.total_checked,
            'total_discrepancies': self.total_discrepancies,
            'timestamp': self.timestamp.isoformat(),
            'discrepancies': self.discrepancies,
            'warnings': self.warnings,
            'details': self.details
        }


class ReconciliationService:
    """Main service class for financial reconciliation and validation"""
    
    @staticmethod
    def reconcile_payment_collections(start_date: Optional[datetime] = None, 
                                     end_date: Optional[datetime] = None) -> ReconciliationResult:
        """
        Verify that total payments match recorded fee collections
        
        Validates: Requirement 11.1
        
        Args:
            start_date: Start date for reconciliation period
            end_date: End date for reconciliation period
            
        Returns:
            ReconciliationResult with payment vs collection verification
        """
        result = ReconciliationResult('payment_collections')
        
        # Set default date range if not provided
        if not end_date:
            end_date = timezone.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
            
        try:
            # Get all student fees in the period
            student_fees = StudentFee.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            result.total_checked = student_fees.count()
            result.details['date_range'] = {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
            
            # Check each student fee
            for student_fee in student_fees:
                # Calculate expected paid amount from payments
                actual_payments = student_fee.payments.aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0.00')
                
                # Compare with recorded paid amount
                recorded_paid = student_fee.paid_amount
                
                if actual_payments != recorded_paid:
                    result.add_discrepancy(
                        description=f"Payment mismatch for {student_fee.student} - {student_fee.fee_structure}",
                        expected=actual_payments,
                        actual=recorded_paid,
                        item_id=student_fee.id,
                        severity='error'
                    )
                    
                # Verify balance calculation
                expected_balance = student_fee.total_amount - recorded_paid - student_fee.discount_amount
                actual_balance = student_fee.balance_amount
                
                if abs(expected_balance - actual_balance) > Decimal('0.01'):  # Allow for rounding
                    result.add_discrepancy(
                        description=f"Balance calculation error for {student_fee.student}",
                        expected=expected_balance,
                        actual=actual_balance,
                        item_id=student_fee.id,
                        severity='error'
                    )
                    
                # Check payment status consistency
                if recorded_paid >= (student_fee.total_amount - student_fee.discount_amount):
                    if student_fee.status != 'paid':
                        result.add_warning(
                            f"Student fee {student_fee.id} is fully paid but status is '{student_fee.status}'"
                        )
                elif recorded_paid > 0:
                    if student_fee.status not in ['partial', 'paid']:
                        result.add_warning(
                            f"Student fee {student_fee.id} has partial payment but status is '{student_fee.status}'"
                        )
                        
            # Summary statistics
            total_expected = student_fees.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00')
            
            total_paid = student_fees.aggregate(
                total=Sum('paid_amount')
            )['total'] or Decimal('0.00')
            
            total_discounts = student_fees.aggregate(
                total=Sum('discount_amount')
            )['total'] or Decimal('0.00')
            
            result.details['summary'] = {
                'total_fees': float(total_expected),
                'total_paid': float(total_paid),
                'total_discounts': float(total_discounts),
                'total_outstanding': float(total_expected - total_paid - total_discounts)
            }
            
        except Exception as e:
            logger.error(f"Error in payment collection reconciliation: {str(e)}")
            result.add_discrepancy(
                description=f"System error during reconciliation: {str(e)}",
                expected=Decimal('0.00'),
                actual=Decimal('0.00'),
                severity='critical'
            )
            
        return result
    
    @staticmethod
    def reconcile_payroll_calculations(month: Optional[datetime] = None) -> ReconciliationResult:
        """
        Validate that payroll calculations are mathematically correct
        
        Validates: Requirement 11.2
        
        Args:
            month: Month for payroll reconciliation (defaults to current month)
            
        Returns:
            ReconciliationResult with payroll calculation verification
        """
        result = ReconciliationResult('payroll_calculations')
        
        # Set default month if not provided
        if not month:
            month = timezone.now().replace(day=1)
        else:
            month = month.replace(day=1)
            
        try:
            # Get all payroll records for the month
            payrolls = StaffPayroll.objects.filter(month=month)
            
            result.total_checked = payrolls.count()
            result.details['month'] = month.strftime('%B %Y')
            
            for payroll in payrolls:
                # Verify gross salary calculation
                expected_gross = payroll.payroll_structure.gross_salary
                actual_gross = payroll.gross_salary
                
                if abs(expected_gross - actual_gross) > Decimal('0.01'):
                    result.add_discrepancy(
                        description=f"Gross salary mismatch for {payroll.teacher}",
                        expected=expected_gross,
                        actual=actual_gross,
                        item_id=payroll.id,
                        severity='error'
                    )
                    
                # Verify tax deduction calculation
                expected_tax = (payroll.gross_salary * payroll.payroll_structure.tax_rate) / 100
                actual_tax = payroll.tax_deduction
                
                if abs(expected_tax - actual_tax) > Decimal('0.01'):
                    result.add_discrepancy(
                        description=f"Tax deduction mismatch for {payroll.teacher}",
                        expected=expected_tax,
                        actual=actual_tax,
                        item_id=payroll.id,
                        severity='error'
                    )
                    
                # Verify pension deduction calculation
                expected_pension = (payroll.gross_salary * payroll.payroll_structure.pension_rate) / 100
                actual_pension = payroll.pension_deduction
                
                if abs(expected_pension - actual_pension) > Decimal('0.01'):
                    result.add_discrepancy(
                        description=f"Pension deduction mismatch for {payroll.teacher}",
                        expected=expected_pension,
                        actual=actual_pension,
                        item_id=payroll.id,
                        severity='error'
                    )
                    
                # Verify net salary calculation
                expected_net = (payroll.gross_salary - payroll.tax_deduction - 
                              payroll.pension_deduction - payroll.other_deductions)
                actual_net = payroll.net_salary
                
                if abs(expected_net - actual_net) > Decimal('0.01'):
                    result.add_discrepancy(
                        description=f"Net salary mismatch for {payroll.teacher}",
                        expected=expected_net,
                        actual=actual_net,
                        item_id=payroll.id,
                        severity='error'
                    )
                    
                # Check for negative values
                if payroll.net_salary < 0:
                    result.add_warning(
                        f"Negative net salary for {payroll.teacher}: {payroll.net_salary}"
                    )
                    
            # Summary statistics
            total_gross = payrolls.aggregate(total=Sum('gross_salary'))['total'] or Decimal('0.00')
            total_deductions = payrolls.aggregate(
                tax=Sum('tax_deduction'),
                pension=Sum('pension_deduction'),
                other=Sum('other_deductions')
            )
            total_net = payrolls.aggregate(total=Sum('net_salary'))['total'] or Decimal('0.00')
            
            result.details['summary'] = {
                'total_gross_salary': float(total_gross),
                'total_tax_deductions': float(total_deductions['tax'] or 0),
                'total_pension_deductions': float(total_deductions['pension'] or 0),
                'total_other_deductions': float(total_deductions['other'] or 0),
                'total_net_salary': float(total_net),
                'total_staff': payrolls.count()
            }
            
        except Exception as e:
            logger.error(f"Error in payroll calculation reconciliation: {str(e)}")
            result.add_discrepancy(
                description=f"System error during reconciliation: {str(e)}",
                expected=Decimal('0.00'),
                actual=Decimal('0.00'),
                severity='critical'
            )
            
        return result
    
    @staticmethod
    def reconcile_scholarship_applications(academic_year: Optional[str] = None) -> ReconciliationResult:
        """
        Check that scholarship deductions are properly applied to student fees
        
        Validates: Requirement 11.3
        
        Args:
            academic_year: Academic year for scholarship reconciliation
            
        Returns:
            ReconciliationResult with scholarship application verification
        """
        result = ReconciliationResult('scholarship_applications')
        
        # Set default academic year if not provided
        if not academic_year:
            current_year = timezone.now().year
            academic_year = f"{current_year}-{current_year + 1}"
            
        try:
            # Get all active scholarship recipients for the academic year
            recipients = ScholarshipRecipient.objects.filter(
                scholarship__academic_year=academic_year,
                status='active'
            ).select_related('scholarship', 'student')
            
            result.total_checked = recipients.count()
            result.details['academic_year'] = academic_year
            
            for recipient in recipients:
                # Get student fees for this recipient
                student_fees = StudentFee.objects.filter(
                    student=recipient.student,
                    fee_structure__term__start_date__gte=recipient.start_date,
                    fee_structure__term__end_date__lte=recipient.end_date
                )
                
                for student_fee in student_fees:
                    # Calculate expected discount based on scholarship
                    if recipient.scholarship.percentage:
                        expected_discount = (student_fee.total_amount * recipient.scholarship.percentage) / 100
                    else:
                        expected_discount = recipient.awarded_amount
                        
                    # Check if discount is applied
                    actual_discount = student_fee.discount_amount
                    
                    # Allow for some tolerance in percentage-based scholarships
                    tolerance = Decimal('0.01')
                    if abs(expected_discount - actual_discount) > tolerance:
                        result.add_discrepancy(
                            description=f"Scholarship discount mismatch for {recipient.student} - {student_fee.fee_structure}",
                            expected=expected_discount,
                            actual=actual_discount,
                            item_id=student_fee.id,
                            severity='warning'  # Warning because manual adjustments may be valid
                        )
                        
                # Check scholarship amount limits
                if recipient.scholarship.max_recipients:
                    active_count = ScholarshipRecipient.objects.filter(
                        scholarship=recipient.scholarship,
                        status='active'
                    ).count()
                    
                    if active_count > recipient.scholarship.max_recipients:
                        result.add_warning(
                            f"Scholarship '{recipient.scholarship.name}' has {active_count} recipients "
                            f"but max is {recipient.scholarship.max_recipients}"
                        )
                        
                # Check date validity
                if recipient.end_date < timezone.now().date() and recipient.status == 'active':
                    result.add_warning(
                        f"Scholarship for {recipient.student} has expired but status is still 'active'"
                    )
                    
            # Summary statistics
            total_awarded = recipients.aggregate(
                total=Sum('awarded_amount')
            )['total'] or Decimal('0.00')
            
            total_discounts_applied = StudentFee.objects.filter(
                student__in=recipients.values_list('student', flat=True)
            ).aggregate(
                total=Sum('discount_amount')
            )['total'] or Decimal('0.00')
            
            result.details['summary'] = {
                'total_recipients': recipients.count(),
                'total_awarded_amount': float(total_awarded),
                'total_discounts_applied': float(total_discounts_applied),
                'scholarships_active': recipients.values('scholarship').distinct().count()
            }
            
        except Exception as e:
            logger.error(f"Error in scholarship application reconciliation: {str(e)}")
            result.add_discrepancy(
                description=f"System error during reconciliation: {str(e)}",
                expected=Decimal('0.00'),
                actual=Decimal('0.00'),
                severity='critical'
            )
            
        return result
    
    @staticmethod
    def reconcile_balance_verification(term: Optional[Term] = None) -> ReconciliationResult:
        """
        Provide balance verification reports for all financial accounts
        
        Validates: Requirement 11.5
        
        Args:
            term: Term for balance verification (defaults to active term)
            
        Returns:
            ReconciliationResult with balance verification
        """
        result = ReconciliationResult('balance_verification')
        
        try:
            # Get active term if not provided
            if not term:
                term = Term.objects.filter(is_active=True).first()
                if not term:
                    result.add_warning("No active term found for balance verification")
                    return result
                    
            result.details['term'] = str(term)
            
            # Get all student fees for the term
            student_fees = StudentFee.objects.filter(
                fee_structure__term=term
            )
            
            result.total_checked = student_fees.count()
            
            # Verify each student fee balance
            for student_fee in student_fees:
                calculated_balance = (student_fee.total_amount - 
                                    student_fee.paid_amount - 
                                    student_fee.discount_amount)
                actual_balance = student_fee.balance_amount
                
                if abs(calculated_balance - actual_balance) > Decimal('0.01'):
                    result.add_discrepancy(
                        description=f"Balance verification failed for {student_fee.student}",
                        expected=calculated_balance,
                        actual=actual_balance,
                        item_id=student_fee.id,
                        severity='error'
                    )
                    
                # Check for negative balances (overpayment)
                if actual_balance < 0:
                    result.add_warning(
                        f"Negative balance (overpayment) for {student_fee.student}: {actual_balance}"
                    )
                    
            # Calculate overall financial position
            total_fees = student_fees.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            total_paid = student_fees.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
            total_discounts = student_fees.aggregate(total=Sum('discount_amount'))['total'] or Decimal('0.00')
            total_outstanding = total_fees - total_paid - total_discounts
            
            # Get payment breakdown by method
            payments = FeePayment.objects.filter(
                student_fee__fee_structure__term=term
            )
            
            payment_by_method = {}
            for method, _ in FeePayment.PAYMENT_METHODS:
                amount = payments.filter(payment_method=method).aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0.00')
                payment_by_method[method] = float(amount)
                
            # Get payroll expenses for the term period
            payroll_expenses = StaffPayroll.objects.filter(
                month__gte=term.start_date,
                month__lte=term.end_date,
                is_paid=True
            ).aggregate(total=Sum('net_salary'))['total'] or Decimal('0.00')
            
            # Get other transactions for the term
            other_income = FinancialTransaction.objects.filter(
                transaction_type='income',
                transaction_date__gte=term.start_date,
                transaction_date__lte=term.end_date
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            other_expenses = FinancialTransaction.objects.filter(
                transaction_type='expense',
                transaction_date__gte=term.start_date,
                transaction_date__lte=term.end_date
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            # Calculate net position
            total_income = total_paid + other_income
            total_expenses = payroll_expenses + other_expenses
            net_position = total_income - total_expenses
            
            result.details['summary'] = {
                'fee_income': {
                    'total_fees_billed': float(total_fees),
                    'total_collected': float(total_paid),
                    'total_discounts': float(total_discounts),
                    'total_outstanding': float(total_outstanding),
                    'collection_rate': float((total_paid / total_fees * 100) if total_fees > 0 else 0),
                    'payment_by_method': payment_by_method
                },
                'expenses': {
                    'payroll': float(payroll_expenses),
                    'other': float(other_expenses),
                    'total': float(payroll_expenses + other_expenses)
                },
                'financial_position': {
                    'total_income': float(total_income),
                    'total_expenses': float(total_expenses),
                    'net_position': float(net_position)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in balance verification: {str(e)}")
            result.add_discrepancy(
                description=f"System error during reconciliation: {str(e)}",
                expected=Decimal('0.00'),
                actual=Decimal('0.00'),
                severity='critical'
            )
            
        return result
    
    @staticmethod
    def run_comprehensive_reconciliation(start_date: Optional[datetime] = None,
                                        end_date: Optional[datetime] = None) -> Dict:
        """
        Run all reconciliation checks and return comprehensive results
        
        Args:
            start_date: Start date for reconciliation period
            end_date: End date for reconciliation period
            
        Returns:
            Dictionary containing all reconciliation results
        """
        results = {
            'timestamp': timezone.now().isoformat(),
            'reconciliations': {}
        }
        
        try:
            # Run payment collection reconciliation
            payment_result = ReconciliationService.reconcile_payment_collections(
                start_date, end_date
            )
            results['reconciliations']['payment_collections'] = payment_result.get_summary()
            
            # Run payroll calculation reconciliation
            payroll_result = ReconciliationService.reconcile_payroll_calculations()
            results['reconciliations']['payroll_calculations'] = payroll_result.get_summary()
            
            # Run scholarship application reconciliation
            scholarship_result = ReconciliationService.reconcile_scholarship_applications()
            results['reconciliations']['scholarship_applications'] = scholarship_result.get_summary()
            
            # Run balance verification
            balance_result = ReconciliationService.reconcile_balance_verification()
            results['reconciliations']['balance_verification'] = balance_result.get_summary()
            
            # Calculate overall status
            all_balanced = all([
                payment_result.is_balanced,
                payroll_result.is_balanced,
                scholarship_result.is_balanced,
                balance_result.is_balanced
            ])
            
            total_discrepancies = sum([
                payment_result.total_discrepancies,
                payroll_result.total_discrepancies,
                scholarship_result.total_discrepancies,
                balance_result.total_discrepancies
            ])
            
            results['overall_status'] = {
                'all_balanced': all_balanced,
                'total_discrepancies': total_discrepancies,
                'requires_attention': not all_balanced
            }
            
        except Exception as e:
            logger.error(f"Error in comprehensive reconciliation: {str(e)}")
            results['error'] = str(e)
            
        return results



class DiscrepancyDetector:
    """Advanced discrepancy detection algorithms with suggestions"""
    
    @staticmethod
    def detect_payment_anomalies(student_fee: StudentFee) -> List[Dict]:
        """
        Detect anomalies in payment patterns
        
        Validates: Requirement 11.4
        
        Returns:
            List of detected anomalies with suggestions
        """
        anomalies = []
        
        try:
            # Check for duplicate payments
            payments = student_fee.payments.all()
            payment_dates = {}
            
            for payment in payments:
                date_key = payment.payment_date.date()
                if date_key in payment_dates:
                    anomalies.append({
                        'type': 'duplicate_payment',
                        'severity': 'warning',
                        'description': f"Multiple payments on {date_key}",
                        'suggestion': "Review payments for potential duplicates",
                        'affected_payments': [payment_dates[date_key], payment.id]
                    })
                payment_dates[date_key] = payment.id
                
            # Check for overpayment
            if student_fee.balance_amount < -Decimal('0.01'):
                anomalies.append({
                    'type': 'overpayment',
                    'severity': 'warning',
                    'description': f"Overpayment of {abs(student_fee.balance_amount)}",
                    'suggestion': "Issue refund or apply credit to future fees",
                    'amount': float(abs(student_fee.balance_amount))
                })
                
            # Check for unusual payment amounts
            for payment in payments:
                if payment.amount > student_fee.total_amount:
                    anomalies.append({
                        'type': 'excessive_payment',
                        'severity': 'error',
                        'description': f"Single payment ({payment.amount}) exceeds total fee ({student_fee.total_amount})",
                        'suggestion': "Verify payment amount and split if necessary",
                        'payment_id': payment.id
                    })
                    
            # Check for very old unpaid fees
            if student_fee.status in ['pending', 'partial', 'overdue']:
                days_overdue = (timezone.now().date() - student_fee.due_date).days
                if days_overdue > 90:
                    anomalies.append({
                        'type': 'long_overdue',
                        'severity': 'warning',
                        'description': f"Fee overdue by {days_overdue} days",
                        'suggestion': "Contact parent/guardian or consider write-off",
                        'days_overdue': days_overdue
                    })
                    
        except Exception as e:
            logger.error(f"Error detecting payment anomalies: {str(e)}")
            
        return anomalies
    
    @staticmethod
    def detect_payroll_anomalies(payroll: StaffPayroll) -> List[Dict]:
        """
        Detect anomalies in payroll calculations
        
        Validates: Requirement 11.4
        
        Returns:
            List of detected anomalies with suggestions
        """
        anomalies = []
        
        try:
            # Check for excessive deductions
            total_deductions = (payroll.tax_deduction + payroll.pension_deduction + 
                              payroll.other_deductions)
            deduction_percentage = (total_deductions / payroll.gross_salary * 100) if payroll.gross_salary > 0 else 0
            
            if deduction_percentage > 50:
                anomalies.append({
                    'type': 'excessive_deductions',
                    'severity': 'warning',
                    'description': f"Total deductions ({deduction_percentage:.1f}%) exceed 50% of gross salary",
                    'suggestion': "Review deduction amounts for accuracy",
                    'deduction_percentage': float(deduction_percentage)
                })
                
            # Check for negative net salary
            if payroll.net_salary < 0:
                anomalies.append({
                    'type': 'negative_net_salary',
                    'severity': 'error',
                    'description': f"Net salary is negative: {payroll.net_salary}",
                    'suggestion': "Reduce deductions or adjust gross salary",
                    'net_salary': float(payroll.net_salary)
                })
                
            # Check for unpaid old payroll
            if not payroll.is_paid:
                months_unpaid = (timezone.now().date().replace(day=1) - payroll.month).days // 30
                if months_unpaid > 1:
                    anomalies.append({
                        'type': 'unpaid_payroll',
                        'severity': 'error',
                        'description': f"Payroll unpaid for {months_unpaid} months",
                        'suggestion': "Process payment immediately",
                        'months_unpaid': months_unpaid
                    })
                    
            # Check for unusual salary changes
            previous_payroll = StaffPayroll.objects.filter(
                teacher=payroll.teacher,
                month__lt=payroll.month
            ).order_by('-month').first()
            
            if previous_payroll:
                salary_change = abs(payroll.gross_salary - previous_payroll.gross_salary)
                change_percentage = (salary_change / previous_payroll.gross_salary * 100) if previous_payroll.gross_salary > 0 else 0
                
                if change_percentage > 20:
                    anomalies.append({
                        'type': 'unusual_salary_change',
                        'severity': 'warning',
                        'description': f"Salary changed by {change_percentage:.1f}% from previous month",
                        'suggestion': "Verify salary adjustment is intentional",
                        'change_percentage': float(change_percentage)
                    })
                    
        except Exception as e:
            logger.error(f"Error detecting payroll anomalies: {str(e)}")
            
        return anomalies
    
    @staticmethod
    def detect_scholarship_anomalies(recipient: ScholarshipRecipient) -> List[Dict]:
        """
        Detect anomalies in scholarship applications
        
        Validates: Requirement 11.4
        
        Returns:
            List of detected anomalies with suggestions
        """
        anomalies = []
        
        try:
            # Check for expired scholarships still marked active
            if recipient.status == 'active' and recipient.end_date < timezone.now().date():
                days_expired = (timezone.now().date() - recipient.end_date).days
                anomalies.append({
                    'type': 'expired_scholarship',
                    'severity': 'warning',
                    'description': f"Scholarship expired {days_expired} days ago but still active",
                    'suggestion': "Update status to 'completed' or extend end date",
                    'days_expired': days_expired
                })
                
            # Check for overlapping scholarships
            overlapping = ScholarshipRecipient.objects.filter(
                student=recipient.student,
                status='active'
            ).exclude(id=recipient.id).filter(
                Q(start_date__lte=recipient.end_date) & Q(end_date__gte=recipient.start_date)
            )
            
            if overlapping.exists():
                anomalies.append({
                    'type': 'overlapping_scholarships',
                    'severity': 'warning',
                    'description': f"Student has {overlapping.count() + 1} overlapping active scholarships",
                    'suggestion': "Review scholarship eligibility and dates",
                    'overlapping_count': overlapping.count()
                })
                
            # Check for scholarship amount exceeding fee amount
            student_fees = StudentFee.objects.filter(
                student=recipient.student,
                fee_structure__term__start_date__gte=recipient.start_date,
                fee_structure__term__end_date__lte=recipient.end_date
            )
            
            for student_fee in student_fees:
                if student_fee.discount_amount > student_fee.total_amount:
                    anomalies.append({
                        'type': 'excessive_scholarship',
                        'severity': 'error',
                        'description': f"Scholarship discount ({student_fee.discount_amount}) exceeds fee amount ({student_fee.total_amount})",
                        'suggestion': "Adjust scholarship amount to not exceed fee",
                        'student_fee_id': student_fee.id
                    })
                    
        except Exception as e:
            logger.error(f"Error detecting scholarship anomalies: {str(e)}")
            
        return anomalies


class ReconciliationReporter:
    """Generate detailed error reports with suggestions"""
    
    @staticmethod
    def generate_discrepancy_report(reconciliation_result: ReconciliationResult) -> Dict:
        """
        Generate a detailed report of discrepancies with actionable suggestions
        
        Validates: Requirement 11.6
        
        Args:
            reconciliation_result: Result from reconciliation check
            
        Returns:
            Detailed report dictionary
        """
        report = {
            'report_type': 'discrepancy_report',
            'reconciliation_type': reconciliation_result.reconciliation_type,
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'is_balanced': reconciliation_result.is_balanced,
                'total_discrepancies': reconciliation_result.total_discrepancies,
                'total_warnings': len(reconciliation_result.warnings)
            },
            'discrepancies': [],
            'warnings': reconciliation_result.warnings,
            'recommendations': []
        }
        
        # Group discrepancies by severity
        critical_discrepancies = []
        error_discrepancies = []
        warning_discrepancies = []
        
        for discrepancy in reconciliation_result.discrepancies:
            severity = discrepancy.get('severity', 'error')
            
            # Add actionable suggestions based on discrepancy type
            suggestion = ReconciliationReporter._get_suggestion_for_discrepancy(
                reconciliation_result.reconciliation_type,
                discrepancy
            )
            discrepancy['actionable_suggestion'] = suggestion
            
            if severity == 'critical':
                critical_discrepancies.append(discrepancy)
            elif severity == 'error':
                error_discrepancies.append(discrepancy)
            else:
                warning_discrepancies.append(discrepancy)
                
        report['discrepancies'] = {
            'critical': critical_discrepancies,
            'errors': error_discrepancies,
            'warnings': warning_discrepancies
        }
        
        # Generate overall recommendations
        if critical_discrepancies:
            report['recommendations'].append({
                'priority': 'urgent',
                'action': 'Address critical discrepancies immediately',
                'details': 'System integrity may be compromised'
            })
            
        if error_discrepancies:
            report['recommendations'].append({
                'priority': 'high',
                'action': 'Review and correct error discrepancies',
                'details': 'Financial data accuracy is affected'
            })
            
        if warning_discrepancies:
            report['recommendations'].append({
                'priority': 'medium',
                'action': 'Investigate warning discrepancies',
                'details': 'Potential issues that may require attention'
            })
            
        return report
    
    @staticmethod
    def _get_suggestion_for_discrepancy(reconciliation_type: str, discrepancy: Dict) -> str:
        """Get specific actionable suggestion based on discrepancy type"""
        
        if reconciliation_type == 'payment_collections':
            if 'payment mismatch' in discrepancy['description'].lower():
                return "Recalculate total payments and update student fee record"
            elif 'balance calculation' in discrepancy['description'].lower():
                return "Verify total amount, paid amount, and discount amount fields"
                
        elif reconciliation_type == 'payroll_calculations':
            if 'gross salary' in discrepancy['description'].lower():
                return "Update payroll record to match payroll structure"
            elif 'tax deduction' in discrepancy['description'].lower():
                return "Recalculate tax based on current tax rate"
            elif 'pension deduction' in discrepancy['description'].lower():
                return "Recalculate pension based on current pension rate"
            elif 'net salary' in discrepancy['description'].lower():
                return "Recalculate net salary: gross - tax - pension - other deductions"
                
        elif reconciliation_type == 'scholarship_applications':
            if 'discount mismatch' in discrepancy['description'].lower():
                return "Apply correct scholarship discount to student fee"
                
        elif reconciliation_type == 'balance_verification':
            if 'balance verification failed' in discrepancy['description'].lower():
                return "Recalculate balance: total - paid - discount"
                
        return "Review and correct the discrepancy manually"
    
    @staticmethod
    def generate_comprehensive_report(comprehensive_results: Dict) -> str:
        """
        Generate a human-readable comprehensive reconciliation report
        
        Args:
            comprehensive_results: Results from comprehensive reconciliation
            
        Returns:
            Formatted report string
        """
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("COMPREHENSIVE FINANCIAL RECONCILIATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {comprehensive_results['timestamp']}")
        report_lines.append("")
        
        overall = comprehensive_results.get('overall_status', {})
        report_lines.append("OVERALL STATUS")
        report_lines.append("-" * 80)
        report_lines.append(f"All Balanced: {'YES' if overall.get('all_balanced') else 'NO'}")
        report_lines.append(f"Total Discrepancies: {overall.get('total_discrepancies', 0)}")
        report_lines.append(f"Requires Attention: {'YES' if overall.get('requires_attention') else 'NO'}")
        report_lines.append("")
        
        # Detail each reconciliation
        for recon_type, recon_data in comprehensive_results.get('reconciliations', {}).items():
            report_lines.append(f"{recon_type.upper().replace('_', ' ')}")
            report_lines.append("-" * 80)
            report_lines.append(f"Balanced: {'YES' if recon_data.get('is_balanced') else 'NO'}")
            report_lines.append(f"Items Checked: {recon_data.get('total_checked', 0)}")
            report_lines.append(f"Discrepancies Found: {recon_data.get('total_discrepancies', 0)}")
            
            if recon_data.get('discrepancies'):
                report_lines.append("\nDiscrepancies:")
                for i, disc in enumerate(recon_data['discrepancies'][:5], 1):  # Show first 5
                    report_lines.append(f"  {i}. {disc.get('description')}")
                    report_lines.append(f"     Expected: {disc.get('expected')}, Actual: {disc.get('actual')}")
                    
                if len(recon_data['discrepancies']) > 5:
                    report_lines.append(f"  ... and {len(recon_data['discrepancies']) - 5} more")
                    
            report_lines.append("")
            
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)


class ReconciliationScheduler:
    """Automated daily reconciliation scheduling with email notifications"""
    
    @staticmethod
    def schedule_daily_reconciliation():
        """
        Schedule automated daily reconciliation checks
        
        Validates: Requirement 11.7
        
        This method should be called by a task scheduler (e.g., Celery, Django-Q)
        """
        from .services_notification import NotificationService
        
        logger.info("Starting scheduled daily reconciliation")
        
        try:
            # Run comprehensive reconciliation
            results = ReconciliationService.run_comprehensive_reconciliation()
            
            # Check if there are any discrepancies
            overall_status = results.get('overall_status', {})
            requires_attention = overall_status.get('requires_attention', False)
            
            if requires_attention:
                # Generate detailed report
                report_text = ReconciliationReporter.generate_comprehensive_report(results)
                
                # Send email notification
                ReconciliationScheduler.send_discrepancy_notification(results, report_text)
                
                logger.warning(f"Daily reconciliation found {overall_status.get('total_discrepancies', 0)} discrepancies")
            else:
                logger.info("Daily reconciliation completed successfully - no discrepancies found")
                
            # Log results for audit trail
            ReconciliationScheduler._log_reconciliation_results(results)
            
        except Exception as e:
            logger.error(f"Error in scheduled daily reconciliation: {str(e)}")
            # Send error notification
            ReconciliationScheduler.send_error_notification(str(e))
            
    @staticmethod
    def send_discrepancy_notification(results: Dict, report_text: str):
        """
        Send email notifications for detected discrepancies
        
        Validates: Requirement 11.7
        
        Args:
            results: Comprehensive reconciliation results
            report_text: Formatted report text
        """
        from django.core.mail import send_mail
        from django.conf import settings
        from .services_notification import NotificationService
        
        try:
            overall_status = results.get('overall_status', {})
            total_discrepancies = overall_status.get('total_discrepancies', 0)
            
            # Get admin users to notify
            admin_users = User.objects.filter(
                Q(role='super_admin') | Q(is_superuser=True)
            )
            
            recipient_emails = [user.email for user in admin_users if user.email]
            
            if not recipient_emails:
                logger.warning("No admin email addresses found for discrepancy notification")
                return
                
            subject = f"Financial Reconciliation Alert: {total_discrepancies} Discrepancies Found"
            
            message = f"""
Financial Reconciliation Alert

{total_discrepancies} discrepancies were detected during the daily reconciliation check.

{report_text}

Please review and address these discrepancies as soon as possible.

This is an automated notification from the School Management System.
"""
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                fail_silently=False
            )
            
            logger.info(f"Discrepancy notification sent to {len(recipient_emails)} administrators")
            
        except Exception as e:
            logger.error(f"Error sending discrepancy notification: {str(e)}")
            
    @staticmethod
    def send_error_notification(error_message: str):
        """
        Send email notification for reconciliation errors
        
        Args:
            error_message: Error message to include in notification
        """
        from django.core.mail import send_mail
        from django.conf import settings
        
        try:
            admin_users = User.objects.filter(
                Q(role='super_admin') | Q(is_superuser=True)
            )
            
            recipient_emails = [user.email for user in admin_users if user.email]
            
            if not recipient_emails:
                return
                
            subject = "Financial Reconciliation System Error"
            
            message = f"""
Financial Reconciliation System Error

An error occurred during the automated daily reconciliation:

{error_message}

Please check the system logs and investigate immediately.

This is an automated notification from the School Management System.
"""
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Error sending error notification: {str(e)}")
            
    @staticmethod
    def _log_reconciliation_results(results: Dict):
        """
        Log reconciliation results for audit trail
        
        Args:
            results: Comprehensive reconciliation results
        """
        try:
            # Store results in a log file or database
            log_entry = {
                'timestamp': results.get('timestamp'),
                'overall_status': results.get('overall_status'),
                'summary': {
                    recon_type: {
                        'is_balanced': recon_data.get('is_balanced'),
                        'total_checked': recon_data.get('total_checked'),
                        'total_discrepancies': recon_data.get('total_discrepancies')
                    }
                    for recon_type, recon_data in results.get('reconciliations', {}).items()
                }
            }
            
            logger.info(f"Reconciliation results logged: {json.dumps(log_entry)}")
            
        except Exception as e:
            logger.error(f"Error logging reconciliation results: {str(e)}")


# Celery task for automated scheduling (if Celery is configured)
try:
    from celery import shared_task
    
    @shared_task
    def run_daily_reconciliation():
        """Celery task for daily reconciliation"""
        ReconciliationScheduler.schedule_daily_reconciliation()
        
except ImportError:
    # Celery not installed, task scheduling will need to be done differently
    logger.info("Celery not available - use alternative task scheduler for daily reconciliation")
