"""
Enhanced Error Handling and Reporting for Bulk Operations

This module provides comprehensive error handling, validation, and reporting
capabilities for bulk financial operations with detailed error analysis,
rollback mechanisms, and user-friendly error reporting.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import logging
import traceback
import json
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class BulkOperationError(Exception):
    """Custom exception for bulk operation errors"""
    
    def __init__(self, message, error_code=None, item_index=None, item_data=None):
        super().__init__(message)
        self.error_code = error_code
        self.item_index = item_index
        self.item_data = item_data
        self.timestamp = timezone.now()


class ValidationErrorCollector:
    """Collects and categorizes validation errors during bulk operations"""
    
    def __init__(self):
        self.field_errors = {}
        self.form_errors = []
        self.business_rule_errors = []
        self.data_integrity_errors = []
        self.critical_errors = []
        
    def add_field_error(self, field_name: str, error_message: str, item_index: int = None):
        """Add a field-specific validation error"""
        if field_name not in self.field_errors:
            self.field_errors[field_name] = []
        self.field_errors[field_name].append({
            'message': error_message,
            'item_index': item_index,
            'timestamp': timezone.now()
        })
        
    def add_form_error(self, error_message: str, item_index: int = None):
        """Add a form-level validation error"""
        self.form_errors.append({
            'message': error_message,
            'item_index': item_index,
            'timestamp': timezone.now()
        })
        
    def add_business_rule_error(self, rule_name: str, error_message: str, item_index: int = None):
        """Add a business rule violation error"""
        self.business_rule_errors.append({
            'rule': rule_name,
            'message': error_message,
            'item_index': item_index,
            'timestamp': timezone.now()
        })
        
    def add_data_integrity_error(self, error_message: str, item_index: int = None):
        """Add a data integrity error"""
        self.data_integrity_errors.append({
            'message': error_message,
            'item_index': item_index,
            'timestamp': timezone.now()
        })
        
    def add_critical_error(self, error_message: str, exception: Exception = None):
        """Add a critical system error"""
        self.critical_errors.append({
            'message': error_message,
            'exception_type': type(exception).__name__ if exception else None,
            'traceback': traceback.format_exc() if exception else None,
            'timestamp': timezone.now()
        })
        
    def has_errors(self) -> bool:
        """Check if any errors have been collected"""
        return (bool(self.field_errors) or bool(self.form_errors) or 
                bool(self.business_rule_errors) or bool(self.data_integrity_errors) or 
                bool(self.critical_errors))
        
    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of all collected errors"""
        return {
            'field_errors_count': sum(len(errors) for errors in self.field_errors.values()),
            'form_errors_count': len(self.form_errors),
            'business_rule_errors_count': len(self.business_rule_errors),
            'data_integrity_errors_count': len(self.data_integrity_errors),
            'critical_errors_count': len(self.critical_errors),
            'total_errors': (sum(len(errors) for errors in self.field_errors.values()) + 
                           len(self.form_errors) + len(self.business_rule_errors) + 
                           len(self.data_integrity_errors) + len(self.critical_errors))
        }
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error collector to dictionary for serialization"""
        return {
            'field_errors': self.field_errors,
            'form_errors': self.form_errors,
            'business_rule_errors': self.business_rule_errors,
            'data_integrity_errors': self.data_integrity_errors,
            'critical_errors': self.critical_errors,
            'summary': self.get_error_summary()
        }


class BulkOperationValidator:
    """Validates data before bulk operations to prevent common errors"""
    
    @staticmethod
    def validate_fee_structure_data(fee_data_list: List[Dict]) -> ValidationErrorCollector:
        """Validate fee structure data before bulk creation"""
        collector = ValidationErrorCollector()
        
        for i, fee_data in enumerate(fee_data_list):
            try:
                # Check required fields
                required_fields = ['name', 'school_class', 'term']
                for field in required_fields:
                    if not fee_data.get(field):
                        collector.add_field_error(field, f"Required field missing", i)
                
                # Validate monetary amounts
                monetary_fields = ['tuition_fee', 'development_fee', 'exam_fee', 
                                 'library_fee', 'sports_fee', 'other_fees']
                for field in monetary_fields:
                    value = fee_data.get(field, 0)
                    if value is not None:
                        try:
                            decimal_value = Decimal(str(value))
                            if decimal_value < 0:
                                collector.add_field_error(field, "Amount cannot be negative", i)
                            elif decimal_value > Decimal('999999.99'):
                                collector.add_field_error(field, "Amount exceeds maximum allowed", i)
                        except (InvalidOperation, ValueError):
                            collector.add_field_error(field, "Invalid monetary amount", i)
                
                # Check for duplicate fee structures
                if fee_data.get('school_class') and fee_data.get('term'):
                    # This would need to check against existing data in the database
                    pass
                    
            except Exception as e:
                collector.add_critical_error(f"Error validating fee structure data at index {i}", e)
                
        return collector
    
    @staticmethod
    def validate_payment_data(payment_data_list: List[Dict]) -> ValidationErrorCollector:
        """Validate payment data before bulk processing"""
        collector = ValidationErrorCollector()
        
        for i, payment_data in enumerate(payment_data_list):
            try:
                # Check required fields
                required_fields = ['student_fee', 'amount', 'payment_method']
                for field in required_fields:
                    if not payment_data.get(field):
                        collector.add_field_error(field, f"Required field missing", i)
                
                # Validate payment amount
                amount = payment_data.get('amount')
                if amount is not None:
                    try:
                        decimal_amount = Decimal(str(amount))
                        if decimal_amount <= 0:
                            collector.add_field_error('amount', "Payment amount must be positive", i)
                        elif decimal_amount > Decimal('999999.99'):
                            collector.add_field_error('amount', "Payment amount exceeds maximum", i)
                    except (InvalidOperation, ValueError):
                        collector.add_field_error('amount', "Invalid payment amount", i)
                
                # Validate payment method
                valid_methods = ['cash', 'bank_transfer', 'card', 'online']
                if payment_data.get('payment_method') not in valid_methods:
                    collector.add_field_error('payment_method', f"Invalid payment method", i)
                    
            except Exception as e:
                collector.add_critical_error(f"Error validating payment data at index {i}", e)
                
        return collector
    
    @staticmethod
    def validate_payroll_data(month, payroll_structure_id, teacher_ids=None) -> ValidationErrorCollector:
        """Validate payroll generation parameters"""
        collector = ValidationErrorCollector()
        
        try:
            # Validate month
            if not month:
                collector.add_form_error("Month is required")
            elif not isinstance(month, (str, timezone.datetime.date)):
                collector.add_form_error("Invalid month format")
            
            # Validate payroll structure
            if not payroll_structure_id:
                collector.add_form_error("Payroll structure ID is required")
            else:
                from .models import PayrollStructure
                if not PayrollStructure.objects.filter(id=payroll_structure_id, is_active=True).exists():
                    collector.add_business_rule_error(
                        'payroll_structure_exists',
                        f"Active payroll structure with ID {payroll_structure_id} not found"
                    )
            
            # Validate teacher IDs if provided
            if teacher_ids:
                from .models import Teacher
                existing_teachers = Teacher.objects.filter(id__in=teacher_ids).count()
                if existing_teachers != len(teacher_ids):
                    collector.add_business_rule_error(
                        'teachers_exist',
                        f"Some teacher IDs not found: expected {len(teacher_ids)}, found {existing_teachers}"
                    )
                    
        except Exception as e:
            collector.add_critical_error("Error validating payroll parameters", e)
            
        return collector


class BulkOperationRollbackManager:
    """Manages rollback operations for failed bulk operations"""
    
    def __init__(self):
        self.rollback_actions = []
        self.rollback_log = []
        
    def add_rollback_action(self, action_type: str, model_class, object_id: int, 
                          original_data: Dict = None):
        """Add a rollback action to be executed if needed"""
        self.rollback_actions.append({
            'action_type': action_type,  # 'delete', 'update', 'restore'
            'model_class': model_class,
            'object_id': object_id,
            'original_data': original_data,
            'timestamp': timezone.now()
        })
        
    def execute_rollback(self) -> bool:
        """Execute all rollback actions in reverse order"""
        success = True
        
        # Execute rollback actions in reverse order
        for action in reversed(self.rollback_actions):
            try:
                if action['action_type'] == 'delete':
                    # Delete the created object
                    obj = action['model_class'].objects.get(id=action['object_id'])
                    obj.delete()
                    self.rollback_log.append(f"Deleted {action['model_class'].__name__} {action['object_id']}")
                    
                elif action['action_type'] == 'update':
                    # Restore original data
                    obj = action['model_class'].objects.get(id=action['object_id'])
                    for field, value in action['original_data'].items():
                        setattr(obj, field, value)
                    obj.save()
                    self.rollback_log.append(f"Restored {action['model_class'].__name__} {action['object_id']}")
                    
                elif action['action_type'] == 'restore':
                    # Recreate deleted object
                    action['model_class'].objects.create(**action['original_data'])
                    self.rollback_log.append(f"Restored {action['model_class'].__name__}")
                    
            except Exception as e:
                logger.error(f"Rollback action failed: {action}, Error: {str(e)}")
                self.rollback_log.append(f"FAILED: {action['action_type']} {action['model_class'].__name__} - {str(e)}")
                success = False
                
        return success
        
    def get_rollback_summary(self) -> Dict[str, Any]:
        """Get summary of rollback operations"""
        return {
            'total_actions': len(self.rollback_actions),
            'rollback_log': self.rollback_log,
            'timestamp': timezone.now()
        }


class BulkOperationReporter:
    """Generates detailed reports for bulk operations"""
    
    @staticmethod
    def generate_detailed_report(operation_type: str, result, validation_errors: ValidationErrorCollector = None,
                               rollback_info: Dict = None) -> Dict[str, Any]:
        """Generate a comprehensive report for a bulk operation"""
        
        report = {
            'operation_type': operation_type,
            'timestamp': timezone.now().isoformat(),
            'summary': result.get_summary() if hasattr(result, 'get_summary') else {},
            'performance_metrics': {
                'total_items': getattr(result, 'total_count', 0),
                'success_rate': (getattr(result, 'success_count', 0) / max(getattr(result, 'total_count', 1), 1)) * 100,
                'processing_time': (result.end_time - result.start_time).total_seconds() if hasattr(result, 'end_time') and hasattr(result, 'start_time') else 0
            },
            'errors': {
                'count': getattr(result, 'error_count', 0),
                'details': getattr(result, 'errors', [])
            },
            'warnings': getattr(result, 'warnings', []),
            'successful_items': len(getattr(result, 'successful_items', [])),
            'failed_items': len(getattr(result, 'failed_items', []))
        }
        
        # Add validation errors if provided
        if validation_errors:
            report['validation_errors'] = validation_errors.to_dict()
            
        # Add rollback information if provided
        if rollback_info:
            report['rollback'] = rollback_info
            
        # Add recommendations based on error patterns
        report['recommendations'] = BulkOperationReporter._generate_recommendations(result, validation_errors)
        
        return report
    
    @staticmethod
    def _generate_recommendations(result, validation_errors: ValidationErrorCollector = None) -> List[str]:
        """Generate recommendations based on operation results"""
        recommendations = []
        
        if hasattr(result, 'error_count') and result.error_count > 0:
            error_rate = (result.error_count / max(result.total_count, 1)) * 100
            
            if error_rate > 50:
                recommendations.append("High error rate detected. Consider reviewing data quality before retrying.")
                
            if error_rate > 20:
                recommendations.append("Consider processing data in smaller batches to isolate issues.")
        
        if validation_errors and validation_errors.has_errors():
            summary = validation_errors.get_error_summary()
            
            if summary['field_errors_count'] > 0:
                recommendations.append("Field validation errors detected. Review required fields and data formats.")
                
            if summary['business_rule_errors_count'] > 0:
                recommendations.append("Business rule violations found. Check data against system constraints.")
                
            if summary['critical_errors_count'] > 0:
                recommendations.append("Critical errors encountered. Contact system administrator.")
        
        if not recommendations:
            recommendations.append("Operation completed successfully. No issues detected.")
            
        return recommendations
    
    @staticmethod
    def export_report_to_json(report: Dict[str, Any], filename: str = None) -> str:
        """Export report to JSON format"""
        if not filename:
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bulk_operation_report_{timestamp}.json"
            
        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            return filename
        except Exception as e:
            logger.error(f"Failed to export report to JSON: {str(e)}")
            raise
    
    @staticmethod
    def format_report_for_display(report: Dict[str, Any]) -> str:
        """Format report for human-readable display"""
        lines = []
        lines.append(f"=== BULK OPERATION REPORT ===")
        lines.append(f"Operation: {report.get('operation_type', 'Unknown')}")
        lines.append(f"Timestamp: {report.get('timestamp', 'Unknown')}")
        lines.append("")
        
        # Summary
        summary = report.get('summary', {})
        lines.append("SUMMARY:")
        lines.append(f"  Total Processed: {summary.get('total_processed', 0)}")
        lines.append(f"  Successful: {summary.get('successful', 0)}")
        lines.append(f"  Failed: {summary.get('failed', 0)}")
        lines.append(f"  Success Rate: {summary.get('success_rate', 0):.1f}%")
        lines.append(f"  Duration: {summary.get('duration_seconds', 0):.2f} seconds")
        lines.append("")
        
        # Errors
        if report.get('errors', {}).get('count', 0) > 0:
            lines.append("ERRORS:")
            for error in report.get('errors', {}).get('details', [])[:10]:  # Show first 10 errors
                lines.append(f"  - {error}")
            if len(report.get('errors', {}).get('details', [])) > 10:
                lines.append(f"  ... and {len(report.get('errors', {}).get('details', [])) - 10} more errors")
            lines.append("")
        
        # Warnings
        if report.get('warnings'):
            lines.append("WARNINGS:")
            for warning in report.get('warnings', []):
                lines.append(f"  - {warning}")
            lines.append("")
        
        # Recommendations
        if report.get('recommendations'):
            lines.append("RECOMMENDATIONS:")
            for rec in report.get('recommendations', []):
                lines.append(f"  - {rec}")
            lines.append("")
        
        return "\n".join(lines)


# Utility functions for error handling
def safe_decimal_conversion(value, field_name: str = "amount") -> Tuple[Optional[Decimal], Optional[str]]:
    """Safely convert a value to Decimal with error reporting"""
    if value is None:
        return None, None
        
    try:
        decimal_value = Decimal(str(value))
        if decimal_value < 0:
            return None, f"{field_name} cannot be negative"
        elif decimal_value > Decimal('999999.99'):
            return None, f"{field_name} exceeds maximum allowed value"
        return decimal_value, None
    except (InvalidOperation, ValueError):
        return None, f"Invalid {field_name} format"


def validate_required_fields(data: Dict, required_fields: List[str]) -> List[str]:
    """Validate that all required fields are present and not empty"""
    errors = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            errors.append(f"Required field '{field}' is missing or empty")
    return errors


def log_bulk_operation_start(operation_type: str, item_count: int, user=None):
    """Log the start of a bulk operation"""
    logger.info(f"Starting bulk operation: {operation_type}, Items: {item_count}, User: {user}")


def log_bulk_operation_end(operation_type: str, result, user=None):
    """Log the completion of a bulk operation"""
    if hasattr(result, 'get_summary'):
        summary = result.get_summary()
        logger.info(f"Completed bulk operation: {operation_type}, "
                   f"Success: {summary.get('successful', 0)}, "
                   f"Failed: {summary.get('failed', 0)}, "
                   f"Duration: {summary.get('duration_seconds', 0):.2f}s, "
                   f"User: {user}")
    else:
        logger.info(f"Completed bulk operation: {operation_type}, User: {user}")