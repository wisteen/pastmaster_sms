"""
Custom template filters to replace deprecated Django filters
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='length_is')
def length_is(value, arg):
    """
    Returns True if the length of the value is equal to the argument.
    Replacement for the deprecated length_is filter removed in Django 5.0+
    
    Usage: {% if mylist|length_is:"3" %}
    """
    try:
        return len(value) == int(arg)
    except (ValueError, TypeError):
        return False


@register.filter(name='tenant_background')
def tenant_background(value, image_url=''):
    """Replace legacy seeded parallax backgrounds with the tenant's image."""
    if not value or not image_url:
        return value

    updated = str(value)
    legacy_urls = (
        "/static/new_static/images/bg/bg8.jpg",
        "{% static 'new_static/images/bg/bg8.jpg' %}",
    )
    for legacy_url in legacy_urls:
        updated = updated.replace(legacy_url, image_url)
    return mark_safe(updated)
