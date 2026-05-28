"""
Financial Management Permissions and Access Control
Comprehensive permission checks for all financial operations

Requirements: All requirements - Proper permission checks and access control
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)


class FinancialPermissions:
    """
    Centralized permission management for financial operations
    """
    
    # Role-based permissions
    ROLE_PERMISSIONS = {
        'super_admin': [
            'view_dashboard',
            'manage_fees',
            'process_payments',
            'manage_scholarships',
            'manage_payroll',
            'view_analytics',
            'generate_reports',
            'bulk_operations',
            'export_data',
            'view_audit_logs',
            'manage_notifications',
            'run_reconciliation',
            'manage_settings'
        ],
        'admin': [
            'view_dashboard',
            'manage_fees',
            'process_payments',
            'manage_scholarships',
            'view_analytics',
            'generate_reports',
            'export_data',
            'view_audit_logs'
        ],
        'accountant': [
            'view_dashboard',
            'manage_fees',
            'process_payments',
            'view_analytics',
            'generate_reports',
            'export_data'
        ],
        'viewer': [
            'view_dashboard',
            'view_analytics',
            'generate_reports'
        ]
    }
    
    @classmethod
    def has_permission(cls, user, permission):
        """
        Check if user has specific permission
        """
        if not user or not user.is_authenticated:
            return False
        
        user_role = getattr(user, 'role', None)
        if not user_role:
            return False
        
        allowed_permissions = cls.ROLE_PERMISSIONS.get(user_role, [])
        return permission in allowed_permissions
    
    @classmethod
    def has_any_permission(cls, user, permissions):
        """
        Check if user has any of the specified permissions
        """
        return any(cls.has_permission(user, perm) for perm in permissions)
    
    @classmethod
    def has_all_permissions(cls, user, permissions):
        """
        Check if user has all of the specified permissions
        """
        return all(cls.has_permission(user, perm) for perm in permissions)
    
    @classmethod
    def get_user_permissions(cls, user):
        """
        Get all permissions for a user
        """
        if not user or not user.is_authenticated:
            return []
        
        user_role = getattr(user, 'role', None)
        return cls.ROLE_PERMISSIONS.get(user_role, [])
    
    @classmethod
    def can_access_module(cls, user, module):
        """
        Check if user can access a specific financial module
        """
        module_permissions = {
            'dashboard': ['view_dashboard'],
            'fees': ['manage_fees'],
            'payments': ['process_payments'],
            'scholarships': ['manage_scholarships'],
            'payroll': ['manage_payroll'],
            'analytics': ['view_analytics'],
            'reports': ['generate_reports'],
            'bulk': ['bulk_operations'],
            'export': ['export_data'],
            'audit': ['view_audit_logs'],
            'notifications': ['manage_notifications'],
            'reconciliation': ['run_reconciliation']
        }
        
        required_perms = module_permissions.get(module, [])
        return cls.has_any_permission(user, required_perms)


def require_financial_permission(permission):
    """
    Decorator to require specific financial permission
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not FinancialPermissions.has_permission(request.user, permission):
                if request.is_ajax() or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Permission denied',
                        'required_permission': permission
                    }, status=403)
                else:
                    messages.error(request, f'You do not have permission to {permission.replace("_", " ")}')
                    return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_any_financial_permission(*permissions):
    """
    Decorator to require any of the specified permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not FinancialPermissions.has_any_permission(request.user, permissions):
                if request.is_ajax() or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Permission denied',
                        'required_permissions': list(permissions)
                    }, status=403)
                else:
                    messages.error(request, 'You do not have permission to access this resource')
                    return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_all_financial_permissions(*permissions):
    """
    Decorator to require all of the specified permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not FinancialPermissions.has_all_permissions(request.user, permissions):
                if request.is_ajax() or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Permission denied',
                        'required_permissions': list(permissions)
                    }, status=403)
                else:
                    messages.error(request, 'You do not have sufficient permissions')
                    return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_financial_module_access(module):
    """
    Decorator to require access to a specific financial module
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not FinancialPermissions.can_access_module(request.user, module):
                if request.is_ajax() or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'Module access denied',
                        'module': module
                    }, status=403)
                else:
                    messages.error(request, f'You do not have access to the {module} module')
                    return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class FinancialAccessControl:
    """
    Context manager for checking permissions in templates
    """
    
    @staticmethod
    def get_context_permissions(user):
        """
        Get permission context for templates
        """
        return {
            'can_view_dashboard': FinancialPermissions.has_permission(user, 'view_dashboard'),
            'can_manage_fees': FinancialPermissions.has_permission(user, 'manage_fees'),
            'can_process_payments': FinancialPermissions.has_permission(user, 'process_payments'),
            'can_manage_scholarships': FinancialPermissions.has_permission(user, 'manage_scholarships'),
            'can_manage_payroll': FinancialPermissions.has_permission(user, 'manage_payroll'),
            'can_view_analytics': FinancialPermissions.has_permission(user, 'view_analytics'),
            'can_generate_reports': FinancialPermissions.has_permission(user, 'generate_reports'),
            'can_bulk_operations': FinancialPermissions.has_permission(user, 'bulk_operations'),
            'can_export_data': FinancialPermissions.has_permission(user, 'export_data'),
            'can_view_audit_logs': FinancialPermissions.has_permission(user, 'view_audit_logs'),
            'can_manage_notifications': FinancialPermissions.has_permission(user, 'manage_notifications'),
            'can_run_reconciliation': FinancialPermissions.has_permission(user, 'run_reconciliation'),
            'can_manage_settings': FinancialPermissions.has_permission(user, 'manage_settings'),
            'user_permissions': FinancialPermissions.get_user_permissions(user)
        }


# Context processor for adding permissions to all templates
def financial_permissions_context(request):
    """
    Context processor to add financial permissions to all templates
    """
    if request.user.is_authenticated:
        return {
            'financial_permissions': FinancialAccessControl.get_context_permissions(request.user)
        }
    return {
        'financial_permissions': {}
    }

