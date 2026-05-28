from django.db import models
from django.utils import timezone
from .tenanting import TenantScopedManager

class SystemLicense(models.Model):
    """System license and expiry control"""
    
    school = models.OneToOneField('core.SchoolTenant', on_delete=models.CASCADE, null=True, blank=True, related_name='license')
    school_name = models.CharField(max_length=200)
    license_key = models.CharField(max_length=100, unique=True)
    activation_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    grace_period_days = models.IntegerField(default=7)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    admin_message = models.TextField(blank=True, help_text="Message to display when system is expired")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tenant_filter_path = 'school'
    objects = TenantScopedManager()
    all_objects = models.Manager()
    
    class Meta:
        verbose_name = 'System License'
        verbose_name_plural = 'System Licenses'
    
    def __str__(self):
        return f"{self.school_name} - Expires: {self.expiry_date}"
    
    def is_expired(self):
        """Check if license has expired"""
        return timezone.now().date() > self.expiry_date
    
    def is_in_grace_period(self):
        """Check if in grace period"""
        if not self.is_expired():
            return False
        days_expired = (timezone.now().date() - self.expiry_date).days
        return days_expired <= self.grace_period_days
    
    def days_until_expiry(self):
        """Get days until expiry"""
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    def days_expired(self):
        """Get days since expiry"""
        if not self.is_expired():
            return 0
        delta = timezone.now().date() - self.expiry_date
        return delta.days
    
    def can_login(self):
        """Check if users can login"""
        if not self.is_active:
            return False
        if self.is_expired() and not self.is_in_grace_period():
            return False
        return True
    
    @classmethod
    def get_active_license(cls, school=None):
        """Get the active license"""
        queryset = cls.all_objects.filter(is_active=True)
        if school:
            tenant_license = queryset.filter(school=school).first()
            if tenant_license:
                return tenant_license
            return queryset.filter(school__isnull=True).first()
        return queryset.filter(school__isnull=True).first() or queryset.first()
    
    @classmethod
    def check_system_access(cls, school=None):
        """Check if system access is allowed"""
        license = cls.get_active_license(school=school)
        if not license:
            return False, "No active license found. Contact system administrator."
        
        if not license.can_login():
            if license.is_expired():
                days_expired = license.days_expired()
                message = license.admin_message or f"System license expired {days_expired} days ago. Please contact system administrator to renew."
                return False, message
            else:
                return False, "System access is currently disabled. Contact system administrator."
        
        return True, None
