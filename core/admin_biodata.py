from django.contrib import admin
from .models_biodata import StudentBioData, Guardian, StaffBioData, StaffQualification, StaffGuarantor, StaffBankAccount

class StudentBioDataInline(admin.StackedInline):
    model = StudentBioData
    can_delete = False
    verbose_name_plural = 'Bio Data'
    fields = ('date_of_birth', 'place_of_birth', 'nationality', 'state_of_origin', 'lga', 'religion', 
              'home_address', 'phone_number', 'email', 'blood_group', 'genotype', 'nin')

class GuardianInline(admin.TabularInline):
    model = Guardian
    extra = 0
    fields = ('user', 'relationship', 'title', 'first_name', 'last_name', 'phone_number', 'is_primary_contact', 'is_emergency_contact')

@admin.register(StudentBioData)
class StudentBioDataAdmin(admin.ModelAdmin):
    list_display = ('student', 'date_of_birth', 'nationality', 'phone_number', 'blood_group')
    search_fields = ('student__user__first_name', 'student__user__last_name', 'student__student_id')
    list_filter = ('nationality', 'blood_group', 'genotype')

@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'student', 'user', 'relationship', 'phone_number', 'is_primary_contact')
    search_fields = ('first_name', 'last_name', 'student__user__first_name', 'user__username', 'user__email')
    list_filter = ('relationship', 'is_primary_contact', 'is_emergency_contact')

class StaffBioDataInline(admin.StackedInline):
    model = StaffBioData
    can_delete = False
    verbose_name_plural = 'Bio Data'
    fields = ('date_of_birth', 'place_of_birth', 'marital_status', 'phone_number', 'email', 
              'date_of_employment', 'employment_type', 'department', 'position')

@admin.register(StaffBioData)
class StaffBioDataAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'date_of_birth', 'employment_type', 'department', 'position')
    search_fields = ('teacher__user__first_name', 'teacher__user__last_name', 'teacher__employee_id')
    list_filter = ('employment_type', 'department', 'marital_status')

@admin.register(StaffQualification)
class StaffQualificationAdmin(admin.ModelAdmin):
    list_display = ('staff_bio_data', 'qualification_type', 'institution', 'year_obtained')
    list_filter = ('qualification_type', 'year_obtained')
    search_fields = ('staff_bio_data__teacher__user__first_name', 'institution')

@admin.register(StaffGuarantor)
class StaffGuarantorAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'staff_bio_data', 'occupation', 'phone_number')
    search_fields = ('first_name', 'last_name', 'staff_bio_data__teacher__user__first_name')

@admin.register(StaffBankAccount)
class StaffBankAccountAdmin(admin.ModelAdmin):
    list_display = ('staff_bio_data', 'bank_name', 'account_number', 'account_type')
    search_fields = ('staff_bio_data__teacher__user__first_name', 'bank_name', 'account_number')
    list_filter = ('bank_name', 'account_type')
