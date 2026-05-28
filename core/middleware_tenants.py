from .models_features import SchoolDomain, SchoolTenant
from .tenant_context import clear_current_school, set_current_school


class SchoolTenantMiddleware:
    """Resolve the active school tenant from an explicit tenant selector or domain."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        school = self._resolve_school(request)
        request.school = school
        set_current_school(school)

        try:
            response = self.get_response(request)
        finally:
            clear_current_school()

        return response

    def _resolve_school(self, request):
        request.school_domain = None
        request.school_domain_matched = False
        school_lookup = request.GET.get('school')
        if school_lookup:
            if str(school_lookup).isdigit():
                school = SchoolTenant.objects.filter(id=school_lookup, is_active=True).first()
            else:
                school = SchoolTenant.objects.filter(slug=school_lookup, is_active=True).first()
            if school:
                request.session['active_school_id'] = school.id
                return school

        host = request.get_host().split(':')[0].lower()
        request.school_host = host
        domain = SchoolDomain.objects.select_related('school').filter(
            domain__iexact=host,
            school__is_active=True
        ).first()
        if domain:
            request.school_domain = domain
            request.school_domain_matched = True
            request.session['active_school_id'] = domain.school_id
            return domain.school

        request.session.pop('active_school_id', None)
        return None
