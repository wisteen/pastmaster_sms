from pathlib import Path

from django import forms
from django.db.models import Q
from django.utils import timezone

from .forms_biodata import (
    GuardianForm,
    StaffBankAccountForm,
    StaffBioDataForm,
    StaffQualificationForm,
    StudentBioDataForm,
)
from .models import SchoolClass, Subject
from .models_onboarding import OnboardingRecord


CONTROL_CLASS = 'onboarding-control'
CHECK_CLASS = 'onboarding-check'


def style_form_fields(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
            widget.attrs['class'] = CHECK_CLASS
        else:
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {CONTROL_CLASS}".strip()


class BasicOnboardingForm(forms.Form):
    person_type = forms.ChoiceField(
        choices=OnboardingRecord.PERSON_TYPE_CHOICES,
        initial=OnboardingRecord.PERSON_STUDENT,
        label='Add a',
    )
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=30, required=False)
    school_class = forms.ModelChoiceField(queryset=SchoolClass.all_objects.none(), required=False, label='Student class')
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    gender = forms.ChoiceField(choices=[('', 'Choose gender'), ('M', 'Male'), ('F', 'Female')], required=False)
    guardian_name = forms.CharField(max_length=200, required=False)
    guardian_email = forms.EmailField(required=False)
    guardian_phone = forms.CharField(max_length=30, required=False)
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.all_objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 5}),
    )
    classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.all_objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 5}),
        label='Teaching classes',
    )
    send_invitation = forms.BooleanField(required=False, initial=True, label='Send the self-service invitation now')

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if self.school:
            classes = SchoolClass.all_objects.filter(school=self.school).order_by('name', 'stream')
            self.fields['school_class'].queryset = classes
            self.fields['classes'].queryset = classes
            self.fields['subjects'].queryset = Subject.all_objects.filter(school=self.school).order_by('name')
        style_form_fields(self)

    def clean(self):
        cleaned = super().clean()
        person_type = cleaned.get('person_type')
        if person_type == OnboardingRecord.PERSON_STUDENT:
            for field_name in ['school_class', 'date_of_birth', 'gender']:
                if not cleaned.get(field_name):
                    self.add_error(field_name, 'This field is required for a student.')
            if not (cleaned.get('guardian_email') or cleaned.get('guardian_phone')):
                self.add_error('guardian_email', 'Add a guardian email or phone number so the invitation can be delivered.')
        elif person_type == OnboardingRecord.PERSON_TEACHER:
            if not (cleaned.get('email') or cleaned.get('phone')):
                self.add_error('email', 'Add an email or phone number so the invitation can be delivered.')
        return cleaned


class BulkOnboardingUploadForm(forms.Form):
    person_type = forms.ChoiceField(choices=OnboardingRecord.PERSON_TYPE_CHOICES)
    spreadsheet = forms.FileField(
        help_text='Upload a CSV or XLSX file with no more than 500 records.',
        widget=forms.FileInput(attrs={'accept': '.csv,.xlsx'}),
    )
    send_invitations = forms.BooleanField(required=False, label='Send invitations after importing valid records')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form_fields(self)

    def clean_spreadsheet(self):
        upload = self.cleaned_data['spreadsheet']
        extension = Path(upload.name).suffix.lower()
        if extension not in {'.csv', '.xlsx'}:
            raise forms.ValidationError('Upload a CSV or XLSX spreadsheet.')
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError('The spreadsheet must be 5 MB or smaller.')
        return upload


class InvitationDeliveryForm(forms.Form):
    channels = forms.MultipleChoiceField(
        choices=[('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')],
        initial=['email'],
        widget=forms.CheckboxSelectMultiple(),
    )


class ReviewOnboardingForm(forms.Form):
    ACTION_APPROVE = 'approve'
    ACTION_CHANGES = 'request_changes'
    action = forms.ChoiceField(choices=[
        (ACTION_APPROVE, 'Approve'),
        (ACTION_CHANGES, 'Request changes'),
    ])
    review_note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    channels = forms.MultipleChoiceField(
        required=False,
        choices=[('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')],
        initial=['email'],
        widget=forms.CheckboxSelectMultiple(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form_fields(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == self.ACTION_CHANGES and not (cleaned.get('review_note') or '').strip():
            self.add_error('review_note', 'Explain what should be corrected before resubmission.')
        return cleaned


class TeacherSignatureForm(forms.Form):
    signature = forms.ImageField(required=True, help_text='Upload a clear PNG or JPG signature image.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form_fields(self)


def teacher_self_service_forms(data=None, files=None, teacher=None):
    bio_data = getattr(teacher, 'bio_data', None) if teacher else None
    qualification = bio_data.qualifications.first() if bio_data else None
    bank_account = getattr(bio_data, 'bank_account', None) if bio_data else None
    defaults = {}
    if teacher:
        defaults = {
            'email': teacher.user.email,
            'phone_number': teacher.user.phone,
            'date_of_employment': timezone.localdate(),
            'employment_type': 'full_time',
            'nationality': 'Nigerian',
            'years_of_experience': 0,
        }
    forms_bundle = {
        'bio': StaffBioDataForm(data, files, instance=bio_data, prefix='staff', initial=defaults),
        'qualification': StaffQualificationForm(data, files, instance=qualification, prefix='qualification'),
        'bank': StaffBankAccountForm(data, instance=bank_account, prefix='bank'),
        'signature': TeacherSignatureForm(data, files, prefix='teacher'),
    }
    for form in forms_bundle.values():
        style_form_fields(form)
    if teacher and teacher.signature:
        forms_bundle['signature'].fields['signature'].required = False
    return forms_bundle


def parent_self_service_forms(data=None, files=None, student=None, record=None):
    bio_data = getattr(student, 'bio_data', None) if student else None
    guardian = student.guardians.filter(is_primary_contact=True).first() if student else None
    if not guardian and student:
        guardian = student.guardians.first()
    guardian_name = (record.recipient_name if record else '') or ''
    guardian_parts = guardian_name.split(' ', 1)
    bio_initial = {}
    guardian_initial = {}
    if student:
        bio_initial = {
            'date_of_birth': student.date_of_birth,
            'home_address': student.address,
            'phone_number': (record.recipient_phone if record else '') or student.user.phone,
            'email': (record.recipient_email if record else '') or student.user.email,
            'nationality': 'Nigerian',
        }
        guardian_initial = {
            'first_name': guardian_parts[0] if guardian_parts else '',
            'last_name': guardian_parts[1] if len(guardian_parts) > 1 else '',
            'phone_number': record.recipient_phone if record else '',
            'email': record.recipient_email if record else '',
            'is_primary_contact': True,
            'is_emergency_contact': True,
        }
    forms_bundle = {
        'bio': StudentBioDataForm(data, files, instance=bio_data, prefix='student', initial=bio_initial),
        'guardian': GuardianForm(data, files, instance=guardian, prefix='guardian', initial=guardian_initial),
    }
    forms_bundle['guardian'].fields.pop('user', None)
    for form in forms_bundle.values():
        style_form_fields(form)
    return forms_bundle
