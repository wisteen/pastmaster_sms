from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
import hashlib
from datetime import timedelta
from .models_features import FeatureFlag, FeatureControlAdmin, PLAN_CHOICES, SchoolDomain, SchoolMembership, SchoolTenant, TenantFeatureOverride
from .models_license import SystemLicense
from .models import SchoolSettings
from .tenant_context import get_current_school
from .tenant_permissions import grant_school_admin_permissions

def feature_control_login(request):
    """Login to feature control dashboard"""
    if request.session.get('feature_admin_authenticated'):
        return redirect('core:feature_control_dashboard')
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            admin = FeatureControlAdmin.objects.get(phone=phone, password_hash=password_hash)
            admin.last_login = timezone.now()
            admin.save()
            
            request.session['feature_admin_authenticated'] = True
            request.session['feature_admin_phone'] = phone
            return redirect('core:feature_control_dashboard')
        except FeatureControlAdmin.DoesNotExist:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'features/login.html')

def feature_control_dashboard(request):
    """Feature control dashboard"""
    if not request.session.get('feature_admin_authenticated'):
        return redirect('core:feature_control_login')
    
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        selected_school = _get_selected_school(request)
        
        if action_type == 'create_school':
            name = request.POST.get('name', '').strip()
            slug = slugify(request.POST.get('slug', '').strip() or name) or 'school'
            domain = request.POST.get('domain', '').strip().lower()
            plan = request.POST.get('plan', 'essential')
            contact_email = request.POST.get('contact_email', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()
            admin_username = request.POST.get('admin_username', '').strip()
            admin_email = request.POST.get('admin_email', '').strip()
            admin_password = request.POST.get('admin_password', '').strip()

            if not name:
                messages.error(request, 'School name is required')
            elif plan not in dict(PLAN_CHOICES):
                messages.error(request, 'Invalid school plan selected')
            elif SchoolTenant.objects.filter(slug=slug).exists():
                messages.error(request, 'A school with that slug already exists')
            elif domain and SchoolDomain.objects.filter(domain__iexact=domain).exists():
                messages.error(request, 'That domain is already assigned to another school')
            else:
                try:
                    school = SchoolTenant.objects.create(
                        name=name,
                        slug=slug,
                        plan=plan,
                        contact_email=contact_email,
                        contact_phone=contact_phone,
                    )
                    if domain:
                        SchoolDomain.objects.create(school=school, domain=domain, is_primary=True)
                    SystemLicense.all_objects.get_or_create(
                        school=school,
                        defaults={
                            'school_name': school.name,
                            'license_key': _unique_license_key(school),
                            'expiry_date': timezone.now().date() + timedelta(days=30),
                        }
                    )
                    SchoolSettings.all_objects.get_or_create(
                        school=school,
                        defaults={
                            'school_name': school.name,
                            'school_address': 'Configure school address',
                            'principal_name': 'Principal',
                        }
                    )
                    if admin_username and admin_password:
                        User = get_user_model()
                        school_admin, created = User.objects.get_or_create(
                            username=admin_username,
                            defaults={
                                'email': admin_email,
                                'role': 'super_admin',
                                'is_staff': False,
                            }
                        )
                        if school_admin.is_staff:
                            school_admin.is_staff = False
                        if school_admin.role != 'super_admin':
                            school_admin.role = 'super_admin'
                        if created:
                            school_admin.set_password(admin_password)
                        school_admin.save()
                        grant_school_admin_permissions(school_admin)
                        SchoolMembership.objects.update_or_create(
                            school=school,
                            user=school_admin,
                            defaults={
                                'primary_role': 'super_admin',
                                'extra_roles': [],
                                'is_active': True,
                            }
                        )
                    request.session['feature_control_school_id'] = school.id
                    messages.success(request, f'{school.name} tenant created successfully')
                except IntegrityError:
                    messages.error(request, 'Could not create the tenant because one of the unique values already exists')

        elif action_type == 'select_school':
            request.session['feature_control_school_id'] = request.POST.get('school_id')

        elif action_type == 'update_school':
            if selected_school:
                selected_school.name = request.POST.get('name', selected_school.name)
                plan = request.POST.get('plan', selected_school.plan)
                selected_school.plan = plan if plan in dict(PLAN_CHOICES) else selected_school.plan
                selected_school.contact_email = request.POST.get('contact_email', selected_school.contact_email)
                selected_school.contact_phone = request.POST.get('contact_phone', selected_school.contact_phone)
                selected_school.is_active = request.POST.get('is_active') == 'on'
                selected_school.save()
                domain = request.POST.get('domain', '').strip().lower()
                if domain:
                    if SchoolDomain.objects.filter(domain__iexact=domain).exclude(school=selected_school).exists():
                        messages.error(request, 'That domain is already assigned to another school')
                        return redirect('core:feature_control_dashboard')
                    primary_domain = selected_school.domains.filter(is_primary=True).first() or selected_school.domains.first()
                    if primary_domain:
                        primary_domain.domain = domain
                        primary_domain.is_primary = True
                        primary_domain.save()
                    else:
                        SchoolDomain.objects.create(school=selected_school, domain=domain, is_primary=True)
                messages.success(request, f'{selected_school.name} updated')
            else:
                messages.error(request, 'Select a school first')

        elif action_type == 'toggle_feature':
            feature_id = request.POST.get('feature_id')
            action = request.POST.get('action')
            
            try:
                feature = FeatureFlag.objects.get(id=feature_id)
                if selected_school:
                    override, _ = TenantFeatureOverride.objects.get_or_create(
                        school=selected_school,
                        feature=feature,
                        defaults={'is_enabled': selected_school.is_feature_allowed_by_plan(feature.name)}
                    )
                    override.is_enabled = (action == 'enable')
                    override.save()
                    messages.success(request, f'{feature.display_name} has been {"enabled" if override.is_enabled else "disabled"} for {selected_school.name}')
                else:
                    feature.is_enabled = (action == 'enable')
                    feature.save()
                    messages.success(request, f'{feature.display_name} has been {"enabled" if feature.is_enabled else "disabled"} globally')
            except FeatureFlag.DoesNotExist:
                messages.error(request, 'Feature not found')

        elif action_type == 'reset_feature_override':
            feature_id = request.POST.get('feature_id')
            if selected_school:
                TenantFeatureOverride.objects.filter(school=selected_school, feature_id=feature_id).delete()
                messages.success(request, 'Feature override reset to plan default')
        
        elif action_type == 'update_license':
            selected_school = _get_selected_school(request)
            expiry_date = request.POST.get('expiry_date')
            grace_period = request.POST.get('grace_period_days', 7)
            contact_email = request.POST.get('contact_email', '')
            contact_phone = request.POST.get('contact_phone', '')
            admin_message = request.POST.get('admin_message', '')
            
            license = SystemLicense.get_active_license(school=selected_school)
            if selected_school and (not license or license.school_id != selected_school.id):
                license, _ = SystemLicense.all_objects.get_or_create(
                    school=selected_school,
                    defaults={
                        'school_name': selected_school.name,
                        'license_key': _unique_license_key(selected_school),
                        'expiry_date': timezone.now().date() + timedelta(days=30),
                    },
                )
            if license:
                license.expiry_date = expiry_date
                license.grace_period_days = int(grace_period)
                license.contact_email = contact_email
                license.contact_phone = contact_phone
                license.admin_message = admin_message
                license.save()
                messages.success(request, 'System license updated successfully')
            else:
                messages.error(request, 'No active license found')
        
        return redirect('core:feature_control_dashboard')
    
    selected_school = _get_selected_school(request)
    features = FeatureFlag.objects.all()
    overrides = {}
    if selected_school:
        overrides = {
            override.feature_id: override
            for override in TenantFeatureOverride.objects.filter(school=selected_school).select_related('feature')
        }
        for feature in features:
            override = overrides.get(feature.id)
            feature.effective_enabled = override.is_enabled if override else selected_school.is_feature_allowed_by_plan(feature.name)
            feature.plan_enabled = selected_school.is_feature_allowed_by_plan(feature.name)
            feature.has_override = bool(override)
    else:
        for feature in features:
            feature.effective_enabled = feature.is_enabled
            feature.plan_enabled = feature.is_enabled
            feature.has_override = False

    features_by_category = {}
    for feature in features:
        if feature.category not in features_by_category:
            features_by_category[feature.category] = []
        features_by_category[feature.category].append(feature)
    
    license = SystemLicense.get_active_license(school=selected_school)
    
    context = {
        'features_by_category': features_by_category,
        'total_features': features.count(),
        'enabled_features': sum(1 for feature in features if feature.effective_enabled),
        'license': license,
        'schools': SchoolTenant.objects.prefetch_related('domains').all(),
        'selected_school': selected_school,
        'primary_domain': selected_school.domains.filter(is_primary=True).first() if selected_school else None,
        'plan_choices': PLAN_CHOICES,
    }
    return render(request, 'features/dashboard.html', context)

def feature_control_logout(request):
    """Logout from feature control"""
    request.session.flush()
    messages.success(request, 'Logged out successfully')
    return redirect('core:feature_control_login')

def is_feature_enabled(feature_name):
    """Helper function to check if a feature is enabled"""
    from .decorators_features import is_feature_enabled_for_school
    enabled, _ = is_feature_enabled_for_school(feature_name, get_current_school())
    return enabled


def _get_selected_school(request):
    school_id = request.POST.get('school_id') or request.GET.get('school') or request.session.get('feature_control_school_id')
    school = None
    if school_id:
        lookup = str(school_id)
        if lookup.isdigit():
            school = SchoolTenant.objects.filter(id=lookup).first()
        if not school:
            school = SchoolTenant.objects.filter(slug=lookup).first()
    if not school:
        school = SchoolTenant.objects.first()
    if school:
        request.session['feature_control_school_id'] = school.id
    return school


def _unique_license_key(school):
    base_key = f'{school.slug.upper()}-TRIAL'
    license_key = base_key
    suffix = 1
    while SystemLicense.all_objects.filter(license_key=license_key).exists():
        suffix += 1
        license_key = f'{base_key}-{suffix}'
    return license_key
