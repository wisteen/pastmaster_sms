from django.db import models
from django.db.models import Q


def get_active_school():
    try:
        from .tenant_context import get_current_school
        return get_current_school()
    except Exception:
        return None


class TenantScopedManager(models.Manager):
    """Default manager that scopes records to the active school when available."""

    def get_queryset(self):
        queryset = super().get_queryset()
        school = get_active_school()
        lookup = getattr(self.model, 'tenant_filter_path', None)
        if not school or not lookup:
            return queryset
        if isinstance(lookup, (list, tuple, set)):
            query = Q()
            for path in lookup:
                query |= Q(**{path: school})
            return queryset.filter(query).distinct()
        return queryset.filter(**{lookup: school})


class TenantOwnedMixin(models.Model):
    school = models.ForeignKey(
        'core.SchoolTenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_set',
    )

    tenant_filter_path = 'school'
    objects = TenantScopedManager()
    all_objects = models.Manager()
    tenant_source_paths = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.school_id:
            school = self.get_tenant_school()
            if school:
                self.school = school
        super().save(*args, **kwargs)

    def get_tenant_school(self):
        school = get_active_school()
        if school:
            return school
        for path in self.tenant_source_paths:
            school = resolve_attr_path(self, path)
            if school:
                return school
        return None


def resolve_attr_path(instance, path):
    value = instance
    for part in path.split('__'):
        value = getattr(value, part, None)
        if value is None:
            return None
    return value


def install_tenant_manager(model, lookup):
    model.tenant_filter_path = lookup
    model.add_to_class('all_objects', models.Manager())
    model.add_to_class('objects', TenantScopedManager())
