"""
Bulk Operations Service Classes for Financial Management Enhancement

This module provides comprehensive bulk processing capabilities for financial operations
including fee structure creation, payment processing, payroll generation, and scholarship
management with transaction safety, error handling, and progress tracking.
"""

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import json

from .models import (
    FeeStructure, StudentFee, FeePayment, Student, Teacher, 
    StaffPayroll, PayrollStructure, Scholarship, ScholarshipRecipient,
    SchoolClass, Term
)
from .forms_financial import (
    FeeStructureForm, FeePaymentForm, ScholarshipForm, 
    ScholarshipRecipientForm, PayrollForm
)
from .bulk_error_handling import BulkOperationRollbackManager

logger = logging.getLogger(__name__)


class BulkOperationResult:
    """Container for bulk operation results with detailed reporting"""
    
    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.total_count = 0
        self.successful_items = []
        self.failed_items = []
        self.errors = []
        self.warnings = []
        self.start_time = timezone.now()
        self.end_time = None
        
    def add_success(self, item, details=None):
        """Add a successful operation"""
        self.success_count += 1
        self.successful_items.append({
            'item': item,
            'details': details,
            'timestamp': timezone.now()
        })
        
    def add_error(self, item_index, error_message, item_data=None):
        """Add a failed operation"""
        self.error_count += 1
        self.failed_items.append({
            'index': item_index,
            'data': item_data,
            'timestamp': timezone.now()
        })
        self.errors.append(f"Item {item_index + 1}: {error_message}")
        
    def add_warning(self, message):
        """Add a warning message"""
        self.warnings.append(message)
        
    def finalize(self):
        """Finalize the result with end time and total count"""
        self.end_time = timezone.now()
        self.total_count = self.success_count + self.error_count
        
    def get_summary(self):
        """Get a summary of the bulk operation"""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        return {
            'total_processed': self.total_count,
            'successful': self.success_count,
            'failed': self.error_count,
            'success_rate': (self.success_count / self.total_count * 100) if self.total_count > 0 else 0,
            'duration_seconds': duration,
            'errors': self.errors,
            'warnings': self.warnings
        }


