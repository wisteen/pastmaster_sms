from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models_license import SystemLicense

@admin.register(SystemLicense)
class SystemLicenseAdmin(admin.ModelAdmin):
    list_display = ['school_name', 'school', 'activation_date', 'expiry_date', 'status_badge', 'days_info', 'is_active']
    list_filter = ['school', 'is_active', 'expiry_date']
    search_fields = ['school_name', 'license_key', 'school__name', 'school__slug']
    readonly_fields = ['created_at', 'updated_at', 'status_display', 'days_display']
    
    fieldsets = (
        ('License Information', {
            'fields': ('school', 'school_name', 'license_key', 'is_active')
        }),
        ('Dates', {
            'fields': ('activation_date', 'expiry_date', 'grace_period_days')
        }),
        ('Contact Information', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Custom Message', {
            'fields': ('admin_message',),
            'description': 'This message will be displayed to users when the system is expired.'
        }),
        ('Status', {
            'fields': ('status_display', 'days_display', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        if not obj.is_active:
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 5px 10px; border-radius: 3px;">Inactive</span>'
            )
        elif obj.is_expired():
            if obj.is_in_grace_period():
                return format_html(
                    '<span style="background-color: #ffc107; color: black; padding: 5px 10px; border-radius: 3px;">Grace Period</span>'
                )
            else:
                return format_html(
                    '<span style="background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 3px;">Expired</span>'
                )
        else:
            days_left = obj.days_until_expiry()
            if days_left <= 7:
                return format_html(
                    '<span style="background-color: #ffc107; color: black; padding: 5px 10px; border-radius: 3px;">Expiring Soon</span>'
                )
            else:
                return format_html(
                    '<span style="background-color: #28a745; color: white; padding: 5px 10px; border-radius: 3px;">Active</span>'
                )
    status_badge.short_description = 'Status'
    
    def days_info(self, obj):
        if obj.is_expired():
            days = obj.days_expired()
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">Expired {} day{} ago</span>',
                days, 's' if days != 1 else ''
            )
        else:
            days = obj.days_until_expiry()
            if days <= 7:
                color = '#ffc107'
            else:
                color = '#28a745'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} day{} remaining</span>',
                color, days, 's' if days != 1 else ''
            )
    days_info.short_description = 'Days Info'
    
    def status_display(self, obj):
        if not obj.is_active:
            return format_html('<p style="color: #6c757d; font-weight: bold;">System is INACTIVE</p>')
        elif obj.is_expired():
            if obj.is_in_grace_period():
                return format_html(
                    '<p style="color: #ffc107; font-weight: bold;">System is in GRACE PERIOD ({} days remaining)</p>',
                    obj.grace_period_days - obj.days_expired()
                )
            else:
                return format_html(
                    '<p style="color: #dc3545; font-weight: bold;">System is EXPIRED (Login BLOCKED)</p>'
                )
        else:
            days_left = obj.days_until_expiry()
            if days_left <= 7:
                return format_html(
                    '<p style="color: #ffc107; font-weight: bold;">System is ACTIVE (Expires in {} days)</p>',
                    days_left
                )
            else:
                return format_html(
                    '<p style="color: #28a745; font-weight: bold;">System is ACTIVE</p>'
                )
    status_display.short_description = 'Current Status'
    
    def days_display(self, obj):
        if obj.is_expired():
            return format_html(
                '<p><strong>Expired:</strong> {} days ago</p>'
                '<p><strong>Grace Period:</strong> {} days</p>'
                '<p><strong>Can Login:</strong> {}</p>',
                obj.days_expired(),
                obj.grace_period_days,
                '✅ Yes' if obj.can_login() else '❌ No'
            )
        else:
            return format_html(
                '<p><strong>Days Until Expiry:</strong> {}</p>'
                '<p><strong>Grace Period:</strong> {} days</p>'
                '<p><strong>Can Login:</strong> ✅ Yes</p>',
                obj.days_until_expiry(),
                obj.grace_period_days
            )
    days_display.short_description = 'Days Information'
    
    def save_model(self, request, obj, form, change):
        # Keep one active license per tenant. Global licenses remain separate.
        if obj.is_active:
            SystemLicense.all_objects.filter(school=obj.school).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }
