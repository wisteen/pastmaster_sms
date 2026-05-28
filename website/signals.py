from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models_features import SchoolTenant
from .services_seed import seed_website_for_school


@receiver(post_save, sender=SchoolTenant)
def create_website_pages_for_new_tenant(sender, instance, created, **kwargs):
    if created and not kwargs.get("raw", False):
        seed_website_for_school(instance, overwrite=False)
