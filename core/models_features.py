from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


ESSENTIAL_FEATURES = {
    'academic_curriculum',
    'academic_lesson_plans',
    'curriculum_management',
    'lesson_plans',
    'reports_results',
    'reports_broadsheet',
    'system_students',
    'system_staff',
    'system_users',
}

STANDARD_FEATURES = ESSENTIAL_FEATURES | {
    'academic_timetable',
    'timetable_management',
    'communication_announcements',
}

PREMIUM_FEATURES = STANDARD_FEATURES | {
    'attendance_id_cards',
    'id_card_generation',
    'attendance_marking',
    'attendance_visitors',
    'attendance_reports',
    'communication_email',
    'cbt_quiz',
    'financial_expenses',
    'financial_transactions',
    'financial_fees',
    'financial_management',
    'financial_reports',
    'financial_payroll',
    'reports_analytics',
    'financial_analytics',
}

PLAN_FEATURES = {
    'essential': ESSENTIAL_FEATURES,
    'standard': STANDARD_FEATURES,
    'premium': PREMIUM_FEATURES,
}

PLAN_CHOICES = [
    ('essential', 'Essential'),
    ('standard', 'Standard'),
    ('premium', 'Premium'),
]

TENANT_ROLE_CHOICES = [
    ('student', 'Student'),
    ('parent', 'Parent'),
    ('subject_teacher', 'Subject Teacher'),
    ('class_teacher', 'Class Teacher'),
    ('librarian', 'Librarian'),
    ('accountant', 'Accountant'),
    ('bursar', 'Bursar'),
    ('security', 'Security'),
    ('super_admin', 'Super Admin'),
]


class SchoolTenant(models.Model):
    """A school/customer using the SaaS platform."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='essential')
    is_active = models.BooleanField(default=True)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def plan_feature_names(self):
        return PLAN_FEATURES.get(self.plan, set())

    def is_feature_allowed_by_plan(self, feature_name):
        return feature_name in self.plan_feature_names


class SchoolDomain(models.Model):
    """Domain or subdomain mapped to a school tenant."""
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='domains')
    domain = models.CharField(max_length=255, unique=True, help_text='Example: brightfuture.yourdomain.com')
    is_primary = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['school__name', '-is_primary', 'domain']

    def __str__(self):
        return self.domain


class SchoolMembership(models.Model):
    """A user's roles inside one school tenant."""
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='school_memberships')
    primary_role = models.CharField(max_length=20, choices=TENANT_ROLE_CHOICES)
    extra_roles = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['school', 'user']
        ordering = ['school__name', 'user__username']

    def get_all_roles(self):
        roles = [self.primary_role]
        roles.extend(self.extra_roles or [])
        return list(dict.fromkeys(roles))

    def __str__(self):
        return f"{self.user} @ {self.school}"

class FeatureFlag(models.Model):
    """Control features availability across the system"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField()
    is_enabled = models.BooleanField(default=True)
    category = models.CharField(max_length=50, choices=[
        ('academic', 'Academic'),
        ('financial', 'Financial'),
        ('attendance', 'Attendance'),
        ('library', 'Library'),
        ('communication', 'Communication'),
        ('reports', 'Reports'),
        ('system', 'System'),
    ])
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'display_name']
    
    def __str__(self):
        return f"{self.display_name} ({'Enabled' if self.is_enabled else 'Disabled'})"


class TenantFeatureOverride(models.Model):
    """Per-school feature override on top of the school's plan."""
    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='feature_overrides')
    feature = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE, related_name='tenant_overrides')
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['school', 'feature']
        ordering = ['school__name', 'feature__category', 'feature__display_name']

    def __str__(self):
        return f"{self.school} - {self.feature.display_name}: {'Enabled' if self.is_enabled else 'Disabled'}"

class FeatureControlAdmin(models.Model):
    """Admin credentials for feature control"""
    phone = models.CharField(max_length=20, unique=True)
    password_hash = models.CharField(max_length=255)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.phone


class TenantDataExportRequest(models.Model):
    """Tracks verified tenant data export/offboarding packages."""

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    school = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name='data_export_requests')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_export_requests',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_tenant_exports',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requester_name = models.CharField(max_length=150, blank=True)
    requester_email = models.EmailField(blank=True)
    reason = models.TextField(blank=True)
    include_media = models.BooleanField(default=True)
    export_file = models.FileField(upload_to='private/tenant_exports/', blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    record_counts = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.school} export - {self.get_status_display()}"

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)
