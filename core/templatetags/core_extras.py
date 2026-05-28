from django import template
import json

register = template.Library()

@register.filter
def lookup(dictionary, key):
    return dictionary.get(key)

@register.filter
def pprint(value):
    """Pretty print JSON data"""
    if isinstance(value, dict):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)