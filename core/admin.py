from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import *
from .models_features import FeatureFlag, SchoolDomain, SchoolMembership, SchoolTenant, TenantFeatureOverride, TenantDataExportRequest
from .services_tenant_export import generate_tenant_export
from .models_biodata import StudentBioData, Guardian, StaffBioData
from .academic_choices import existing_session_choices, setup_session_choices


class CustomUserChangeForm(UserAdmin.form):
    extra_roles = forms.MultipleChoiceField(
        choices=User.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Grant additional dashboard/access roles without changing the primary role.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['extra_roles'].initial = self.instance.extra_roles or []

    def clean_extra_roles(self):
        return self.cleaned_data.get('extra_roles') or []

# Inline classes for bio-data
class StudentBioDataInline(admin.StackedInline):
    model = StudentBioData
    can_delete = False
    verbose_name_plural = 'Bio Data'
    fieldsets = (
        ('Personal Information', {
            'fields': ('date_of_birth', 'place_of_birth', 'nationality', 'state_of_origin', 'lga', 'religion', 
                      'home_address', 'phone_number', 'email', 'passport_photo')
        }),
        ('Health Records', {
            'fields': ('blood_group', 'genotype', 'allergies', 'medical_conditions', 'medications',
                      'doctor_name', 'doctor_phone', 'hospital_name', 'hospital_address'),
            'classes': ('collapse',)
        }),
        ('Previous School', {
            'fields': ('previous_school_name', 'previous_school_address', 'previous_class', 
                      'reason_for_leaving', 'transfer_certificate'),
            'classes': ('collapse',)
        }),
        ('Government IDs', {
            'fields': ('birth_certificate_number', 'nin'),
            'classes': ('collapse',)
        }),
        ('Experience', {
            'fields': ('hobbies', 'special_talents'),
            'classes': ('collapse',)
        }),
    )

class GuardianInline(admin.TabularInline):
    model = Guardian
    extra = 0
    fields = ('user', 'relationship', 'title', 'first_name', 'last_name', 'phone_number', 'is_primary_contact', 'is_emergency_contact')

class StaffBioDataInline(admin.StackedInline):
    model = StaffBioData
    can_delete = False
    verbose_name_plural = 'Bio Data'
    fields = ('date_of_birth', 'place_of_birth', 'marital_status', 'phone_number', 'email', 
              'date_of_employment', 'employment_type', 'department', 'position')

# Feature-based model visibility
def is_feature_enabled(feature_name):
    from .decorators_features import is_feature_enabled_for_school
    from .tenant_context import get_current_school

    enabled, _ = is_feature_enabled_for_school(feature_name, get_current_school())
    return enabled


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'category', 'is_enabled', 'updated_at')
    list_filter = ('category', 'is_enabled')
    search_fields = ('display_name', 'name', 'description')


@admin.register(GlobalAdvertisement)
class GlobalAdvertisementAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'priority', 'starts_at', 'ends_at', 'created_by', 'updated_at')
    list_filter = ('is_active', 'starts_at', 'ends_at')
    search_fields = ('title', 'message', 'destination_url')
    readonly_fields = ('created_by', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(CurriculumInstallation)
class CurriculumInstallationAdmin(admin.ModelAdmin):
    list_display = ('school', 'provider', 'academic_year', 'installed_by', 'installed_at')
    list_filter = ('provider', 'academic_year', 'installed_at')
    search_fields = ('school__name', 'installed_by__username')
    readonly_fields = (
        'school', 'provider', 'levels', 'academic_year', 'installed_by',
        'include_calendar', 'activated_first_term', 'summary', 'installed_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'extra_roles_display', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Portal Access', {'fields': ('role', 'extra_roles', 'phone')}),
    )

    def extra_roles_display(self, obj):
        return ', '.join(obj.extra_roles or [])
    extra_roles_display.short_description = 'Granted Roles'


class SchoolDomainInline(admin.TabularInline):
    model = SchoolDomain
    extra = 1


class TenantFeatureOverrideInline(admin.TabularInline):
    model = TenantFeatureOverride
    extra = 0
    autocomplete_fields = ('feature',)


class SchoolMembershipInline(admin.TabularInline):
    model = SchoolMembership
    extra = 0
    autocomplete_fields = ('user',)


@admin.register(SchoolTenant)
class SchoolTenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'plan', 'is_active', 'contact_email', 'created_at')
    list_filter = ('plan', 'is_active')
    search_fields = ('name', 'slug', 'contact_email', 'contact_phone')
    inlines = [SchoolDomainInline, TenantFeatureOverrideInline]
    readonly_fields = ('memberships_link',)
    actions = ['create_data_export_request', 'create_and_generate_data_export', 'deactivate_selected_schools']

    @admin.display(description='School memberships')
    def memberships_link(self, obj):
        if not obj or not obj.pk:
            return 'Save the school before managing memberships.'
        url = reverse('admin:core_schoolmembership_changelist')
        return format_html(
            '<a class="button" href="{}?school__id__exact={}">Manage {} memberships</a>',
            url,
            obj.pk,
            obj.memberships.count(),
        )

    def create_data_export_request(self, request, queryset):
        created = 0
        for school in queryset:
            TenantDataExportRequest.objects.create(
                school=school,
                requested_by=request.user,
                requester_name=request.user.get_full_name() or request.user.username,
                requester_email=request.user.email,
                reason='Created from School Tenant admin action.',
            )
            created += 1
        self.message_user(
            request,
            f'{created} tenant data export request(s) created. Open Tenant data export requests, select the request, then run "Generate selected tenant export ZIPs" to create the downloadable file.'
        )
    create_data_export_request.short_description = 'Create data export request for selected schools'

    def create_and_generate_data_export(self, request, queryset):
        generated = 0
        failed = 0
        for school in queryset:
            export_request = TenantDataExportRequest.objects.create(
                school=school,
                requested_by=request.user,
                approved_by=request.user,
                requester_name=request.user.get_full_name() or request.user.username,
                requester_email=request.user.email,
                reason='Created and generated from School Tenant admin action.',
                approved_at=timezone.now(),
            )
            try:
                generate_tenant_export(export_request)
                generated += 1
            except Exception:
                failed += 1
        if generated:
            self.message_user(request, f'{generated} tenant export ZIP(s) generated. Open Tenant data export requests to download.')
        if failed:
            self.message_user(request, f'{failed} tenant export ZIP(s) failed. Check the export request error message.', level='error')
    create_and_generate_data_export.short_description = 'Create and generate tenant export ZIP for selected schools'

    def deactivate_selected_schools(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} school tenant(s) deactivated.')
    deactivate_selected_schools.short_description = 'Deactivate selected schools'

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SchoolDomain)
class SchoolDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'school', 'is_primary', 'created_at')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'school__name')


@admin.register(TenantFeatureOverride)
class TenantFeatureOverrideAdmin(admin.ModelAdmin):
    list_display = ('school', 'feature', 'is_enabled', 'updated_at')
    list_filter = ('school', 'feature__category', 'is_enabled')
    search_fields = ('school__name', 'feature__display_name', 'feature__name')


@admin.register(SchoolMembership)
class SchoolMembershipAdmin(admin.ModelAdmin):
    list_display = ('school', 'user', 'primary_role', 'extra_roles_display', 'is_active')
    list_filter = ('school', 'primary_role', 'is_active')
    search_fields = ('school__name', 'user__username', 'user__email', 'user__first_name', 'user__last_name')

    def extra_roles_display(self, obj):
        return ', '.join(obj.extra_roles or [])
    extra_roles_display.short_description = 'Extra Roles'


