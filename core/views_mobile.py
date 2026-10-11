from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models_features import SchoolTenant


@require_GET
def school_directory(request):
    """Return active tenant portals that the attendance app can open."""
    schools = SchoolTenant.objects.filter(
        is_active=True,
        domains__isnull=False,
    ).prefetch_related('domains').distinct().order_by('name', 'id')

    results = []
    for school in schools:
        domains = sorted(
            school.domains.all(),
            key=lambda item: (not item.is_primary, item.domain.lower()),
        )
        domain = next(
            (
                item.domain.strip().lower().rstrip('.')
                for item in domains
                if _is_valid_portal_domain(item.domain)
            ),
            None,
        )
        if not domain:
            continue
        results.append({
            'name': school.name,
            'slug': school.slug,
            'base_url': f'https://{domain}',
        })

    response = JsonResponse({'schools': results})
    response['Cache-Control'] = 'public, max-age=300'
    return response


def _is_valid_portal_domain(value):
    domain = (value or '').strip().lower().rstrip('.')
    return bool(
        domain
        and '.' in domain
        and '/' not in domain
        and ':' not in domain
        and not any(character.isspace() for character in domain)
    )
