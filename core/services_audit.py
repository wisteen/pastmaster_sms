"""
Financial Audit Logging Services

This module provides comprehensive audit logging functionality for all financial operations
in the school management system. It tracks all changes, payments, and bulk operations
with immutable audit trail entries.
"""

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from .models import FinancialAuditLog
import json

User = get_user_model()


class AuditLogger:
    """Service for creating immutable audit log entries for financial operations"""
    
    # Model name mappings for audit logging
    MODEL_MAPPINGS = {
        'FeeStructure': 'fee_structure',
        'StudentFee': 'student_fee',
        'FeePayment': 'fee_payment',
        'Scholarship': 'scholarship',
        'ScholarshipRecipient': 'scholarship_recipient',
        'StaffPayroll': 'staff_payroll',
        'FinancialTransaction': 'financial_transaction',
        'PayrollStructure': 'payroll_structure',
    }
    
    @classmethod
    def log_create(cls, instance, user=None, request=None):
        """Log creation of a financial model instance"""
        return cls._create_audit_log(
            operation='create',
            instance=instance,
            user=user,
            request=request,
            changes={'created': cls._serialize_instance(instance)}
        )
    
    @classmethod
    def log_update(cls, instance, old_values, user=None, request=None):
        """Log update of a financial model instance"""
        new_values = cls._serialize_instance(instance)
        changes = {
            'before': old_values,
            'after': new_values,
            'changed_fields': cls._get_changed_fields(old_values, new_values)
        }
        
        return cls._create_audit_log(
            operation='update',
            instance=instance,
            user=user,
            request=request,
            changes=changes
        )
    
    @classmethod
    def log_delete(cls, instance, user=None, request=None):
        """Log deletion of a financial model instance"""
        return cls._create_audit_log(
            operation='delete',
            instance=instance,
            user=user,
            request=request,
            changes={'deleted': cls._serialize_instance(instance)}
        )
    
    @classmethod
    def log_payment(cls, payment_instance, user=None, request=None):
        """Log payment transactions with special handling"""
        return cls._create_audit_log(
            operation='payment',
            instance=payment_instance,
            user=user,
            request=request,
            changes={
                'payment_details': cls._serialize_instance(payment_instance),
                'student_fee_id': payment_instance.student_fee.id,
                'amount': str(payment_instance.amount),
                'payment_method': payment_instance.payment_method
            }
        )
    
    @classmethod
    def log_bulk_operation(cls, operation_type, affected_objects, user=None, request=None, details=None):
        """Log bulk operations with summary information"""
        changes = {
            'operation_type': operation_type,
            'affected_count': len(affected_objects),
            'affected_objects': [
                {
                    'model': obj.__class__.__name__,
                    'id': obj.id,
                    'str_representation': str(obj)
                } for obj in affected_objects
            ],
            'details': details or {}
        }
        
        # Create a single audit log entry for the bulk operation
        # Use the first object for model_name and object_id reference
        first_obj = affected_objects[0] if affected_objects else None
        
        return cls._create_audit_log(
            operation='bulk_operation',
            instance=first_obj,
            user=user,
            request=request,
            changes=changes
        )
    
    @classmethod
    def _create_audit_log(cls, operation, instance, user=None, request=None, changes=None):
        """Create an immutable audit log entry"""
        model_name = cls.MODEL_MAPPINGS.get(instance.__class__.__name__)
        if not model_name:
            # Skip audit logging for non-financial models
            return None
        
        # Extract IP address and user agent from request
        ip_address = None
        user_agent = ''
        
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length
        
        # Create audit log entry
        audit_log = FinancialAuditLog.objects.create(
            operation=operation,
            model_name=model_name,
            object_id=instance.id if instance else 0,
            user=user,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return audit_log
    
    @classmethod
    def _serialize_instance(cls, instance):
        """Serialize model instance to JSON-compatible format"""
        if not instance:
            return {}
        
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            
            # Handle different field types
            if isinstance(field, models.DateTimeField):
                data[field.name] = value.isoformat() if value else None
            elif isinstance(field, models.DateField):
                data[field.name] = value.isoformat() if value else None
            elif isinstance(field, models.DecimalField):
                data[field.name] = str(value) if value is not None else None
            elif isinstance(field, models.ForeignKey):
                data[field.name] = value.id if value else None
                data[f"{field.name}_str"] = str(value) if value else None
            else:
                data[field.name] = value
        
        return data
    
    @classmethod
    def _get_changed_fields(cls, old_values, new_values):
        """Identify which fields changed between old and new values"""
        changed_fields = []
        
        for field_name in old_values.keys():
            if field_name in new_values:
                old_val = old_values[field_name]
                new_val = new_values[field_name]
                
                # Handle decimal comparison
                if isinstance(old_val, str) and isinstance(new_val, str):
                    try:
                        old_decimal = float(old_val) if old_val else 0
                        new_decimal = float(new_val) if new_val else 0
                        if abs(old_decimal - new_decimal) > 0.001:  # Small tolerance for decimal comparison
                            changed_fields.append(field_name)
                    except (ValueError, TypeError):
                        if old_val != new_val:
                            changed_fields.append(field_name)
                else:
                    if old_val != new_val:
                        changed_fields.append(field_name)
        
        return changed_fields
    
    @classmethod
    def _get_client_ip(cls, request):
        """Extract client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AuditLogSearchService:
    """Service for searching and filtering audit logs"""
    
    @classmethod
    def search_logs(cls, filters=None):
        """Search audit logs with various filters"""
        queryset = FinancialAuditLog.objects.all()
        
        if not filters:
            return queryset
        
        # Filter by user
        if filters.get('user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        # Filter by operation type
        if filters.get('operation'):
            queryset = queryset.filter(operation=filters['operation'])
        
        # Filter by model type
        if filters.get('model_name'):
            queryset = queryset.filter(model_name=filters['model_name'])
        
        # Filter by date range
        if filters.get('date_from'):
            queryset = queryset.filter(timestamp__date__gte=filters['date_from'])
        
        if filters.get('date_to'):
            queryset = queryset.filter(timestamp__date__lte=filters['date_to'])
        
        # Filter by object ID
        if filters.get('object_id'):
            queryset = queryset.filter(object_id=filters['object_id'])
        
        # Search in changes JSON field
        if filters.get('search_term'):
            search_term = filters['search_term']
            queryset = queryset.filter(
                models.Q(changes__icontains=search_term) |
                models.Q(user__first_name__icontains=search_term) |
                models.Q(user__last_name__icontains=search_term) |
                models.Q(user__username__icontains=search_term)
            )
        
        return queryset.order_by('-timestamp')
    
    @classmethod
    def get_object_history(cls, model_name, object_id):
        """Get complete audit history for a specific object"""
        return FinancialAuditLog.objects.filter(
            model_name=model_name,
            object_id=object_id
        ).order_by('-timestamp')
    
    @classmethod
    def get_user_activity(cls, user_id, days=30):
        """Get recent activity for a specific user"""
        from datetime import timedelta
        
        since_date = timezone.now() - timedelta(days=days)
        
        return FinancialAuditLog.objects.filter(
            user_id=user_id,
            timestamp__gte=since_date
        ).order_by('-timestamp')
    
    @classmethod
    def get_operation_summary(cls, date_from=None, date_to=None):
        """Get summary of operations within date range"""
        queryset = FinancialAuditLog.objects.all()
        
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        
        # Group by operation type
        summary = queryset.values('operation').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        return summary


class AuditLogMiddleware:
    """Middleware to automatically capture audit information from requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request in thread-local storage for access in models
        from threading import local
        if not hasattr(self, '_local'):
            self._local = local()
        
        self._local.request = request
        
        response = self.get_response(request)
        
        # Clean up
        if hasattr(self._local, 'request'):
            delattr(self._local, 'request')
        
        return response
    
    @classmethod
    def get_current_request(cls):
        """Get current request from thread-local storage"""
        if hasattr(cls, '_local') and hasattr(cls._local, 'request'):
            return cls._local.request
        return None


# Signal handlers for automatic audit logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import (
    FeeStructure, StudentFee, FeePayment, Scholarship, 
    ScholarshipRecipient, StaffPayroll, FinancialTransaction, PayrollStructure
)