@admin.register(TenantDataExportRequest)
class TenantDataExportRequestAdmin(admin.ModelAdmin):
    list_display = (
        'school',
        'status',
        'requester_name',
        'requested_by',
        'requested_at',
        'generated_at',
        'expires_at',
        'file_size_display',
        'generate_link',
        'download_link',
    )
    list_filter = ('status', 'include_media', 'requested_at', 'generated_at', 'school')
    search_fields = ('school__name', 'school__slug', 'requester_name', 'requester_email', 'reason')
    readonly_fields = (
        'requested_by',
        'approved_by',
        'status',
        'export_file',
        'file_size',
        'file_size_display',
        'record_counts',
        'error_message',
        'requested_at',
        'approved_at',
        'generated_at',
        'expires_at',
        'updated_at',
        'generate_link',
        'download_link',
    )
    actions = ['generate_exports', 'cancel_exports', 'deactivate_exported_schools']

    fieldsets = (
        ('Request', {
            'fields': ('school', 'requester_name', 'requester_email', 'reason', 'include_media', 'notes')
        }),
        ('Workflow', {
            'fields': ('status', 'requested_by', 'approved_by', 'requested_at', 'approved_at', 'generated_at', 'expires_at')
        }),
        ('Export Package', {
            'fields': ('generate_link', 'download_link', 'export_file', 'file_size_display', 'record_counts', 'error_message')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/download/',
                self.admin_site.admin_view(self.download_export),
                name='core_tenantdataexportrequest_download',
            ),
            path(
                '<int:object_id>/generate/',
                self.admin_site.admin_view(self.generate_export),
                name='core_tenantdataexportrequest_generate',
            ),
        ]
        return custom_urls + urls

    def save_model(self, request, obj, form, change):
        if not change and not obj.requested_by_id:
            obj.requested_by = request.user
            if not obj.requester_name:
                obj.requester_name = request.user.get_full_name() or request.user.username
            if not obj.requester_email:
                obj.requester_email = request.user.email
        super().save_model(request, obj, form, change)

    def generate_exports(self, request, queryset):
        generated = 0
        failed = 0
        for export_request in queryset:
            if export_request.status == export_request.STATUS_CANCELLED:
                continue
            export_request.approved_by = request.user
            export_request.approved_at = timezone.now()
            export_request.save(update_fields=['approved_by', 'approved_at', 'updated_at'])
            try:
                generate_tenant_export(export_request)
                generated += 1
            except Exception:
                failed += 1
        if generated:
            self.message_user(request, f'{generated} tenant export package(s) generated.')
        if failed:
            self.message_user(request, f'{failed} tenant export package(s) failed. Check error messages.', level='error')
    generate_exports.short_description = 'Generate selected tenant export ZIPs'

    def generate_export(self, request, object_id):
        export_request = self.get_object(request, object_id)
        if not export_request:
            raise Http404('Export request not found.')
        if export_request.status == export_request.STATUS_CANCELLED:
            self.message_user(request, 'Cancelled export requests cannot be generated.', level='error')
            return HttpResponseRedirect(reverse('admin:core_tenantdataexportrequest_change', args=[object_id]))

        export_request.approved_by = request.user
        export_request.approved_at = timezone.now()
        export_request.save(update_fields=['approved_by', 'approved_at', 'updated_at'])
        try:
            generate_tenant_export(export_request)
            self.message_user(request, 'Tenant export ZIP generated. Use Download ZIP to retrieve it.')
        except Exception:
            self.message_user(request, 'Tenant export generation failed. Check the error message below.', level='error')
        return HttpResponseRedirect(reverse('admin:core_tenantdataexportrequest_change', args=[object_id]))

    def cancel_exports(self, request, queryset):
        updated = queryset.exclude(status=TenantDataExportRequest.STATUS_READY).update(
            status=TenantDataExportRequest.STATUS_CANCELLED,
            updated_at=timezone.now(),
        )
        self.message_user(request, f'{updated} pending export request(s) cancelled.')
    cancel_exports.short_description = 'Cancel selected pending exports'

    def deactivate_exported_schools(self, request, queryset):
        ready_exports = queryset.filter(status=TenantDataExportRequest.STATUS_READY)
        school_ids = ready_exports.values_list('school_id', flat=True)
        updated = SchoolTenant.objects.filter(id__in=school_ids).update(is_active=False)
        self.message_user(request, f'{updated} school tenant(s) deactivated.')
    deactivate_exported_schools.short_description = 'Deactivate schools with ready exports'

    def download_export(self, request, object_id):
        export_request = self.get_object(request, object_id)
        if not export_request or export_request.status != export_request.STATUS_READY or not export_request.export_file:
            raise Http404('Export file is not available.')
        export_request.export_file.open('rb')
        return FileResponse(
            export_request.export_file,
            as_attachment=True,
            filename=export_request.export_file.name.split('/')[-1],
        )

    def download_link(self, obj):
        if not obj or obj.status != obj.STATUS_READY or not obj.export_file:
            return '-'
        url = reverse('admin:core_tenantdataexportrequest_download', args=[obj.pk])
        return format_html('<a class="button" href="{}">Download ZIP</a>', url)
    download_link.short_description = 'Download'

    def generate_link(self, obj):
        if not obj or not obj.pk:
            return '-'
        if obj.status == obj.STATUS_CANCELLED:
            return 'Cancelled'
        if obj.status == obj.STATUS_PROCESSING:
            return 'Processing'
        url = reverse('admin:core_tenantdataexportrequest_generate', args=[obj.pk])
        label = 'Regenerate ZIP' if obj.status == obj.STATUS_READY else 'Generate ZIP'
        return format_html('<a class="button" href="{}">{}</a>', url, label)
    generate_link.short_description = 'Generate'

    def file_size_display(self, obj):
        if not obj or not obj.file_size:
            return '-'
        size = obj.file_size
        for unit in ['bytes', 'KB', 'MB', 'GB']:
            if size < 1024 or unit == 'GB':
                return f'{size:.1f} {unit}' if unit != 'bytes' else f'{size} bytes'
            size = size / 1024
        return f'{obj.file_size} bytes'
    file_size_display.short_description = 'File size'

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


from . import admin_license  # noqa: E402,F401

@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'stream', 'created_at')
    search_fields = ('name', 'stream')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'pass_mark', 'created_at')
    search_fields = ('name', 'code')

@admin.register(GradingSystem)
class GradingSystemAdmin(admin.ModelAdmin):
    list_display = ('grade', 'min_score', 'max_score', 'grade_point', 'remark')
    ordering = ['-min_score']

@admin.register(ResultComponent)
class ResultComponentAdmin(admin.ModelAdmin):
    list_display = ('school_class', 'subject', 'component_name', 'weight', 'max_score')
    list_filter = ('school_class', 'subject')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'school_class', 'is_promoted', 'promoted_to')
    list_filter = ('school_class', 'is_promoted')
    search_fields = ('student_id', 'user__first_name', 'user__last_name')
    readonly_fields = ('student_id',)
    inlines = [StudentBioDataInline, GuardianInline]

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name')
    filter_horizontal = ('subjects', 'classes')
    inlines = [StaffBioDataInline]

@admin.register(ClassTeacher)
class ClassTeacherAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'school_class', 'can_assign_parent_wards', 'can_print_download_results')
    list_filter = ('teacher', 'school_class', 'can_assign_parent_wards', 'can_print_download_results')

@admin.register(HeadTeacher)
class HeadTeacherAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'title', 'classes_list')
    filter_horizontal = ('classes',)
    
    def classes_list(self, obj):
        return ", ".join([c.name for c in obj.classes.all()])
    classes_list.short_description = 'Classes'

class TermAdminForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = getattr(self.instance, 'school', None)
        self.fields['session'].widget = forms.Select(choices=setup_session_choices(school))


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    form = TermAdminForm
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)

@admin.register(ComponentResult)
class ComponentResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'component', 'term', 'score')
    list_filter = ('term', 'component__subject')

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'term', 'total_score', 'grade', 'grade_point')
    list_filter = ('term', 'subject', 'grade')
    search_fields = ('student__student_id', 'student__user__first_name')

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'school_class', 'teacher', 'status', 'start_time')
    list_filter = ('status', 'subject', 'school_class', 'shuffle_questions', 'full_screen_mode')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'question_type', 'question_text', 'max_marks')
    list_filter = ('question_type', 'quiz__subject')

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'student', 'final_score', 'is_submitted', 'is_graded', 'tab_switches')
    list_filter = ('is_submitted', 'is_graded', 'quiz__subject')

@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'selected_answer', 'is_correct', 'manual_score')
    list_filter = ('is_correct', 'question__question_type')


@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'school', 'back_home_url', 'principal_name', 'proprietor_name')
    search_fields = ('school_name', 'school__name', 'back_home_url')


@admin.register(Psychomotor)
class PsychomotorAdmin(admin.ModelAdmin):
    list_display = ('student', 'term')
    list_filter = ('term', 'student__school_class')


@admin.register(EffectiveDomain)
class EffectiveDomainAdmin(admin.ModelAdmin):
    list_display = ('student', 'term')
    list_filter = ('term', 'student__school_class')


@admin.register(LearnerDomainCriterion)
class LearnerDomainCriterionAdmin(admin.ModelAdmin):
    list_display = ('school', 'domain_type', 'name', 'display_order', 'is_active')
    list_filter = ('school', 'domain_type', 'is_active')
    search_fields = ('name', 'school__name')


@admin.register(LearnerDomainRating)
class LearnerDomainRatingAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'criterion', 'value')
    list_filter = ('term', 'criterion__domain_type', 'criterion')
    search_fields = ('student__student_id', 'student__user__first_name', 'student__user__last_name', 'criterion__name')

