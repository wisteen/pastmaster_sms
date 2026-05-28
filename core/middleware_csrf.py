from urllib.parse import urlparse

from django.middleware.csrf import CsrfViewMiddleware

from .models_features import SchoolDomain


class TenantAwareCsrfViewMiddleware(CsrfViewMiddleware):
    """Allow CSRF origins registered as tenant domains."""

    def _origin_verified(self, request):
        if super()._origin_verified(request):
            return True
        return self._tenant_origin_allowed(request, request.META.get('HTTP_ORIGIN'))

    def _check_referer(self, request):
        if self._tenant_origin_allowed(request, request.META.get('HTTP_REFERER')):
            return
        return super()._check_referer(request)

    def _tenant_origin_allowed(self, request, origin):
        if not origin:
            return False

        try:
            parsed = urlparse(origin)
        except ValueError:
            return False

        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return False

        origin_host = parsed.hostname.lower()
        request_host = request.get_host().split(':')[0].lower()

        if origin_host == request_host and getattr(request, 'school_domain_matched', False):
            return True

        school = getattr(request, 'school', None)
        domains = SchoolDomain.objects.filter(
            domain__iexact=origin_host,
            school__is_active=True,
        )
        if school is not None:
            domains = domains.filter(school=school)

        return domains.exists()
