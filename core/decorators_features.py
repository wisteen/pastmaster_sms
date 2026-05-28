from functools import wraps
from django.shortcuts import render
from django.contrib import messages
from .models_features import FeatureFlag, TenantFeatureOverride


def is_feature_enabled_for_school(feature_name, school=None):
    try:
        feature = FeatureFlag.objects.get(name=feature_name)
    except FeatureFlag.DoesNotExist:
        return True, None

    if not feature.is_enabled:
        return False, feature

    if not school:
        return True, feature

    override = TenantFeatureOverride.objects.filter(school=school, feature=feature).first()
    if override:
        return override.is_enabled, feature

    return school.is_feature_allowed_by_plan(feature_name), feature

def feature_required(feature_name):
    """Decorator to check if a feature is enabled"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            enabled, feature = is_feature_enabled_for_school(feature_name, getattr(request, 'school', None))
            if not enabled and feature:
                messages.error(request, f'{feature.display_name} is not available on this school portal plan.')
                return render(request, 'features/disabled.html', {
                    'feature': feature,
                    'school': getattr(request, 'school', None),
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