@admin.register(ResultToken)
class ResultTokenAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'token', 'uses_count', 'max_uses', 'created_at')
    list_filter = ('term', 'student__school_class')
    search_fields = ('token', 'student__student_id', 'student__user__first_name', 'student__user__last_name')
    readonly_fields = ('token', 'created_at')
    
    def has_add_permission(self, request):
        return False


# Academic Management Admin Classes

class LearningObjectiveInline(admin.TabularInline):
    model = LearningObjective
    extra = 1
    fields = ('title', 'description', 'subject', 'grade_level', 'order')
    ordering = ('order',)

class SyllabusContentInline(admin.TabularInline):
    model = SyllabusContent
    extra = 1
    fields = ('subject', 'content', 'order')
    ordering = ('order',)

@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return is_feature_enabled('academic_curriculum')
    
    list_display = ('title', 'academic_year', 'is_published', 'subjects_count', 'objectives_count', 'created_by', 'created_at')
    list_filter = ('academic_year', 'is_published', 'subjects', 'created_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('subjects',)
    inlines = [LearningObjectiveInline, SyllabusContentInline]
    readonly_fields = ('created_at', 'updated_at')
    actions = ['publish_curricula', 'unpublish_curricula', 'duplicate_curriculum']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'academic_year', 'subjects')
        }),
        ('Publication', {
            'fields': ('is_published',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def subjects_count(self, obj):
        return obj.subjects.count()
    subjects_count.short_description = 'Subjects'
    
    def objectives_count(self, obj):
        return obj.learning_objectives.count()
    objectives_count.short_description = 'Learning Objectives'
    
    def publish_curricula(self, request, queryset):
        updated = 0
        for curriculum in queryset:
            if curriculum.learning_objectives.exists():
                curriculum.is_published = True
                curriculum.save()
                updated += 1
        
        if updated:
            self.message_user(request, f'{updated} curricula published successfully.')
        else:
            self.message_user(request, 'No curricula could be published. Ensure they have learning objectives.', level='warning')
    publish_curricula.short_description = 'Publish selected curricula'
    
    def unpublish_curricula(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} curricula unpublished successfully.')
    unpublish_curricula.short_description = 'Unpublish selected curricula'
    
    def duplicate_curriculum(self, request, queryset):
        for curriculum in queryset:
            # Create a copy with a new title
            new_curriculum = Curriculum.objects.create(
                title=f"{curriculum.title} (Copy)",
                description=curriculum.description,
                academic_year=curriculum.academic_year,
                created_by=request.user,
                is_published=False
            )
            new_curriculum.subjects.set(curriculum.subjects.all())
            
            # Copy learning objectives
            for objective in curriculum.learning_objectives.all():
                LearningObjective.objects.create(
                    curriculum=new_curriculum,
                    title=objective.title,
                    description=objective.description,
                    subject=objective.subject,
                    grade_level=objective.grade_level,
                    order=objective.order
                )
            
            # Copy syllabus content
            for content in curriculum.syllabus_contents.all():
                SyllabusContent.objects.create(
                    curriculum=new_curriculum,
                    subject=content.subject,
                    content=content.content,
                    order=content.order
                )
        
        self.message_user(request, f'{queryset.count()} curricula duplicated successfully.')
    duplicate_curriculum.short_description = 'Duplicate selected curricula'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(LearningObjective)
class LearningObjectiveAdmin(admin.ModelAdmin):
    list_display = ('title', 'curriculum', 'subject', 'grade_level', 'order')
    list_filter = ('curriculum', 'subject', 'grade_level')
    search_fields = ('title', 'description')
    ordering = ('curriculum', 'order')
    actions = ['reorder_objectives']
    
    def reorder_objectives(self, request, queryset):
        # Simple reordering based on title alphabetically
        for i, objective in enumerate(queryset.order_by('title'), 1):
            objective.order = i
            objective.save()
        self.message_user(request, f'{queryset.count()} objectives reordered alphabetically.')
    reorder_objectives.short_description = 'Reorder selected objectives alphabetically'

@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'school_class', 'teacher', 'is_completed', 'completion_date', 'estimated_duration')
    list_filter = ('subject', 'school_class', 'teacher', 'is_completed', 'curriculum', 'created_at')
    search_fields = ('title', 'content')
    filter_horizontal = ('learning_objectives',)
    readonly_fields = ('created_at', 'updated_at', 'completion_date')
    actions = ['mark_completed', 'mark_incomplete', 'bulk_assign_objectives']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'curriculum', 'subject', 'school_class', 'teacher')
        }),
        ('Content', {
            'fields': ('learning_objectives', 'content', 'resources', 'estimated_duration'),
            'description': 'Use the rich text editor for detailed lesson content.'
        }),
        ('Status', {
            'fields': ('is_completed', 'completion_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def mark_completed(self, request, queryset):
        updated = queryset.update(is_completed=True)
        # Trigger coverage update for each lesson plan
        for lesson in queryset:
            lesson.save()  # This will trigger the update_coverage_tracking method
        self.message_user(request, f'{updated} lesson plans marked as completed.')
    mark_completed.short_description = 'Mark selected lesson plans as completed'
    
    def mark_incomplete(self, request, queryset):
        updated = queryset.update(is_completed=False, completion_date=None)
        # Trigger coverage update for each lesson plan
        for lesson in queryset:
            lesson.save()
        self.message_user(request, f'{updated} lesson plans marked as incomplete.')
    mark_incomplete.short_description = 'Mark selected lesson plans as incomplete'
    
    def bulk_assign_objectives(self, request, queryset):
        # This would need a custom form, for now just show a message
        self.message_user(request, 'Bulk objective assignment requires individual editing.', level='info')
    bulk_assign_objectives.short_description = 'Bulk assign learning objectives'

@admin.register(CurriculumCoverage)
class CurriculumCoverageAdmin(admin.ModelAdmin):
    list_display = ('curriculum', 'school_class', 'learning_objective', 'completion_percentage', 'completed_lessons', 'total_planned_lessons', 'status_indicator')
    list_filter = ('curriculum', 'school_class', 'learning_objective__subject')
    search_fields = ('learning_objective__title', 'curriculum__title')
    readonly_fields = ('completion_percentage', 'last_updated')
    actions = ['recalculate_coverage']
    
    def status_indicator(self, obj):
        if obj.completion_percentage >= 100:
            return format_html('<span style="color: green;">✓ Complete</span>')
        elif obj.completion_percentage >= 75:
            return format_html('<span style="color: orange;">⚠ Nearly Complete</span>')
        elif obj.completion_percentage >= 50:
            return format_html('<span style="color: blue;">◐ In Progress</span>')
        else:
            return format_html('<span style="color: red;">◯ At Risk</span>')
    status_indicator.short_description = 'Status'
    
    def recalculate_coverage(self, request, queryset):
        for coverage in queryset:
            # Recalculate based on actual lesson plans
            total_lessons = LessonPlan.objects.filter(
                curriculum=coverage.curriculum,
                school_class=coverage.school_class,
                learning_objectives=coverage.learning_objective
            ).count()
            
            completed_lessons = LessonPlan.objects.filter(
                curriculum=coverage.curriculum,
                school_class=coverage.school_class,
                learning_objectives=coverage.learning_objective,
                is_completed=True
            ).count()
            
            coverage.total_planned_lessons = max(total_lessons, 1)
            coverage.completed_lessons = completed_lessons
            coverage.completion_percentage = (completed_lessons / coverage.total_planned_lessons) * 100
            coverage.save()
        
        self.message_user(request, f'{queryset.count()} coverage records recalculated.')
    recalculate_coverage.short_description = 'Recalculate coverage percentages'

@admin.register(LessonNote)
class LessonNoteAdmin(admin.ModelAdmin):
    list_display = ('lesson_plan', 'teacher', 'date_taught', 'student_engagement', 'created_at')
    list_filter = ('date_taught', 'student_engagement', 'teacher', 'curriculum')
    search_fields = ('lesson_plan__title', 'content_covered', 'teacher__user__first_name', 'teacher__user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['export_lesson_notes']
    
    fieldsets = (
        ('Lesson Information', {
            'fields': ('lesson_plan', 'curriculum', 'teacher', 'date_taught')
        }),
        ('Content', {
            'fields': ('content_covered', 'teaching_methods', 'student_engagement')
        }),
        ('Observations', {
            'fields': ('challenges_faced', 'homework_assigned', 'next_lesson_plan')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def export_lesson_notes(self, request, queryset):
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="lesson_notes_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Lesson Plan', 'Teacher', 'Date Taught', 'Student Engagement', 'Challenges'])
        
        for note in queryset:
            writer.writerow([
                note.lesson_plan.title,
                note.teacher.user.get_full_name(),
                note.date_taught.strftime('%Y-%m-%d'),
                note.get_student_engagement_display(),
                note.challenges_faced[:100] if note.challenges_faced else ''
            ])
        
        return response
    export_lesson_notes.short_description = 'Export lesson notes to CSV'

@admin.register(AcademicEvent)
class AcademicEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_type', 'start_date', 'end_date', 'academic_year', 'is_recurring', 'terms_list')
    list_filter = ('event_type', 'academic_year', 'is_recurring', 'terms')
    search_fields = ('title', 'description')
    filter_horizontal = ('terms',)
    readonly_fields = ('created_at',)
    actions = ['duplicate_events', 'create_recurring_instances']
    
    fieldsets = (
        ('Event Details', {
            'fields': ('title', 'description', 'event_type')
        }),
        ('Scheduling', {
            'fields': ('start_date', 'end_date', 'academic_year', 'terms')
        }),
        ('Recurrence', {
            'fields': ('is_recurring', 'recurrence_pattern'),
            'description': 'Set recurrence pattern: daily, weekly, monthly, or yearly'
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def terms_list(self, obj):
        return ", ".join([term.name for term in obj.terms.all()]) or "All Terms"
    terms_list.short_description = 'Terms'
    
    def duplicate_events(self, request, queryset):
        for event in queryset:
            AcademicEvent.objects.create(
                title=f"{event.title} (Copy)",
                description=event.description,
                event_type=event.event_type,
                start_date=event.start_date,
                end_date=event.end_date,
                is_recurring=event.is_recurring,
                recurrence_pattern=event.recurrence_pattern,
                academic_year=event.academic_year,
                created_by=request.user
            )
        self.message_user(request, f'{queryset.count()} events duplicated.')
    duplicate_events.short_description = 'Duplicate selected events'
    
    def create_recurring_instances(self, request, queryset):
        # This would need more complex logic for actual recurring event creation
        self.message_user(request, 'Recurring event creation requires individual processing.', level='info')
    create_recurring_instances.short_description = 'Create recurring instances'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'academic_year', 'is_recurring')
    list_filter = ('academic_year', 'is_recurring', 'date')
    search_fields = ('name',)
    ordering = ('date',)
    actions = ['mark_recurring', 'mark_non_recurring']
    
    def mark_recurring(self, request, queryset):
        updated = queryset.update(is_recurring=True)
        self.message_user(request, f'{updated} holidays marked as recurring.')
    mark_recurring.short_description = 'Mark as recurring holidays'
    
    def mark_non_recurring(self, request, queryset):
        updated = queryset.update(is_recurring=False)
        self.message_user(request, f'{updated} holidays marked as non-recurring.')
    mark_non_recurring.short_description = 'Mark as non-recurring holidays'

@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = ('subject', 'school_class', 'exam_date', 'duration', 'room', 'invigilator', 'conflict_status')
    list_filter = ('subject', 'school_class', 'exam_date', 'invigilator')
    search_fields = ('subject__name', 'school_class__name', 'room')
    actions = ['check_conflicts', 'assign_rooms_bulk']
    
    def conflict_status(self, obj):
        # Simple conflict check display
        try:
            obj.clean()
            return format_html('<span style="color: green;">✓ No Conflicts</span>')
        except:
            return format_html('<span style="color: red;">⚠ Conflicts Detected</span>')
    conflict_status.short_description = 'Status'
    
    def check_conflicts(self, request, queryset):
        conflicts = 0
        for exam in queryset:
            try:
                exam.clean()
            except:
                conflicts += 1
        
        if conflicts:
            self.message_user(request, f'{conflicts} exams have scheduling conflicts.', level='warning')
        else:
            self.message_user(request, 'No conflicts detected in selected exams.')
    check_conflicts.short_description = 'Check for scheduling conflicts'
    
    def assign_rooms_bulk(self, request, queryset):
        self.message_user(request, 'Bulk room assignment requires individual editing.', level='info')
    assign_rooms_bulk.short_description = 'Bulk assign rooms'

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('name', 'day_of_week_display', 'start_time', 'end_time', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    ordering = ('day_of_week', 'start_time')
    actions = ['activate_slots', 'deactivate_slots']
    
    def day_of_week_display(self, obj):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[obj.day_of_week]
    day_of_week_display.short_description = 'Day'
    
    def activate_slots(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} time slots activated.')
    activate_slots.short_description = 'Activate selected time slots'
    
    def deactivate_slots(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} time slots deactivated.')
    deactivate_slots.short_description = 'Deactivate selected time slots'

@admin.register(RoomAssignment)
class RoomAssignmentAdmin(admin.ModelAdmin):
    list_display = ('room_name', 'room_type', 'capacity', 'is_available', 'utilization_status')
    list_filter = ('room_type', 'is_available')
    search_fields = ('room_name',)
    actions = ['mark_available', 'mark_unavailable']
    
    def utilization_status(self, obj):
        # Count current timetable assignments
        current_assignments = Timetable.objects.filter(room=obj, is_active=True).count()
        if current_assignments == 0:
            return format_html('<span style="color: gray;">Unused</span>')
        elif current_assignments < 10:
            return format_html('<span style="color: green;">Low Usage</span>')
        elif current_assignments < 20:
            return format_html('<span style="color: orange;">Medium Usage</span>')
        else:
            return format_html('<span style="color: red;">High Usage</span>')
    utilization_status.short_description = 'Usage'
    
    def mark_available(self, request, queryset):
        updated = queryset.update(is_available=True)
        self.message_user(request, f'{updated} rooms marked as available.')
    mark_available.short_description = 'Mark rooms as available'
    
    def mark_unavailable(self, request, queryset):
        updated = queryset.update(is_available=False)
        self.message_user(request, f'{updated} rooms marked as unavailable.')
    mark_unavailable.short_description = 'Mark rooms as unavailable'

@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('school_class', 'subject', 'teacher', 'time_slot', 'room', 'term', 'is_active', 'conflict_indicator')
    list_filter = ('term', 'academic_year', 'subject', 'school_class', 'is_active')
    search_fields = ('school_class__name', 'subject__name', 'teacher__user__first_name', 'teacher__user__last_name')
    actions = ['activate_timetables', 'deactivate_timetables', 'check_all_conflicts']
    
    def conflict_indicator(self, obj):
        try:
            obj.clean()
            return format_html('<span style="color: green;">✓</span>')
        except:
            return format_html('<span style="color: red;">⚠</span>')
    conflict_indicator.short_description = 'Status'
    
    def activate_timetables(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} timetable entries activated.')
    activate_timetables.short_description = 'Activate selected timetables'
    
    def deactivate_timetables(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} timetable entries deactivated.')
    deactivate_timetables.short_description = 'Deactivate selected timetables'
    
    def check_all_conflicts(self, request, queryset):
        conflicts = 0
        for timetable in queryset:
            try:
                timetable.clean()
            except:
                conflicts += 1
        
        if conflicts:
            self.message_user(request, f'{conflicts} timetable entries have conflicts.', level='warning')
        else:
            self.message_user(request, 'No conflicts detected in selected timetables.')
    check_all_conflicts.short_description = 'Check for conflicts'

class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0
    readonly_fields = ('uploaded_at', 'original_filename')
    fields = ('file', 'original_filename', 'uploaded_at')

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return is_feature_enabled('assignments')
    
    list_display = ('title', 'subject', 'teacher', 'due_date', 'max_score', 'allow_late_submission', 'submission_count', 'overdue_status')
    list_filter = ('subject', 'teacher', 'allow_late_submission', 'created_at', 'due_date')
    search_fields = ('title', 'description')
    filter_horizontal = ('school_classes',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ['extend_deadline', 'allow_late_submissions', 'disallow_late_submissions']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'subject', 'teacher', 'school_classes'),
            'description': 'Use the rich text editor for detailed assignment descriptions.'
        }),
        ('Submission Settings', {
            'fields': ('due_date', 'max_score', 'allow_late_submission', 'late_penalty_percentage')
        }),
        ('Attachments', {
            'fields': ('attachment',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def submission_count(self, obj):
        return obj.submissions.count()
    submission_count.short_description = 'Submissions'
    
    def overdue_status(self, obj):
        if obj.is_overdue():
            return format_html('<span style="color: red;">Overdue</span>')
        else:
            remaining = obj.time_remaining()
            if remaining and remaining.days <= 1:
                return format_html('<span style="color: orange;">Due Soon</span>')
            return format_html('<span style="color: green;">Active</span>')
    overdue_status.short_description = 'Status'
    
    def extend_deadline(self, request, queryset):
        # This would need a custom form for date selection
        self.message_user(request, 'Deadline extension requires individual editing.', level='info')
    extend_deadline.short_description = 'Extend deadline'
    
    def allow_late_submissions(self, request, queryset):
        updated = queryset.update(allow_late_submission=True)
        self.message_user(request, f'{updated} assignments now allow late submissions.')
    allow_late_submissions.short_description = 'Allow late submissions'
    
    def disallow_late_submissions(self, request, queryset):
        updated = queryset.update(allow_late_submission=False)
        self.message_user(request, f'{updated} assignments no longer allow late submissions.')
    disallow_late_submissions.short_description = 'Disallow late submissions'

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'submitted_at', 'is_late', 'score', 'grading_status', 'file_count')
    list_filter = ('is_late', 'assignment__subject', 'submitted_at', 'assignment')
    search_fields = ('assignment__title', 'student__user__first_name', 'student__user__last_name', 'student__student_id')
    readonly_fields = ('submitted_at', 'is_late')
    inlines = [SubmissionFileInline]
    actions = ['mark_graded', 'send_feedback_notification']
    
    fieldsets = (
        ('Submission Info', {
            'fields': ('assignment', 'student', 'submitted_at', 'is_late')
        }),
        ('Content', {
            'fields': ('submission_text',),
            'description': 'Student submission content with rich text formatting.'
        }),
        ('Grading', {
            'fields': ('score', 'feedback')
        })
    )
    
    def grading_status(self, obj):
        if obj.score is not None:
            return format_html('<span style="color: green;">Graded</span>')
        else:
            return format_html('<span style="color: orange;">Pending</span>')
    grading_status.short_description = 'Grading'
    
    def file_count(self, obj):
        return obj.files.count()
    file_count.short_description = 'Files'
    
    def mark_graded(self, request, queryset):
        graded = 0
        for submission in queryset:
            if submission.score is not None:
                graded += 1
        
        self.message_user(request, f'{graded} submissions are already graded. Use individual editing to assign scores.')
    mark_graded.short_description = 'Check grading status'
    
    def send_feedback_notification(self, request, queryset):
        # This would integrate with notification system
        self.message_user(request, 'Feedback notifications would be sent here.', level='info')
    send_feedback_notification.short_description = 'Send feedback notifications'

@admin.register(SubmissionFile)
class SubmissionFileAdmin(admin.ModelAdmin):
    list_display = ('submission', 'original_filename', 'uploaded_at', 'file_size_display')
    list_filter = ('uploaded_at',)
    search_fields = ('original_filename', 'submission__student__user__first_name')
    readonly_fields = ('uploaded_at', 'original_filename')
    
    def file_size_display(self, obj):
        try:
            size = obj.file.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except:
            return "Unknown"
    file_size_display.short_description = 'File Size'

# Additional Admin Classes for Missing Models

@admin.register(QuestionGroup)
class QuestionGroupAdmin(admin.ModelAdmin):
    list_display = ('subject', 'instruction_preview', 'created_by', 'created_at', 'questions_count')
    list_filter = ('subject', 'created_by', 'created_at')
    search_fields = ('instruction',)
    readonly_fields = ('created_at',)
    
    def instruction_preview(self, obj):
        return obj.instruction[:100] + "..." if len(obj.instruction) > 100 else obj.instruction
    instruction_preview.short_description = 'Instruction Preview'
    
    def questions_count(self, obj):
        return obj.questions.count()
    questions_count.short_description = 'Questions'

@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ('subject', 'school_class', 'question_type', 'topic', 'difficulty', 'created_by', 'created_at')
    list_filter = ('subject', 'school_class', 'question_type', 'difficulty', 'created_by')
    search_fields = ('question_text', 'topic')
    readonly_fields = ('created_at',)
    actions = ['mark_easy', 'mark_medium', 'mark_hard']
    
    fieldsets = (
        ('Question Details', {
            'fields': ('subject', 'school_class', 'question_type', 'topic', 'group')
        }),
        ('Question Content', {
            'fields': ('question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer'),
            'description': 'Use rich text editor for question content and options.'
        }),
        ('Metadata', {
            'fields': ('difficulty', 'created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def mark_easy(self, request, queryset):
        updated = queryset.update(difficulty='easy')
        self.message_user(request, f'{updated} questions marked as easy.')
    mark_easy.short_description = 'Mark as easy difficulty'
    
    def mark_medium(self, request, queryset):
        updated = queryset.update(difficulty='medium')
        self.message_user(request, f'{updated} questions marked as medium.')
    mark_medium.short_description = 'Mark as medium difficulty'
    
    def mark_hard(self, request, queryset):
        updated = queryset.update(difficulty='hard')
        self.message_user(request, f'{updated} questions marked as hard.')
    mark_hard.short_description = 'Mark as hard difficulty'

@admin.register(AISubscription)
class AISubscriptionAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'amount', 'reference', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'created_at', 'start_date', 'end_date')
    search_fields = ('teacher__user__first_name', 'teacher__user__last_name', 'reference')
    readonly_fields = ('created_at',)
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} subscriptions activated.')
    activate_subscriptions.short_description = 'Activate subscriptions'
    
    def deactivate_subscriptions(self, request, queryset):
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} subscriptions deactivated.')
    deactivate_subscriptions.short_description = 'Deactivate subscriptions'

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'days_present', 'days_absent', 'total_days', 'attendance_percentage')
    list_filter = ('term', 'student__school_class')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    actions = ['recalculate_totals']
    
    def attendance_percentage(self, obj):
        percentage = obj.percentage()
        if percentage >= 90:
            return format_html('<span style="color: green;">{} %</span>', f"{percentage:.1f}")
        elif percentage >= 75:
            return format_html('<span style="color: orange;">{} %</span>', f"{percentage:.1f}")
        else:
            return format_html('<span style="color: red;">{} %</span>', f"{percentage:.1f}")
    attendance_percentage.short_description = 'Attendance %'
    
    def recalculate_totals(self, request, queryset):
        for attendance in queryset:
            attendance.total_days = attendance.days_present + attendance.days_absent
            attendance.save()
        self.message_user(request, f'{queryset.count()} attendance records recalculated.')
    recalculate_totals.short_description = 'Recalculate total days'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'has_teacher_comment', 'has_proprietor_comment')
    list_filter = ('term', 'student__school_class')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'term')
        }),
        ('Comments', {
            'fields': ('teacher_comment', 'proprietor_comment'),
            'description': 'Add comments for the student report card.'
        })
    )
    
    def has_teacher_comment(self, obj):
        return bool(obj.teacher_comment)
    has_teacher_comment.boolean = True
    has_teacher_comment.short_description = 'Teacher Comment'
    
    def has_proprietor_comment(self, obj):
        return bool(obj.proprietor_comment)
    has_proprietor_comment.boolean = True
    has_proprietor_comment.short_description = 'Proprietor Comment'

@admin.register(QuestionGroupInstance)
class QuestionGroupInstanceAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'instruction_preview', 'order', 'questions_count')
    list_filter = ('quiz',)
    search_fields = ('instruction',)
    
    def instruction_preview(self, obj):
        return obj.instruction[:100] + "..." if len(obj.instruction) > 100 else obj.instruction
    instruction_preview.short_description = 'Instruction Preview'
    
    def questions_count(self, obj):
        return obj.questions.count()
    questions_count.short_description = 'Questions'

# Add SyllabusContent admin if not already registered
@admin.register(SyllabusContent)
class SyllabusContentAdmin(admin.ModelAdmin):
    list_display = ('curriculum', 'subject', 'order', 'content_preview')
    list_filter = ('curriculum', 'subject')
    search_fields = ('content',)
    
    def content_preview(self, obj):
        # Strip HTML tags for preview
        import re
        clean_content = re.sub('<.*?>', '', obj.content)
        return clean_content[:100] + "..." if len(clean_content) > 100 else clean_content
    content_preview.short_description = 'Content Preview'


# Financial Management Admin Classes

class FeePaymentInline(admin.TabularInline):
    model = FeePayment
    extra = 0
    readonly_fields = ('payment_date',)
    fields = ('amount', 'payment_method', 'reference_number', 'payment_date', 'received_by', 'notes')

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return is_feature_enabled('financial_management')
    
    list_display = ('name', 'school_class', 'term', 'total_fee', 'is_active', 'created_at')
    list_filter = ('is_active', 'term', 'school_class', 'created_at')
    search_fields = ('name', 'school_class__name')
    readonly_fields = ('total_fee', 'created_at')
    actions = ['activate_structures', 'deactivate_structures', 'clone_fee_structure']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'school_class', 'term', 'is_active')
        }),
        ('Fee Components', {
            'fields': ('tuition_fee', 'development_fee', 'exam_fee', 'library_fee', 'sports_fee', 'other_fees'),
            'description': 'Enter fee amounts for each component'
        }),
        ('Summary', {
            'fields': ('total_fee',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def activate_structures(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} fee structures activated.')
    activate_structures.short_description = 'Activate selected fee structures'
    
    def deactivate_structures(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} fee structures deactivated.')
    deactivate_structures.short_description = 'Deactivate selected fee structures'
    
    def clone_fee_structure(self, request, queryset):
        """Clone selected fee structures for different terms/classes"""
        cloned_count = 0
        for fee_structure in queryset:
            # Create a copy with modified name
            new_name = f"{fee_structure.name} (Copy)"
            try:
                new_structure = FeeStructure.objects.create(
                    name=new_name,
                    school_class=fee_structure.school_class,
                    term=fee_structure.term,
                    tuition_fee=fee_structure.tuition_fee,
                    development_fee=fee_structure.development_fee,
                    exam_fee=fee_structure.exam_fee,
                    library_fee=fee_structure.library_fee,
                    sports_fee=fee_structure.sports_fee,
                    other_fees=fee_structure.other_fees,
                    is_active=False  # Set as inactive by default
                )
                
                # Create student fees for all students in the class
                students = Student.objects.filter(school_class=new_structure.school_class)
                for student in students:
                    StudentFee.objects.get_or_create(
                        student=student,
                        fee_structure=new_structure,
                        defaults={
                            'total_amount': new_structure.total_fee,
                            'due_date': timezone.now().date() + timezone.timedelta(days=30)
                        }
                    )
                
                cloned_count += 1
            except Exception as e:
                self.message_user(request, f'Error cloning {fee_structure.name}: {str(e)}', level='error')
        
        if cloned_count:
            self.message_user(request, f'{cloned_count} fee structures cloned successfully with student fees created.')
    clone_fee_structure.short_description = 'Clone selected fee structures'

@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return is_feature_enabled('financial_management')
    
    list_display = ('student', 'fee_structure', 'total_amount', 'paid_amount', 'balance_display', 'status', 'due_date')
    list_filter = ('status', 'fee_structure__term', 'fee_structure__school_class', 'due_date', 'created_at')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    readonly_fields = ('balance_amount', 'created_at')
    inlines = [FeePaymentInline]
    actions = ['mark_as_paid', 'send_payment_reminders', 'bulk_apply_discount', 'update_payment_status', 'bulk_payment_processing']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'fee_structure')
        }),
        ('Payment Details', {
            'fields': ('total_amount', 'paid_amount', 'discount_amount', 'balance_amount', 'status')
        }),
        ('Due Date', {
            'fields': ('due_date',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def balance_display(self, obj):
        balance = obj.balance_amount
        if balance > 0:
            return format_html('<span style="color: red; font-weight: bold;">${}</span>', f"{balance:.2f}")
        else:
            return format_html('<span style="color: green; font-weight: bold;">$0.00</span>')
    balance_display.short_description = 'Balance'
    
    def mark_as_paid(self, request, queryset):
        updated = 0
        for student_fee in queryset:
            if student_fee.balance_amount <= 0:
                student_fee.status = 'paid'
                student_fee.save()
                updated += 1
        self.message_user(request, f'{updated} fees marked as paid.')
    mark_as_paid.short_description = 'Mark selected fees as paid'
    
    def send_payment_reminders(self, request, queryset):
        # Placeholder for notification system integration
        pending_fees = queryset.exclude(status='paid').count()
        self.message_user(request, f'Payment reminders would be sent for {pending_fees} pending fees.')
    send_payment_reminders.short_description = 'Send payment reminders'
    
    def bulk_apply_discount(self, request, queryset):
        # Placeholder for bulk discount application
        self.message_user(request, 'Bulk discount application requires individual editing.', level='info')
    bulk_apply_discount.short_description = 'Apply bulk discount'
    
    def update_payment_status(self, request, queryset):
        updated = 0
        for student_fee in queryset:
            student_fee.update_status()
            updated += 1
        self.message_user(request, f'{updated} payment statuses updated.')
    update_payment_status.short_description = 'Update payment status'
    
    def bulk_payment_processing(self, request, queryset):
        """Process bulk payments for selected student fees"""
        from django.db import transaction
        
        processed_count = 0
        error_count = 0
        
        with transaction.atomic():
            for student_fee in queryset:
                try:
                    if student_fee.balance_amount > 0:
                        # Create a payment record for the full balance
                        FeePayment.objects.create(
                            student_fee=student_fee,
                            amount=student_fee.balance_amount,
                            payment_method='bulk_processing',
                            reference_number=f'BULK_{timezone.now().strftime("%Y%m%d_%H%M%S")}_{student_fee.id}',
                            received_by=request.user,
                            notes='Bulk payment processing via admin'
                        )
                        processed_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    error_count += 1
                    self.message_user(request, f'Error processing payment for {student_fee.student}: {str(e)}', level='error')
        
        if processed_count:
            self.message_user(request, f'{processed_count} payments processed successfully.')
        if error_count:
            self.message_user(request, f'{error_count} payments could not be processed.', level='warning')
    bulk_payment_processing.short_description = 'Process bulk payments'

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('student_fee', 'amount', 'payment_method', 'reference_number', 'payment_date', 'received_by')
    list_filter = ('payment_method', 'payment_date', 'received_by')
    search_fields = ('student_fee__student__user__first_name', 'student_fee__student__user__last_name', 
                    'student_fee__student__student_id', 'reference_number')
    readonly_fields = ('payment_date',)
    actions = ['generate_receipts', 'verify_payments']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('student_fee', 'amount', 'payment_method', 'reference_number')
        }),
        ('Processing Details', {
            'fields': ('payment_date', 'received_by', 'notes')
        })
    )
    
    def generate_receipts(self, request, queryset):
        # Placeholder for receipt generation
        self.message_user(request, f'Receipts would be generated for {queryset.count()} payments.')
    generate_receipts.short_description = 'Generate payment receipts'
    
    def verify_payments(self, request, queryset):
        # Placeholder for payment verification
        self.message_user(request, f'{queryset.count()} payments verified.')
    verify_payments.short_description = 'Verify payments'

class ScholarshipAdminForm(forms.ModelForm):
    class Meta:
        model = Scholarship
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        school = getattr(self.instance, 'school', None)
        included_sessions = [self.instance.academic_year] if self.instance.pk else []
        self.fields['academic_year'].widget = forms.Select(
            choices=existing_session_choices(school, include=included_sessions)
        )


class ScholarshipRecipientInline(admin.TabularInline):
    model = ScholarshipRecipient
    extra = 0
    fields = ('student', 'awarded_amount', 'start_date', 'end_date', 'status')
    readonly_fields = ('created_at',)

@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    form = ScholarshipAdminForm
    list_display = ('name', 'scholarship_type', 'amount', 'percentage', 'max_recipients', 'current_recipients', 'is_active', 'academic_year')
    list_filter = ('scholarship_type', 'is_active', 'academic_year', 'created_at')
    search_fields = ('name', 'description')
    inlines = [ScholarshipRecipientInline]
    actions = ['activate_scholarships', 'deactivate_scholarships', 'award_to_eligible_students']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'scholarship_type', 'description', 'academic_year')
        }),
        ('Award Details', {
            'fields': ('amount', 'percentage', 'max_recipients'),
            'description': 'Specify either amount or percentage, not both'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def current_recipients(self, obj):
        active_count = obj.scholarshiprecipient_set.filter(status='active').count()
        return format_html('{} / {}', active_count, obj.max_recipients)
    current_recipients.short_description = 'Recipients (Active/Max)'
    
    def activate_scholarships(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} scholarships activated.')
    activate_scholarships.short_description = 'Activate scholarships'
    
    def deactivate_scholarships(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} scholarships deactivated.')
    deactivate_scholarships.short_description = 'Deactivate scholarships'
    
    def award_to_eligible_students(self, request, queryset):
        """Award scholarships to eligible students based on criteria"""
        from django.db import transaction
        
        awarded_count = 0
        error_count = 0
        
        for scholarship in queryset.filter(is_active=True):
            try:
                with transaction.atomic():
                    # Get current recipients count
                    current_recipients = scholarship.scholarshiprecipient_set.filter(status='active').count()
                    available_slots = scholarship.max_recipients - current_recipients
                    
                    if available_slots <= 0:
                        self.message_user(request, f'{scholarship.name} has no available slots.', level='warning')
                        continue
                    
                    # Find eligible students (example criteria: students without active scholarships)
                    eligible_students = Student.objects.exclude(
                        scholarshiprecipient__status='active'
                    ).order_by('student_id')[:available_slots]
                    
                    for student in eligible_students:
                        # Calculate awarded amount
                        if scholarship.percentage:
                            # Get student's total fee amount
                            student_fees = StudentFee.objects.filter(student=student, status__in=['pending', 'partial'])
                            if student_fees.exists():
                                total_fee = sum(fee.total_amount for fee in student_fees)
                                awarded_amount = (total_fee * scholarship.percentage) / 100
                            else:
                                awarded_amount = scholarship.amount or 0
                        else:
                            awarded_amount = scholarship.amount
                        
                        # Create scholarship recipient record
                        recipient = ScholarshipRecipient.objects.create(
                            scholarship=scholarship,
                            student=student,
                            awarded_amount=awarded_amount,
                            start_date=timezone.now().date(),
                            end_date=timezone.now().date() + timezone.timedelta(days=365),  # 1 year
                            status='active',
                            notes=f'Auto-awarded via bulk action on {timezone.now().date()}'
                        )
                        from .services_financial_integrity import sync_scholarship_fee_applications
                        sync_scholarship_fee_applications(recipient)
                        awarded_count += 1
                        
            except Exception as e:
                error_count += 1
                self.message_user(request, f'Error awarding {scholarship.name}: {str(e)}', level='error')
        
        if awarded_count:
            self.message_user(request, f'{awarded_count} scholarships awarded successfully.')
        if error_count:
            self.message_user(request, f'{error_count} scholarships could not be awarded.', level='warning')
    award_to_eligible_students.short_description = 'Award to eligible students'

@admin.register(ScholarshipRecipient)
class ScholarshipRecipientAdmin(admin.ModelAdmin):
    list_display = ('scholarship', 'student', 'awarded_amount', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status', 'scholarship__scholarship_type', 'start_date', 'end_date')
    search_fields = ('scholarship__name', 'student__user__first_name', 'student__user__last_name', 'student__student_id')
    readonly_fields = ('created_at',)
    actions = ['activate_recipients', 'suspend_recipients', 'complete_recipients']
    
    fieldsets = (
        ('Scholarship Information', {
            'fields': ('scholarship', 'student', 'awarded_amount')
        }),
        ('Duration', {
            'fields': ('start_date', 'end_date', 'status')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def activate_recipients(self, request, queryset):
        from .services_financial_integrity import sync_scholarship_fee_applications
        updated = 0
        for recipient in queryset:
            try:
                recipient.status = 'active'
                recipient.save(update_fields=['status'])
                sync_scholarship_fee_applications(recipient)
                updated += 1
            except ValidationError as exc:
                self.message_user(request, f'{recipient}: {exc}', level='error')
        self.message_user(request, f'{updated} scholarship recipients activated.')
    activate_recipients.short_description = 'Activate recipients'
    
    def suspend_recipients(self, request, queryset):
        from .services_financial_integrity import clear_scholarship_fee_applications
        updated = 0
        for recipient in queryset:
            clear_scholarship_fee_applications(recipient)
            recipient.status = 'suspended'
            recipient.save(update_fields=['status'])
            updated += 1
        self.message_user(request, f'{updated} scholarship recipients suspended.')
    suspend_recipients.short_description = 'Suspend recipients'
    
    def complete_recipients(self, request, queryset):
        from .services_financial_integrity import clear_scholarship_fee_applications
        updated = 0
        for recipient in queryset:
            clear_scholarship_fee_applications(recipient)
            recipient.status = 'completed'
            recipient.save(update_fields=['status'])
            updated += 1
        self.message_user(request, f'{updated} scholarship recipients marked as completed.')
    complete_recipients.short_description = 'Mark as completed'

@admin.register(PayrollStructure)
class PayrollStructureAdmin(admin.ModelAdmin):
    list_display = ('name', 'basic_salary', 'gross_salary', 'tax_rate', 'pension_rate', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('gross_salary', 'created_at')
    actions = ['activate_structures', 'deactivate_structures', 'clone_payroll_structure']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'basic_salary', 'is_active')
        }),
        ('Allowances', {
            'fields': ('house_allowance', 'transport_allowance', 'medical_allowance', 'other_allowances'),
            'description': 'Enter allowance amounts'
        }),
        ('Deductions', {
            'fields': ('tax_rate', 'pension_rate'),
            'description': 'Enter deduction rates as percentages'
        }),
        ('Summary', {
            'fields': ('gross_salary',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def activate_structures(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} payroll structures activated.')
    activate_structures.short_description = 'Activate payroll structures'
    
    def deactivate_structures(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} payroll structures deactivated.')
    deactivate_structures.short_description = 'Deactivate payroll structures'
    
    def clone_payroll_structure(self, request, queryset):
        cloned_count = 0
        for structure in queryset:
            new_name = f"{structure.name} (Copy)"
            try:
                PayrollStructure.objects.create(
                    name=new_name,
                    basic_salary=structure.basic_salary,
                    house_allowance=structure.house_allowance,
                    transport_allowance=structure.transport_allowance,
                    medical_allowance=structure.medical_allowance,
                    other_allowances=structure.other_allowances,
                    tax_rate=structure.tax_rate,
                    pension_rate=structure.pension_rate,
                    is_active=False
                )
                cloned_count += 1
            except Exception as e:
                self.message_user(request, f'Error cloning {structure.name}: {str(e)}', level='error')
        
        if cloned_count:
            self.message_user(request, f'{cloned_count} payroll structures cloned successfully.')
    clone_payroll_structure.short_description = 'Clone payroll structures'

@admin.register(StaffPayroll)
class StaffPayrollAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'month_display', 'gross_salary', 'total_deductions', 'net_salary', 'is_paid', 'payment_date')
    list_filter = ('is_paid', 'month', 'payroll_structure', 'created_at')
    search_fields = ('teacher__user__first_name', 'teacher__user__last_name', 'teacher__employee_id')
    readonly_fields = ('gross_salary', 'net_salary', 'created_at')
    actions = ['process_payroll_payments', 'generate_payroll_slips', 'recalculate_salaries', 'bulk_payroll_generation']
    
    fieldsets = (
        ('Employee Information', {
            'fields': ('teacher', 'payroll_structure', 'month')
        }),
        ('Salary Breakdown', {
            'fields': ('gross_salary', 'tax_deduction', 'pension_deduction', 'other_deductions', 'net_salary')
        }),
        ('Payment Status', {
            'fields': ('is_paid', 'payment_date')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def month_display(self, obj):
        return obj.month.strftime('%B %Y')
    month_display.short_description = 'Month'
    
    def total_deductions(self, obj):
        total = obj.tax_deduction + obj.pension_deduction + obj.other_deductions
        return format_html('${}', f"{total:.2f}")
    total_deductions.short_description = 'Total Deductions'
    
    def process_payroll_payments(self, request, queryset):
        """Mark selected payrolls as paid"""
        from django.utils import timezone
        updated = 0
        for payroll in queryset.filter(is_paid=False):
            payroll.is_paid = True
            payroll.payment_date = timezone.now()
            payroll.save()
            updated += 1
        self.message_user(request, f'{updated} payrolls processed.')
    process_payroll_payments.short_description = 'Process selected payroll payments'
    
    def generate_payroll_slips(self, request, queryset):
        # Placeholder for payroll slip generation
        self.message_user(request, f'Payroll slips would be generated for {queryset.count()} records.')
    generate_payroll_slips.short_description = 'Generate payroll slips'
    
    def recalculate_salaries(self, request, queryset):
        updated = 0
        for payroll in queryset:
            payroll.calculate_net_salary()
            updated += 1
        self.message_user(request, f'{updated} salaries recalculated.')
    recalculate_salaries.short_description = 'Recalculate net salaries'
    
    def bulk_payroll_generation(self, request, queryset):
        """Generate payroll for multiple teachers for the current month"""
        from django.db import transaction
        import calendar
        
        current_date = timezone.now().date()
        current_month = current_date.replace(day=1)
        
        generated_count = 0
        error_count = 0
        
        # Get all active payroll structures
        active_structures = PayrollStructure.objects.filter(is_active=True)
        if not active_structures.exists():
            self.message_user(request, 'No active payroll structures found.', level='error')
            return
        
        # Use the first active structure as default
        default_structure = active_structures.first()
        
        with transaction.atomic():
            # Get all teachers
            teachers = Teacher.objects.all()
            
            for teacher in teachers:
                try:
                    # Check if payroll already exists for this month
                    existing_payroll = StaffPayroll.objects.filter(
                        teacher=teacher,
                        month=current_month
                    ).first()
                    
                    if existing_payroll:
                        continue  # Skip if already exists
                    
                    # Create new payroll record
                    payroll = StaffPayroll.objects.create(
                        teacher=teacher,
                        payroll_structure=default_structure,
                        month=current_month,
                        gross_salary=default_structure.gross_salary,
                        net_salary=0  # Will be calculated
                    )
                    
                    # Calculate net salary
                    payroll.calculate_net_salary()
                    generated_count += 1
                    
                except Exception as e:
                    error_count += 1
                    self.message_user(request, f'Error generating payroll for {teacher}: {str(e)}', level='error')
        
        if generated_count:
            self.message_user(request, f'{generated_count} payroll records generated for {current_month.strftime("%B %Y")}.')
        if error_count:
            self.message_user(request, f'{error_count} payroll records could not be generated.', level='warning')
    bulk_payroll_generation.short_description = 'Generate bulk payroll for current month'

@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'category', 'amount', 'description', 'transaction_date', 'created_by', 'created_at')
    list_filter = ('transaction_type', 'category', 'transaction_date', 'created_by', 'created_at')
    search_fields = ('description', 'reference_number')
    readonly_fields = ('created_at',)
    actions = ['mark_as_income', 'mark_as_expense', 'bulk_categorize']
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('transaction_type', 'category', 'amount', 'description')
        }),
        ('Reference Information', {
            'fields': ('reference_number', 'transaction_date')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def mark_as_income(self, request, queryset):
        updated = queryset.update(transaction_type='income')
        self.message_user(request, f'{updated} transactions marked as income.')
    mark_as_income.short_description = 'Mark as income'
    
    def mark_as_expense(self, request, queryset):
        updated = queryset.update(transaction_type='expense')
        self.message_user(request, f'{updated} transactions marked as expense.')
    mark_as_expense.short_description = 'Mark as expense'
    
    def bulk_categorize(self, request, queryset):
        # Placeholder for bulk categorization
        self.message_user(request, 'Bulk categorization requires individual editing.', level='info')
    bulk_categorize.short_description = 'Bulk categorize transactions'


# Financial Audit Logging Admin

@admin.register(FinancialAuditLog)
class FinancialAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'operation', 'model_name', 'object_id', 'user', 'ip_address', 'changes_summary')
    list_filter = ('operation', 'model_name', 'timestamp', 'user')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'ip_address', 'changes')
    readonly_fields = ('operation', 'model_name', 'object_id', 'user', 'timestamp', 'changes', 'ip_address', 'user_agent')
    ordering = ['-timestamp']
    actions = ['export_audit_logs']
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('timestamp', 'operation', 'model_name', 'object_id', 'user')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Changes', {
            'fields': ('changes',),
            'description': 'JSON representation of the changes made'
        })
    )
    
    def has_add_permission(self, request):
        """Audit logs should not be manually created"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs should be immutable"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Audit logs should not be deleted"""
        return False
    
    def changes_summary(self, obj):
        """Display a summary of changes"""
        if not obj.changes:
            return "No changes"
        
        if obj.operation == 'create':
            return "Record created"
        elif obj.operation == 'delete':
            return "Record deleted"
        elif obj.operation == 'update':
            changed_fields = obj.changes.get('changed_fields', [])
            if changed_fields:
                return f"Updated: {', '.join(changed_fields[:3])}{'...' if len(changed_fields) > 3 else ''}"
            return "Updated"
        elif obj.operation == 'payment':
            amount = obj.changes.get('amount', 'Unknown')
            method = obj.changes.get('payment_method', 'Unknown')
            return f"Payment: ${amount} via {method}"
        elif obj.operation == 'bulk_operation':
            operation_type = obj.changes.get('operation_type', 'Unknown')
            affected_count = obj.changes.get('affected_count', 0)
            return f"Bulk {operation_type}: {affected_count} records"
        
        return "Changes recorded"
    changes_summary.short_description = 'Summary'
    
    def export_audit_logs(self, request, queryset):
        """Export selected audit logs to CSV"""
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Timestamp', 'Operation', 'Model', 'Object ID', 'User', 'IP Address', 'Summary'])
        
        for log in queryset:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.get_operation_display(),
                log.get_model_name_display(),
                log.object_id,
                str(log.user) if log.user else 'System',
                log.ip_address or 'Unknown',
                self.changes_summary(log)
            ])
        
        return response
    export_audit_logs.short_description = 'Export selected audit logs to CSV'


# Notification System Admin Classes

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_active', 'created_at', 'updated_at')
    list_filter = ('template_type', 'is_active', 'created_at')
    search_fields = ('name', 'subject_template')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['activate_templates', 'deactivate_templates', 'duplicate_templates']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_type', 'is_active')
        }),
        ('Email Content', {
            'fields': ('subject_template', 'html_template', 'text_template'),
            'description': 'Use Django template syntax for dynamic content. Available variables depend on notification type.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def activate_templates(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} templates activated.')
    activate_templates.short_description = 'Activate selected templates'
    
    def deactivate_templates(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} templates deactivated.')
    deactivate_templates.short_description = 'Deactivate selected templates'
    
    def duplicate_templates(self, request, queryset):
        for template in queryset:
            NotificationTemplate.objects.create(
                name=f"{template.name} (Copy)",
                template_type=template.template_type,
                subject_template=template.subject_template,
                html_template=template.html_template,
                text_template=template.text_template,
                is_active=False  # Start as inactive
            )
        self.message_user(request, f'{queryset.count()} templates duplicated.')
    duplicate_templates.short_description = 'Duplicate selected templates'


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('notification_type', 'recipient_email', 'recipient_name', 'status', 'sent_at', 'retry_count', 'created_at')
    list_filter = ('status', 'notification_type', 'created_at', 'sent_at')
    search_fields = ('recipient_email', 'recipient_name', 'subject')
    readonly_fields = ('notification_type', 'recipient_email', 'recipient_name', 'subject', 'sent_at', 'created_at', 'context_data')
    actions = ['retry_failed_notifications', 'mark_as_sent', 'export_notification_logs']
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('notification_type', 'recipient_email', 'recipient_name', 'subject')
        }),
        ('Status', {
            'fields': ('status', 'sent_at', 'error_message')
        }),
        ('Retry Settings', {
            'fields': ('retry_count', 'max_retries')
        }),
        ('Context Data', {
            'fields': ('context_data',),
            'classes': ('collapse',),
            'description': 'JSON data used to render the notification template'
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Notification logs are created automatically"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Only allow changing retry settings and status"""
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion of old logs for cleanup"""
        return True
    
    def retry_failed_notifications(self, request, queryset):
        """Retry failed notifications that can be retried"""
        from .services_notification import NotificationService
        
        retryable = queryset.filter(status__in=['failed', 'retry']).filter(
            retry_count__lt=models.F('max_retries')
        )
        
        if not retryable.exists():
            self.message_user(request, 'No notifications can be retried.', level='warning')
            return
        
        service = NotificationService()
        results = {'succeeded': 0, 'failed': 0}
        
        for notification in retryable:
            if service._retry_notification(notification):
                results['succeeded'] += 1
            else:
                results['failed'] += 1
        
        self.message_user(
            request, 
            f"Retry completed: {results['succeeded']} succeeded, {results['failed']} failed."
        )
    retry_failed_notifications.short_description = 'Retry failed notifications'
    
    def mark_as_sent(self, request, queryset):
        """Mark notifications as sent (use with caution)"""
        from django.utils import timezone
        updated = queryset.filter(status__in=['pending', 'failed', 'retry']).update(
            status='sent',
            sent_at=timezone.now()
        )
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = 'Mark as sent (use with caution)'
    
    def export_notification_logs(self, request, queryset):
        """Export selected notification logs to CSV"""
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="notification_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Notification Type', 'Recipient Email', 'Recipient Name', 'Subject', 
            'Status', 'Sent At', 'Retry Count', 'Error Message', 'Created At'
        ])
        
        for log in queryset:
            writer.writerow([
                log.notification_type,
                log.recipient_email,
                log.recipient_name,
                log.subject,
                log.get_status_display(),
                log.sent_at.strftime('%Y-%m-%d %H:%M:%S') if log.sent_at else '',
                log.retry_count,
                log.error_message,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_notification_logs.short_description = 'Export selected logs to CSV'