class BulkOperationService:
    """Main service class for handling bulk financial operations"""
    
    @staticmethod
    @transaction.atomic
    def bulk_create_fee_structures_with_progress(fee_data_list, user=None, progress_tracker=None):
        """
        Create multiple fee structures with validation, progress tracking, and rollback
        
        Args:
            fee_data_list: List of dictionaries containing fee structure data
            user: User performing the operation (for audit logging)
            progress_tracker: Progress tracker instance for real-time updates
            
        Returns:
            BulkOperationResult: Detailed results of the bulk operation
        """
        result = BulkOperationResult()
        rollback_manager = BulkOperationRollbackManager()
        
        try:
            # Create a savepoint for potential rollback
            savepoint = transaction.savepoint()
            
            for i, fee_data in enumerate(fee_data_list):
                try:
                    # Update progress
                    if progress_tracker:
                        progress_tracker.update_progress(
                            i, f"Processing fee structure {i+1} of {len(fee_data_list)}"
                        )
                    
                    # Validate the fee structure data
                    form = FeeStructureForm(data=fee_data)
                    if form.is_valid():
                        # Create the fee structure
                        fee_structure = form.save()
                        
                        # Add rollback action for the fee structure
                        rollback_manager.add_rollback_action(
                            'delete', FeeStructure, fee_structure.id
                        )
                        
                        # Create student fees for all students in the class
                        students = Student.objects.filter(school_class=fee_structure.school_class)
                        student_fees_created = 0
                        created_student_fee_ids = []
                        
                        for student in students:
                            student_fee, created = StudentFee.objects.get_or_create(
                                student=student,
                                fee_structure=fee_structure,
                                defaults={
                                    'total_amount': fee_structure.total_fee,
                                    'due_date': timezone.now().date() + timedelta(days=30)
                                }
                            )
                            if created:
                                student_fees_created += 1
                                created_student_fee_ids.append(student_fee.id)
                                # Add rollback action for each student fee
                                rollback_manager.add_rollback_action(
                                    'delete', StudentFee, student_fee.id
                                )
                        
                        result.add_success(
                            fee_structure,
                            f"Created fee structure and {student_fees_created} student fees"
                        )
                        
                        logger.info(f"Created fee structure: {fee_structure} with {student_fees_created} student fees")
                        
                    else:
                        error_messages = []
                        for field, errors in form.errors.items():
                            error_messages.extend([f"{field}: {error}" for error in errors])
                        error_msg = "; ".join(error_messages)
                        result.add_error(i, error_msg, fee_data)
                        
                        # Add error to progress tracker
                        if progress_tracker:
                            progress_tracker.add_error(f"Item {i+1}: {error_msg}")
                        
                except IntegrityError as e:
                    error_msg = f"Database integrity error: {str(e)}"
                    result.add_error(i, error_msg, fee_data)
                    logger.error(f"Integrity error creating fee structure {i}: {str(e)}")
                    
                    # Add error to progress tracker
                    if progress_tracker:
                        progress_tracker.add_error(f"Item {i+1}: {error_msg}")
                    
                    # If we have too many errors, consider rolling back
                    if result.error_count > len(fee_data_list) * 0.5:  # More than 50% errors
                        result.add_warning("High error rate detected. Rolling back all changes.")
                        transaction.savepoint_rollback(savepoint)
                        rollback_success = rollback_manager.execute_rollback()
                        if rollback_success:
                            result.add_warning("Successfully rolled back all changes.")
                        else:
                            result.add_error(i, "Rollback failed. Manual cleanup may be required.")
                        break
                    
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    result.add_error(i, error_msg, fee_data)
                    logger.error(f"Unexpected error creating fee structure {i}: {str(e)}")
                    
                    # Add error to progress tracker
                    if progress_tracker:
                        progress_tracker.add_error(f"Item {i+1}: {error_msg}")
                    
        except Exception as e:
            logger.error(f"Critical error in bulk fee structure creation: {str(e)}")
            critical_error = f"Critical operation error: {str(e)}"
            result.add_error(0, critical_error)
            
            # Add critical error to progress tracker
            if progress_tracker:
                progress_tracker.add_error(f"Critical error: {critical_error}")
            
            # Attempt rollback on critical error
            try:
                transaction.savepoint_rollback(savepoint)
                rollback_success = rollback_manager.execute_rollback()
                if rollback_success:
                    result.add_warning("Successfully rolled back all changes due to critical error.")
                else:
                    result.add_error(0, "Critical error rollback failed. Manual cleanup required.")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {str(rollback_error)}")
                result.add_error(0, f"Rollback failed: {str(rollback_error)}")
            
        # Final progress update
        if progress_tracker:
            progress_tracker.update_progress(
                len(fee_data_list), 
                f"Completed: {result.success_count} successful, {result.error_count} failed"
            )
            
        result.finalize()
        
        # Add rollback information to result
        if rollback_manager.rollback_actions:
            result.rollback_info = rollback_manager.get_rollback_summary()
            
        return result
    
    @staticmethod
    @transaction.atomic
    def bulk_process_payments(payment_data_list, user):
        """
        Process multiple payments with validation and balance checking
        
        Args:
            payment_data_list: List of dictionaries containing payment data
            user: User processing the payments
            
        Returns:
            BulkOperationResult: Detailed results of the bulk operation
        """
        result = BulkOperationResult()
        
        try:
            for i, payment_data in enumerate(payment_data_list):
                try:
                    # Add the user who is processing the payment
                    payment_data['received_by'] = user.id
                    
                    # Validate the payment data
                    form = FeePaymentForm(data=payment_data)
                    if form.is_valid():
                        # Create the payment
                        payment = form.save()
                        
                        result.add_success(
                            payment,
                            f"Payment of {payment.amount} processed for {payment.student_fee.student}"
                        )
                        
                        logger.info(f"Processed payment: {payment}")
                        
                    else:
                        error_messages = []
                        for field, errors in form.errors.items():
                            error_messages.extend([f"{field}: {error}" for error in errors])
                        result.add_error(i, "; ".join(error_messages), payment_data)
                        
                except IntegrityError as e:
                    result.add_error(i, f"Database integrity error: {str(e)}", payment_data)
                    logger.error(f"Integrity error processing payment {i}: {str(e)}")
                    
                except Exception as e:
                    result.add_error(i, f"Unexpected error: {str(e)}", payment_data)
                    logger.error(f"Unexpected error processing payment {i}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Critical error in bulk payment processing: {str(e)}")
            result.add_error(0, f"Critical operation error: {str(e)}")
            
        result.finalize()
        return result
    
    @staticmethod
    @transaction.atomic
    def bulk_generate_payroll(month, payroll_structure_id, teacher_ids=None):
        """
        Generate payroll for multiple staff members for a given month
        
        Args:
            month: Date object representing the month (first day of month)
            payroll_structure_id: ID of the payroll structure to use
            teacher_ids: Optional list of teacher IDs (if None, generates for all teachers)
            
        Returns:
            BulkOperationResult: Detailed results of the bulk operation
        """
        result = BulkOperationResult()
        
        try:
            # Get the payroll structure
            try:
                payroll_structure = PayrollStructure.objects.get(id=payroll_structure_id)
            except PayrollStructure.DoesNotExist:
                result.add_error(0, f"Payroll structure with ID {payroll_structure_id} not found")
                result.finalize()
                return result
            
            # Get teachers to process
            if teacher_ids:
                teachers = Teacher.objects.filter(id__in=teacher_ids)
                if teachers.count() != len(teacher_ids):
                    found_ids = list(teachers.values_list('id', flat=True))
                    missing_ids = set(teacher_ids) - set(found_ids)
                    result.add_warning(f"Teachers not found: {missing_ids}")
            else:
                teachers = Teacher.objects.all()
            
            # Process each teacher
            for i, teacher in enumerate(teachers):
                try:
                    # Check if payroll already exists for this month
                    existing_payroll = StaffPayroll.objects.filter(
                        teacher=teacher,
                        month=month
                    ).first()
                    
                    if existing_payroll:
                        result.add_warning(f"Payroll already exists for {teacher} for {month.strftime('%B %Y')}")
                        continue
                    
                    # Create new payroll
                    payroll = StaffPayroll.objects.create(
                        teacher=teacher,
                        payroll_structure=payroll_structure,
                        month=month,
                        gross_salary=payroll_structure.gross_salary,
                        net_salary=0  # Will be calculated
                    )
                    
                    # Calculate net salary
                    payroll.calculate_net_salary()
                    
                    result.add_success(
                        payroll,
                        f"Generated payroll for {teacher} - Net: {payroll.net_salary}"
                    )
                    
                    logger.info(f"Generated payroll: {payroll}")
                    
                except IntegrityError as e:
                    result.add_error(i, f"Database integrity error for {teacher}: {str(e)}")
                    logger.error(f"Integrity error generating payroll for {teacher}: {str(e)}")
                    
                except Exception as e:
                    result.add_error(i, f"Unexpected error for {teacher}: {str(e)}")
                    logger.error(f"Unexpected error generating payroll for {teacher}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Critical error in bulk payroll generation: {str(e)}")
            result.add_error(0, f"Critical operation error: {str(e)}")
            
        result.finalize()
        return result
    
    @staticmethod
    @transaction.atomic
    def bulk_apply_scholarships(scholarship_data_list, user=None):
        """
        Apply scholarships to multiple eligible students
        
        Args:
            scholarship_data_list: List of dictionaries containing scholarship application data
            user: User applying the scholarships
            
        Returns:
            BulkOperationResult: Detailed results of the bulk operation
        """
        result = BulkOperationResult()
        
        try:
            for i, scholarship_data in enumerate(scholarship_data_list):
                try:
                    # Validate the scholarship recipient data
                    form = ScholarshipRecipientForm(data=scholarship_data)
                    if form.is_valid():
                        # Check if scholarship has available slots
                        scholarship = form.cleaned_data['scholarship']
                        current_recipients = ScholarshipRecipient.objects.filter(
                            scholarship=scholarship,
                            status='active'
                        ).count()
                        
                        if current_recipients >= scholarship.max_recipients:
                            result.add_error(
                                i, 
                                f"Scholarship {scholarship.name} has reached maximum recipients ({scholarship.max_recipients})",
                                scholarship_data
                            )
                            continue
                        
                        # Create the scholarship recipient
                        recipient = form.save()
                        
                        result.add_success(
                            recipient,
                            f"Awarded {recipient.awarded_amount} to {recipient.student}"
                        )
                        
                        logger.info(f"Applied scholarship: {recipient}")
                        
                    else:
                        error_messages = []
                        for field, errors in form.errors.items():
                            error_messages.extend([f"{field}: {error}" for error in errors])
                        result.add_error(i, "; ".join(error_messages), scholarship_data)
                        
                except IntegrityError as e:
                    result.add_error(i, f"Database integrity error: {str(e)}", scholarship_data)
                    logger.error(f"Integrity error applying scholarship {i}: {str(e)}")
                    
                except Exception as e:
                    result.add_error(i, f"Unexpected error: {str(e)}", scholarship_data)
                    logger.error(f"Unexpected error applying scholarship {i}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Critical error in bulk scholarship application: {str(e)}")
            result.add_error(0, f"Critical operation error: {str(e)}")
            
        result.finalize()
        return result
    
    @staticmethod
    @transaction.atomic
    def bulk_update_payment_statuses(payment_updates, user=None):
        """
        Update payment statuses in bulk based on external confirmations
        
        Args:
            payment_updates: List of dictionaries with payment ID and new status
            user: User performing the updates
            
        Returns:
            BulkOperationResult: Detailed results of the bulk operation
        """
        result = BulkOperationResult()
        
        try:
            for i, update_data in enumerate(payment_updates):
                try:
                    payment_id = update_data.get('payment_id')
                    new_status = update_data.get('status')
                    reference_number = update_data.get('reference_number', '')
                    
                    if not payment_id or not new_status:
                        result.add_error(i, "Missing payment_id or status", update_data)
                        continue
                    
                    # Get the student fee
                    try:
                        student_fee = StudentFee.objects.get(id=payment_id)
                    except StudentFee.DoesNotExist:
                        result.add_error(i, f"StudentFee with ID {payment_id} not found", update_data)
                        continue
                    
                    # Update the status
                    old_status = student_fee.status
                    student_fee.status = new_status
                    student_fee.save()
                    
                    # If there's a reference number, update the latest payment
                    if reference_number and student_fee.payments.exists():
                        latest_payment = student_fee.payments.latest('payment_date')
                        latest_payment.reference_number = reference_number
                        latest_payment.save()
                    
                    result.add_success(
                        student_fee,
                        f"Updated status from {old_status} to {new_status}"
                    )
                    
                    logger.info(f"Updated payment status: {student_fee} from {old_status} to {new_status}")
                    
                except Exception as e:
                    result.add_error(i, f"Unexpected error: {str(e)}", update_data)
                    logger.error(f"Unexpected error updating payment status {i}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Critical error in bulk payment status update: {str(e)}")
            result.add_error(0, f"Critical operation error: {str(e)}")
            
        result.finalize()
        return result


