from django import forms
from .models_biodata import (
    StudentBioData, Guardian, StaffBioData, StaffQualification,
    StaffGuarantor, StaffBankAccount, PaymentSchedule
)

class StudentBioDataForm(forms.ModelForm):
    FIELD_CLASS = (
        'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm '
        'text-slate-900 shadow-sm transition focus:border-blue-500 focus:outline-none '
        'focus:ring-4 focus:ring-blue-100'
    )
    TEXTAREA_CLASS = (
        'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm '
        'text-slate-900 shadow-sm transition focus:border-blue-500 focus:outline-none '
        'focus:ring-4 focus:ring-blue-100 resize-y'
    )
    FILE_CLASS = (
        'block w-full rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2.5 '
        'text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 '
        'file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-blue-700'
    )

    class Meta:
        model = StudentBioData
        exclude = ['student', 'created_at', 'updated_at']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'home_address': forms.Textarea(attrs={'rows': 3}),
            'previous_school_address': forms.Textarea(attrs={'rows': 2}),
            'reason_for_leaving': forms.Textarea(attrs={'rows': 2}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2}),
            'medications': forms.Textarea(attrs={'rows': 2}),
            'hospital_address': forms.Textarea(attrs={'rows': 2}),
            'hobbies': forms.Textarea(attrs={'rows': 2}),
            'special_talents': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'place_of_birth': 'City or town of birth',
            'nationality': 'e.g. Nigerian',
            'state_of_origin': 'State of origin',
            'lga': 'Local government area',
            'religion': 'Religion',
            'home_address': 'Current residential address',
            'phone_number': 'Parent or student phone number',
            'email': 'Optional email address',
            'previous_school_name': 'Previous school name',
            'previous_school_address': 'Previous school address',
            'previous_class': 'Last class attended',
            'reason_for_leaving': 'Reason for transfer or leaving',
            'allergies': 'List known allergies, if any',
            'medical_conditions': 'List known medical conditions, if any',
            'medications': 'Current medications, if any',
            'doctor_name': 'Doctor name',
            'doctor_phone': 'Doctor phone number',
            'hospital_name': 'Preferred hospital',
            'hospital_address': 'Hospital address',
            'birth_certificate_number': 'Birth certificate number',
            'nin': '11-digit NIN',
            'hobbies': 'Student hobbies',
            'special_talents': 'Skills, interests, or talents',
        }
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.FileInput):
                css_class = self.FILE_CLASS
            elif isinstance(widget, forms.Textarea):
                css_class = self.TEXTAREA_CLASS
            else:
                css_class = self.FIELD_CLASS
            widget.attrs['class'] = css_class
            if name in placeholders:
                widget.attrs.setdefault('placeholder', placeholders[name])


class GuardianForm(forms.ModelForm):
    class Meta:
        model = Guardian
        exclude = ['student', 'created_at', 'updated_at']
        widgets = {
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'employer': forms.TextInput(attrs={'class': 'form-control'}),
            'office_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'home_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_primary_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_emergency_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StaffBioDataForm(forms.ModelForm):
    class Meta:
        model = StaffBioData
        exclude = ['teacher', 'created_at', 'updated_at']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'state_of_origin': forms.TextInput(attrs={'class': 'form-control'}),
            'lga': forms.TextInput(attrs={'class': 'form-control'}),
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'marital_status': forms.Select(attrs={'class': 'form-control'}),
            'home_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'genotype': forms.Select(attrs={'class': 'form-control'}),
            'allergies': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'medical_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'nin': forms.TextInput(attrs={'class': 'form-control'}),
            'bvn': forms.TextInput(attrs={'class': 'form-control'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-control'}),
            'drivers_license': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'date_of_employment': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'previous_employer': forms.TextInput(attrs={'class': 'form-control'}),
            'previous_position': forms.TextInput(attrs={'class': 'form-control'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class StaffQualificationForm(forms.ModelForm):
    class Meta:
        model = StaffQualification
        exclude = ['staff_bio_data', 'created_at']
        widgets = {
            'qualification_type': forms.Select(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'institution': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'course_of_study': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'grade': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'year_obtained': forms.NumberInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'certificate': forms.FileInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
        }


class StaffGuarantorForm(forms.ModelForm):
    class Meta:
        model = StaffGuarantor
        exclude = ['staff_bio_data', 'created_at', 'updated_at']
        widgets = {
            'title': forms.Select(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'first_name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'last_name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'phone_number': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'email': forms.EmailInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'occupation': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'employer': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'office_address': forms.Textarea(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'rows': 2}),
            'home_address': forms.Textarea(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500', 'rows': 2}),
            'relationship': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
        }


class StaffBankAccountForm(forms.ModelForm):
    class Meta:
        model = StaffBankAccount
        exclude = ['staff_bio_data', 'created_at', 'updated_at']
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'account_number': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'account_name': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'account_type': forms.Select(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
            'branch': forms.TextInput(attrs={'class': 'block w-full px-3 py-2 text-sm sm:text-base border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'}),
        }


class PaymentScheduleGeneratorForm(forms.Form):
    month = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'month', 'class': 'form-control'}),
        label='Payment Month'
    )
    include_all_staff = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include All Staff'
    )
