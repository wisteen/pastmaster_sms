from django.shortcuts import render
from django.contrib.auth import logout

class SystemLicenseMiddleware:
    """Middleware to check system license and block access if expired"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = ['/static/', '/media/', '/feature-control/']
        self.blocked_paths = ['/login/', '/dashboard/', '/admin/', '/teacher/', '/student/', '/results/', '/attendance/', '/timetable/', '/subjects/', '/classes/', '/exams/', '/quiz/', '/finance/']
    
    def __call__(self, request):
        if any(request.path.startswith(path) for path in self.exempt_paths):
            return self.get_response(request)
        
        should_check_license = any(request.path.startswith(path) for path in self.blocked_paths)
        
        if should_check_license:
            from .models_license import SystemLicense
            can_access, error_message = SystemLicense.check_system_access(getattr(request, 'school', None))
            
            if not can_access:
                if request.user.is_authenticated:
                    logout(request)
                
                return render(request, 'system_expired.html', {
                    'error_message': error_message,
                    'license': SystemLicense.get_active_license(getattr(request, 'school', None)),
                }, status=403)
        
        return self.get_response(request)