# Store original values before save for update logging
_original_values = {}

@receiver(pre_save)
def store_original_values(sender, instance, **kwargs):
    """Store original values before save for update detection"""
    if sender.__name__ in AuditLogger.MODEL_MAPPINGS:
        if instance.pk:  # Only for updates, not creates
            try:
                original = sender.objects.get(pk=instance.pk)
                _original_values[f"{sender.__name__}_{instance.pk}"] = AuditLogger._serialize_instance(original)
            except sender.DoesNotExist:
                pass

@receiver(post_save)
def log_financial_model_save(sender, instance, created, **kwargs):
    """Automatically log financial model saves"""
    if sender.__name__ in AuditLogger.MODEL_MAPPINGS:
        request = AuditLogMiddleware.get_current_request()
        user = request.user if request and request.user.is_authenticated else None
        
        if created:
            AuditLogger.log_create(instance, user=user, request=request)
        else:
            # Get original values for update logging
            key = f"{sender.__name__}_{instance.pk}"
            old_values = _original_values.get(key, {})
            if old_values:
                AuditLogger.log_update(instance, old_values, user=user, request=request)
                # Clean up stored values
                _original_values.pop(key, None)

@receiver(post_delete)
def log_financial_model_delete(sender, instance, **kwargs):
    """Automatically log financial model deletions"""
    if sender.__name__ in AuditLogger.MODEL_MAPPINGS:
        request = AuditLogMiddleware.get_current_request()
        user = request.user if request and request.user.is_authenticated else None
        
        AuditLogger.log_delete(instance, user=user, request=request)

# Special handler for payments
@receiver(post_save, sender=FeePayment)
def log_payment_transaction(sender, instance, created, **kwargs):
    """Special logging for payment transactions"""
    if created:  # Only log new payments, not updates
        request = AuditLogMiddleware.get_current_request()
        user = request.user if request and request.user.is_authenticated else None
        
        AuditLogger.log_payment(instance, user=user, request=request)