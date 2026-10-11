from django import forms
from django.contrib.auth import get_user_model

from .models import SchoolClass, SchoolMembership, SchoolMessage


User = get_user_model()
INPUT_CLASSES = 'w-full border rounded px-3 py-2'


def school_message_recipients(school, sender, audience, selected_users=None, school_class=None):
    selected_users = selected_users or User.objects.none()
    memberships = SchoolMembership.objects.filter(
        school=school,
        is_active=True,
        portal_access_enabled=True,
    ).select_related('user')

    role_sets = {
        'admins': {'super_admin'},
        'teachers': {'subject_teacher', 'class_teacher'},
        'parents': {'parent'},
        'students': {'student'},
    }

    if audience == 'selected':
        users = selected_users
    elif audience == 'class' and school_class:
        users = User.objects.filter(student__school=school, student__school_class=school_class, student__status='active')
    elif audience == 'everyone':
        users = User.objects.filter(
            school_memberships__school=school,
            school_memberships__is_active=True,
            school_memberships__portal_access_enabled=True,
        )
    else:
        roles = role_sets.get(audience, set())
        user_ids = [
            membership.user_id
            for membership in memberships
            if roles.intersection(membership.get_all_roles())
        ]
        users = User.objects.filter(pk__in=user_ids)

    return users.exclude(pk=sender.pk).distinct().order_by('first_name', 'last_name', 'username')


class SchoolMessageComposeForm(forms.ModelForm):
    recipient_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.none(),
        required=False,
        label='Class',
    )
    recipient_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label='Select Users',
        widget=forms.SelectMultiple(attrs={'size': 8}),
    )

    class Meta:
        model = SchoolMessage
        fields = ['audience', 'recipient_class', 'recipient_users', 'subject', 'body']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        self.sender = kwargs.pop('sender', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {INPUT_CLASSES}'.strip()
        if self.school and self.sender:
            self.fields['recipient_class'].queryset = SchoolClass.all_objects.filter(
                school=self.school,
            ).order_by('name', 'stream')
            self.fields['recipient_users'].queryset = User.objects.filter(
                school_memberships__school=self.school,
                school_memberships__is_active=True,
                school_memberships__portal_access_enabled=True,
            ).exclude(pk=self.sender.pk).select_related('student__school_class', 'teacher').distinct().order_by('first_name', 'last_name', 'username')
            self._set_recipient_labels()

    def user_label(self, user):
        name = user.get_full_name() or user.username
        student = getattr(user, 'student', None)
        if student and student.school_id == getattr(self.school, 'id', None):
            return f'{name} | @{user.username} | {student.school_class} | {student.student_id}'
        teacher = getattr(user, 'teacher', None)
        identifier = getattr(teacher, 'employee_id', '')
        return f'{name} | @{user.username}' + (f' | {identifier}' if identifier else '')

    def _set_recipient_labels(self):
        self.fields['recipient_users'].label_from_instance = self.user_label

    def full_clean(self):
        self._set_recipient_labels()
        return super().full_clean()

    def clean(self):
        cleaned_data = super().clean()
        audience = cleaned_data.get('audience')
        selected_users = cleaned_data.get('recipient_users')
        if audience == 'selected' and not selected_users:
            self.add_error('recipient_users', 'Select at least one user or choose an audience group.')
        if audience == 'class' and not cleaned_data.get('recipient_class'):
            self.add_error('recipient_class', 'Select the class that should receive this message.')
        return cleaned_data

    def resolved_recipients(self):
        return school_message_recipients(
            self.school,
            self.sender,
            self.cleaned_data['audience'],
            self.cleaned_data.get('recipient_users'),
            self.cleaned_data.get('recipient_class'),
        )
