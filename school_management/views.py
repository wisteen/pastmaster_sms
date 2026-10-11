from types import SimpleNamespace

from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import HttpResponseServerError
from django.views.decorators.csrf import ensure_csrf_cookie, requires_csrf_token

from website.views import _visible_pages, _website_profile


@requires_csrf_token
@ensure_csrf_cookie
def csrf_failure(request, reason=""):
    return render(request, '403_csrf.html', {
        'reason': reason,
        'host': request.get_host(),
        'retry_url': request.META.get('HTTP_REFERER') or '/login/?role=super_admin',
    }, status=403)


def handler404(request, exception):
    school = getattr(request, 'school', None)
    website_profile, school_settings = _website_profile(school)
    page = SimpleNamespace(
        id=None,
        title='Page not found',
        meta_title='Page not found',
        meta_description='',
        meta_keywords='',
        og_title='',
        og_description='',
        og_image=None,
    )
    return render(request, '404.html', {
        'active_school': school,
        'page': page,
        'website_profile': website_profile,
        'school_settings': school_settings,
        'nav_pages': _visible_pages(school),
        'canonical_url': request.build_absolute_uri('/'),
    }, status=404)

def handler500(request):
    return HttpResponseServerError(render_to_string('500.html'))
