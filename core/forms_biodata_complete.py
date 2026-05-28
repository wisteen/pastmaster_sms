from django import forms
from .models_biodata import (
    StudentBioData, Guardian, StaffBioData, 
    StaffQualification, StaffGuarantor, StaffBankAccount
)

class StudentBioDataForm(forms.ModelForm):
    class Meta:
        model = StudentBioData
        exclude = ['student', 'created_at', 'updated_at']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'home_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'previous_school_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'reason_for_leaving': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'medications': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'hospital_address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'hobbies': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'special_talents': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

class GuardianForm(forms.ModelForm):
    class Meta:
        model = Guardian
        exclude = ['student', 'created_at', 'updated_at']
        widgets = {
            'home_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'office_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class StaffBioDataForm(forms.ModelForm):
    class Meta:
        model = StaffBioData
        exclude = ['teacher', 'created_at', 'updated_at']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_employment': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'home_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'emergency_contact_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

class StaffQualificationForm(forms.ModelForm):
    class Meta:
        model = StaffQualification
        exclude = ['staff_bio_data', 'created_at']
        widgets = {
            'year_obtained': forms.NumberInput(attrs={'class': 'form-control', 'min': '1950', 'max': '2030'}),
        }

class StaffGuarantorForm(forms.ModelForm):
    class Meta:
        model = StaffGuarantor
        exclude = ['staff_bio_data', 'created_at', 'updated_at']
        widgets = {
            'home_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'office_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class StaffBankAccountForm(forms.ModelForm):
    class Meta:
        model = StaffBankAccount
        exclude = ['staff_bio_data', 'created_at', 'updated_at']
        widgets = {
            'account_number': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
        }
