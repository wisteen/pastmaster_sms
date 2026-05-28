from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from functools import wraps

def role_required(allowed_roles):
    """
    Decorator to restrict access based on user roles
    Usage: @role_required(['super_admin', 'teacher'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.has_any_role(allowed_roles):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You don't have permission to access this feature.")
        return wrapper
    return decorator

def financial_access_required(view_func):
    """
    Decorator to restrict access to financial features only to authorized roles
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("You don't have permission to access financial features.")
    return wrapper

def accountant_or_admin_required(view_func):
    """
    Decorator specifically for accountant and admin access
    """
    return financial_access_required(view_func)
