from django.contrib.auth import logout
from django.shortcuts import redirect, render


class TenantAccessMiddleware:
    """Block authenticated users who are not members of the active tenant."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = (
            '/static/',
            '/media/',
            '/admin/',
            '/feature-control/',
            '/login/',
            '/logout/',
            '/role-selection/',
            '/switch-school/',
        )

    def __call__(self, request):
        user = getattr(request, 'user', None)
        school = getattr(request, 'school', None)

        if (
            user
            and user.is_authenticated
            and school
            and not any(request.path.startswith(path) for path in self.exempt_paths)
            and getattr(user, 'active_school_membership', None) is None
        ):
            logout(request)
            return render(request, 'tenant_no_access.html', {'school': school}, status=403)

        if (
            user
            and user.is_authenticated
            and request.path.startswith('/admin/')
            and not user.is_superuser
            and getattr(user, 'has_role', None)
            and user.has_role('super_admin')
        ):
            return redirect('core:school_admin_dashboard')

        return self.get_response(request)
