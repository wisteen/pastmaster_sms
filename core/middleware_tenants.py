from django.conf import settings

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

        fallback_school = self._resolve_primary_host_fallback(host)
        if fallback_school:
            request.session['active_school_id'] = fallback_school.id
            return fallback_school

        request.session.pop('active_school_id', None)
        return None

    def _resolve_primary_host_fallback(self, host):
        primary_hosts = {
            item.lower()
            for item in getattr(settings, 'PRIMARY_TENANT_HOSTS', [])
            if item
        }
        if host not in primary_hosts:
            return None

        default_slug = getattr(settings, 'DEFAULT_SCHOOL_SLUG', '')
        if default_slug:
            return SchoolTenant.objects.filter(slug=default_slug, is_active=True).first()

        active_queryset = SchoolTenant.objects.filter(is_active=True).order_by('id')
        non_default_schools = list(active_queryset.exclude(slug='default-school')[:2])
        if len(non_default_schools) == 1:
            return non_default_schools[0]

        active_schools = list(active_queryset[:2])
        if len(active_schools) == 1:
            return active_schools[0]
        return None
