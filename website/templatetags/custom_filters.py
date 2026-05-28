"""
Custom template filters to replace deprecated Django filters
"""
from django import template

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