class BulkOperationProgressTracker:
    """Progress tracking for long-running bulk operations"""
    
    def __init__(self, operation_id, total_items):
        self.operation_id = operation_id
        self.total_items = total_items
        self.processed_items = 0
        self.start_time = timezone.now()
        self.status = 'running'
        self.current_item = None
        self.errors = []
        
    def update_progress(self, processed_count, current_item_description=None):
        """Update the progress of the operation"""
        self.processed_items = processed_count
        self.current_item = current_item_description
        
    def add_error(self, error_message):
        """Add an error to the tracker"""
        self.errors.append({
            'message': error_message,
            'timestamp': timezone.now(),
            'item_index': self.processed_items
        })
        
    def complete(self, status='completed'):
        """Mark the operation as complete"""
        self.status = status
        self.end_time = timezone.now()
        
    def get_progress_percentage(self):
        """Get the current progress as a percentage"""
        if self.total_items == 0:
            return 100
        return (self.processed_items / self.total_items) * 100
        
    def get_estimated_time_remaining(self):
        """Estimate time remaining based on current progress"""
        if self.processed_items == 0:
            return None
            
        elapsed_time = (timezone.now() - self.start_time).total_seconds()
        items_per_second = self.processed_items / elapsed_time
        remaining_items = self.total_items - self.processed_items
        
        if items_per_second > 0:
            return remaining_items / items_per_second
        return None
        
    def to_dict(self):
        """Convert tracker to dictionary for JSON serialization"""
        return {
            'operation_id': self.operation_id,
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'progress_percentage': self.get_progress_percentage(),
            'status': self.status,
            'current_item': self.current_item,
            'start_time': self.start_time.isoformat(),
            'estimated_time_remaining': self.get_estimated_time_remaining(),
            'error_count': len(self.errors),
            'recent_errors': self.errors[-5:] if self.errors else []  # Last 5 errors
        }


# Global progress tracker storage (in production, use Redis or database)
_progress_trackers = {}

def get_progress_tracker(operation_id):
    """Get a progress tracker by operation ID"""
    return _progress_trackers.get(operation_id)

def create_progress_tracker(operation_id, total_items):
    """Create a new progress tracker"""
    tracker = BulkOperationProgressTracker(operation_id, total_items)
    _progress_trackers[operation_id] = tracker
    return tracker

def remove_progress_tracker(operation_id):
    """Remove a progress tracker"""
    if operation_id in _progress_trackers:
        del _progress_trackers[operation_id]