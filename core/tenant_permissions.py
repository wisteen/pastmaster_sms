from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


PLATFORM_MODELS = {
    'FeatureControlAdmin',
    'FeatureFlag',
    'SchoolDomain',
    'SchoolMembership',
    'SchoolTenant',
    'SystemLicense',
    'TenantFeatureOverride',
}


def grant_school_admin_permissions(user):
    """Keep tenant school admins out of Django admin.

    School administrators manage their tenant through the portal pages. Older
    setup flows still call this helper, so it now removes previously granted
    Django-admin permissions for non-superusers instead of granting new ones.
    """
    if not user or not user.pk:
        return
    if user.is_superuser:
        return

    permissions = Permission.objects.filter(
        content_type__app_label='core',
    ).exclude(
        content_type__model__in={name.lower() for name in PLATFORM_MODELS}
    )

    user.user_permissions.remove(*permissions)
    if user.is_staff:
        user.is_staff = False
        user.save(update_fields=['is_staff'])
