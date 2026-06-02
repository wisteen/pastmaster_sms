from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import (
    ClassTeacher,
    ExamSchedule,
    GradingSystem,
    HeadTeacher,
    ResultComponent,
    SchoolMembership,
    SchoolClass,
    SchoolSettings,
    Student,
    Subject,
    Teacher,
    Term,
    StaffPayroll,
)
from .models_biodata import Guardian
from .academic_choices import existing_session_choices, normalize_session, setup_session_choices


User = get_user_model()
INPUT_CLASSES = 'w-full border rounded px-3 py-2'


def _style_fields(form):
    for field in form.fields.values():
        if isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            continue
        existing = field.widget.attrs.get('class', '')
        field.widget.attrs['class'] = f'{existing} {INPUT_CLASSES}'.strip()


class SchoolUserForm(forms.Form):
    user_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=15, required=False)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
    extra_roles = forms.MultipleChoiceField(
        choices=User.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )
    password = forms.CharField(
        max_length=128,
        required=False,
        widget=forms.PasswordInput(render_value=True),
    )
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class SchoolStudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['user', 'student_id', 'school_class', 'date_of_birth', 'gender', 'address', 'passport_photo']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if school:
            users = User.objects.filter(
                school_memberships__school=school,
                school_memberships__is_active=True,
                school_memberships__primary_role='student',
                is_superuser=False,
            )
            if self.instance.pk:
                users = users.filter(Q(student__isnull=True) | Q(pk=self.instance.user_id))
            else:
                users = users.filter(student__isnull=True)

            self.fields['user'].queryset = users.distinct().order_by('first_name', 'last_name', 'username')
            self.fields['school_class'].queryset = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')


class SchoolTeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['user', 'employee_id', 'subjects', 'classes', 'signature']
        widgets = {
            'subjects': forms.CheckboxSelectMultiple(),
            'classes': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if school:
            users = User.objects.filter(
                school_memberships__school=school,
                school_memberships__is_active=True,
                school_memberships__primary_role__in=['subject_teacher', 'class_teacher'],
                is_superuser=False,
            )
            if self.instance.pk:
                users = users.filter(Q(teacher__isnull=True) | Q(pk=self.instance.user_id))
            else:
                users = users.filter(teacher__isnull=True)

            self.fields['user'].queryset = users.distinct().order_by('first_name', 'last_name', 'username')
            self.fields['subjects'].queryset = Subject.all_objects.filter(school=school).order_by('name')
            self.fields['classes'].queryset = SchoolClass.all_objects.filter(school=school).order_by('name', 'stream')


class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ['name', 'stream']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class SchoolSubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'subject_type', 'pass_mark']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class SchoolTermForm(forms.ModelForm):
    name = forms.ChoiceField(choices=Term.TERM_NAME_CHOICES)
    session = forms.ChoiceField(choices=())

    class Meta:
        model = Term
        fields = [
            'name', 'session', 'start_date', 'end_date', 'vacation_date',
            'resumption_date', 'school_opened_days', 'is_active', 'result_published',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'vacation_date': forms.DateInput(attrs={'type': 'date'}),
            'resumption_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        self.fields['session'].choices = setup_session_choices(school)
        _style_fields(self)

    def clean_session(self):
        return normalize_session(self.cleaned_data['session'])


class SchoolSettingsForm(forms.ModelForm):
    class Meta:
        model = SchoolSettings
        fields = [
            'school_name', 'school_address', 'school_logo', 'school_seal',
            'principal_signature', 'principal_name', 'proprietor_name',
            'school_motto', 'primary_color', 'secondary_color', 'accent_color',
            'student_id_prefix', 'student_id_digits', 'teacher_id_prefix',
            'teacher_id_digits',
        ]
        widgets = {
            'school_address': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ['primary_color', 'secondary_color', 'accent_color']:
            value = (cleaned_data.get(field_name) or '').strip()
            if len(value) != 7 or not value.startswith('#') or any(
                character not in '0123456789abcdefABCDEF' for character in value[1:]
            ):
                self.add_error(field_name, 'Enter a valid hex color such as #2563eb.')
        return cleaned_data


class SchoolCommunicationForm(forms.Form):
    MESSAGE_TYPES = [
        ('result', 'Publish and email learner result'),
        ('fee_statement', 'Email school fee statement and outstanding balance'),
        ('payslip', 'Email teacher payslip'),
        ('announcement', 'Send general information'),
    ]
    AUDIENCES = [
        ('parents', 'Parents'),
        ('students', 'Students'),
        ('teachers', 'Teachers'),
        ('everyone', 'Parents, students, and teachers'),
    ]

    message_type = forms.ChoiceField(choices=MESSAGE_TYPES)
    send_to_all_students = forms.BooleanField(required=False, label='Send to every learner')
    student = forms.ModelChoiceField(queryset=Student.objects.none(), required=False)
    term = forms.ModelChoiceField(queryset=Term.objects.none(), required=False)
    payroll = forms.ModelChoiceField(queryset=StaffPayroll.objects.none(), required=False)
    audience = forms.ChoiceField(choices=AUDIENCES, required=False)
    subject = forms.CharField(max_length=200, required=False)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), required=False)

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)
        if school:
            self.fields['student'].queryset = Student.all_objects.filter(
                school=school
            ).select_related('user').order_by('school_class__name', 'user__first_name', 'user__last_name')
            self.fields['term'].queryset = Term.all_objects.filter(school=school).order_by('-start_date')
            self.fields['payroll'].queryset = StaffPayroll.objects.filter(
                teacher__school=school
            ).select_related('teacher__user').order_by('-month', 'teacher__user__first_name')

    def clean(self):
        cleaned_data = super().clean()
        message_type = cleaned_data.get('message_type')
        required_fields = {
            'result': ['term'],
            'fee_statement': [],
            'payslip': ['payroll'],
            'announcement': ['audience', 'subject', 'message'],
        }
        for field_name in required_fields.get(message_type, []):
            if not cleaned_data.get(field_name):
                self.add_error(field_name, 'This field is required for the selected communication type.')
        if message_type in ['result', 'fee_statement'] and not (
            cleaned_data.get('send_to_all_students') or cleaned_data.get('student')
        ):
            self.add_error('student', 'Select one learner or choose to send to every learner.')
        return cleaned_data


class SchoolResultComponentForm(forms.ModelForm):
    class Meta:
        model = ResultComponent
        fields = ['school_class', 'subject', 'component_name', 'weight', 'max_score']

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if self.school:
            self.fields['school_class'].queryset = SchoolClass.all_objects.filter(
                school=self.school
            ).order_by('name', 'stream')
            self.fields['subject'].queryset = Subject.all_objects.filter(
                school=self.school
            ).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        school_class = cleaned_data.get('school_class')
        subject = cleaned_data.get('subject')
        weight = cleaned_data.get('weight') or 0
        max_score = cleaned_data.get('max_score') or 0

        if weight <= 0:
            self.add_error('weight', 'Weight must be greater than zero.')
        if max_score <= 0:
            self.add_error('max_score', 'Max score must be greater than zero.')

        if self.school and school_class and school_class.school_id != self.school.id:
            self.add_error('school_class', 'This class is not managed under this school.')
        if self.school and subject and subject.school_id != self.school.id:
            self.add_error('subject', 'This subject is not managed under this school.')

        if school_class and subject and weight > 0:
            existing_weight = ResultComponent.objects.filter(
                school_class=school_class,
                subject=subject,
            ).exclude(pk=self.instance.pk).values_list('weight', flat=True)
            total_weight = sum(existing_weight) + weight
            if total_weight > 100:
                self.add_error('weight', f'Total assessment weight for this class and subject cannot exceed 100%. Current total would be {total_weight}%.')

        return cleaned_data


class SchoolBulkResultComponentForm(forms.Form):
    school_class = forms.ModelChoiceField(queryset=SchoolClass.objects.none())
    component_name = forms.CharField(max_length=50)
    weight = forms.IntegerField(min_value=1, max_value=100)
    max_score = forms.IntegerField(min_value=1, initial=100)

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if self.school:
            self.fields['school_class'].queryset = SchoolClass.all_objects.filter(
                school=self.school
            ).order_by('name', 'stream')

    def get_target_subjects(self):
        if not self.school:
            return Subject.objects.none()
        return Subject.all_objects.filter(
            school=self.school,
            subject_type='academic',
        ).order_by('name')

    def clean_school_class(self):
        school_class = self.cleaned_data.get('school_class')
        if self.school and school_class and school_class.school_id != self.school.id:
            raise forms.ValidationError('This class is not managed under this school.')
        return school_class

    def clean_component_name(self):
        return (self.cleaned_data.get('component_name') or '').strip()

    def clean(self):
        cleaned_data = super().clean()
        school_class = cleaned_data.get('school_class')
        component_name = cleaned_data.get('component_name')
        weight = cleaned_data.get('weight') or 0

        if not school_class or not component_name or weight <= 0:
            return cleaned_data

        subjects = self.get_target_subjects()
        if not subjects.exists():
            raise forms.ValidationError('Add academic subjects before applying an assessment structure.')

        over_limit_subjects = []
        for subject in subjects:
            existing_component = ResultComponent.objects.filter(
                school_class=school_class,
                subject=subject,
                component_name=component_name,
            ).first()
            existing_weights = ResultComponent.objects.filter(
                school_class=school_class,
                subject=subject,
            )
            if existing_component:
                existing_weights = existing_weights.exclude(pk=existing_component.pk)
            total_weight = sum(existing_weights.values_list('weight', flat=True)) + weight
            if total_weight > 100:
                over_limit_subjects.append(f'{subject.name} ({total_weight}%)')

        if over_limit_subjects:
            shown_subjects = ', '.join(over_limit_subjects[:5])
            if len(over_limit_subjects) > 5:
                shown_subjects += ', ...'
            self.add_error(
                'weight',
                f'Total assessment weight cannot exceed 100% for: {shown_subjects}.',
            )

        return cleaned_data


class SchoolClassTeacherAssignmentForm(forms.Form):
    school_class = forms.ModelChoiceField(queryset=SchoolClass.objects.none())
    teacher = forms.ModelChoiceField(queryset=Teacher.objects.none())
    can_assign_parent_wards = forms.BooleanField(
        required=False,
        label='Allow parent-ward assignment',
        help_text='When enabled, this class teacher can link learners in the assigned class to parent portal accounts.',
    )

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if self.school:
            self.fields['school_class'].queryset = SchoolClass.all_objects.filter(
                school=self.school
            ).order_by('name', 'stream')
            self.fields['teacher'].queryset = Teacher.all_objects.filter(
                school=self.school
            ).select_related('user').order_by('user__first_name', 'user__last_name', 'employee_id')

    def clean(self):
        cleaned_data = super().clean()
        school_class = cleaned_data.get('school_class')
        teacher = cleaned_data.get('teacher')

        if self.school and school_class and school_class.school_id != self.school.id:
            self.add_error('school_class', 'This class is not managed under this school.')
        if self.school and teacher and teacher.school_id != self.school.id:
            self.add_error('teacher', 'This teacher is not managed under this school.')

        if school_class and teacher:
            existing_teacher_class = ClassTeacher.objects.filter(teacher=teacher).exclude(
                school_class=school_class
            ).select_related('school_class').first()
            if existing_teacher_class:
                self.add_error(
                    'teacher',
                    f'{teacher} is already class teacher for {existing_teacher_class.school_class}.',
                )

        return cleaned_data


class SchoolHeadTeacherAssignmentForm(forms.ModelForm):
    class Meta:
        model = HeadTeacher
        fields = ['teacher', 'title', 'classes', 'signature']
        widgets = {
            'classes': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if self.school:
            self.fields['teacher'].queryset = Teacher.all_objects.filter(
                school=self.school,
            ).select_related('user').order_by('user__first_name', 'user__last_name', 'employee_id')
            self.fields['classes'].queryset = SchoolClass.all_objects.filter(
                school=self.school,
            ).order_by('name', 'stream')

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        classes = cleaned_data.get('classes')

        if self.school and teacher and teacher.school_id != self.school.id:
            self.add_error('teacher', 'This staff member is not managed under this school.')
        if self.school and classes:
            invalid_classes = [school_class for school_class in classes if school_class.school_id != self.school.id]
            if invalid_classes:
                self.add_error('classes', 'One or more selected classes are not managed under this school.')

        return cleaned_data


class SchoolWardParentAssignmentForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.none(), label='Learner')
    parent_user = forms.ModelChoiceField(queryset=User.objects.none(), label='Parent account')
    relationship = forms.ChoiceField(choices=Guardian.RELATIONSHIP_CHOICES)
    is_primary_contact = forms.BooleanField(required=False, label='Primary contact')
    is_emergency_contact = forms.BooleanField(required=False, label='Emergency contact')

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        self.allowed_class = kwargs.pop('allowed_class', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

        if self.school:
            students = Student.all_objects.filter(
                school=self.school,
            ).select_related('user', 'school_class').order_by(
                'school_class__name',
                'school_class__stream',
                'user__first_name',
                'user__last_name',
                'student_id',
            )
            if self.allowed_class:
                students = students.filter(school_class=self.allowed_class)
            self.fields['student'].queryset = students

            parent_user_ids = [
                membership.user_id
                for membership in SchoolMembership.objects.filter(
                    school=self.school,
                    is_active=True,
                    user__is_superuser=False,
                )
                if 'parent' in membership.get_all_roles()
            ]
            self.fields['parent_user'].queryset = User.objects.filter(
                id__in=parent_user_ids,
                is_superuser=False,
            ).distinct().order_by('first_name', 'last_name', 'username')

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        parent_user = cleaned_data.get('parent_user')

        if self.school and student and student.school_id != self.school.id:
            self.add_error('student', 'This learner is not managed under this school.')
        if self.allowed_class and student and student.school_class_id != self.allowed_class.id:
            self.add_error('student', 'You can only assign parent accounts to learners in your assigned class.')
        if self.school and parent_user:
            membership = parent_user.school_memberships.filter(
                school=self.school,
                is_active=True,
            ).first()
            is_parent = bool(membership and 'parent' in membership.get_all_roles())
            if not is_parent:
                self.add_error('parent_user', 'This parent account is not active under this school.')

        return cleaned_data


class SchoolGradingSystemForm(forms.ModelForm):
    class Meta:
        model = GradingSystem
        fields = ['min_score', 'max_score', 'grade', 'grade_point', 'remark']

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        _style_fields(self)

    def clean(self):
        cleaned_data = super().clean()
        min_score = cleaned_data.get('min_score')
        max_score = cleaned_data.get('max_score')

        if min_score is not None and max_score is not None:
            if min_score < 0 or max_score > 100:
                self.add_error('min_score', 'Grade ranges must stay within 0 to 100.')
            if min_score > max_score:
                self.add_error('max_score', 'Maximum score must be greater than or equal to minimum score.')

            if self.school:
                overlapping = GradingSystem.all_objects.filter(
                    school=self.school,
                    min_score__lte=max_score,
                    max_score__gte=min_score,
                ).exclude(pk=self.instance.pk)
                if overlapping.exists():
                    self.add_error('min_score', 'This score range overlaps an existing grade range.')

        return cleaned_data


class SchoolExamScheduleForm(forms.Form):
    school_class = forms.ModelChoiceField(queryset=SchoolClass.objects.none())
    subject = forms.ModelChoiceField(queryset=Subject.objects.none())
    exam_date = forms.DateTimeField(widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    duration_minutes = forms.IntegerField(min_value=1, label='Duration (minutes)')
    room = forms.CharField(max_length=50, required=False)
    invigilator = forms.ModelChoiceField(queryset=Teacher.objects.none(), required=False)
    academic_year = forms.ChoiceField(choices=())

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        self.allowed_class = kwargs.pop('allowed_class', None)
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        included_sessions = []
        if self.instance:
            included_sessions.append(self.instance.academic_event.academic_year)
        self.fields['academic_year'].choices = existing_session_choices(self.school, include=included_sessions)
        _style_fields(self)

        if self.school:
            classes = SchoolClass.all_objects.filter(school=self.school).order_by('name', 'stream')
            if self.allowed_class:
                classes = classes.filter(pk=self.allowed_class.pk)
                self.fields['school_class'].initial = self.allowed_class
            self.fields['school_class'].queryset = classes
            self.fields['subject'].queryset = Subject.all_objects.filter(
                school=self.school,
                subject_type='academic',
            ).order_by('name')
            self.fields['invigilator'].queryset = Teacher.all_objects.filter(
                school=self.school
            ).select_related('user').order_by('user__first_name', 'user__last_name', 'employee_id')

        if self.instance:
            self.fields['school_class'].initial = self.instance.school_class
            self.fields['subject'].initial = self.instance.subject
            self.fields['exam_date'].initial = self.instance.exam_date
            self.fields['duration_minutes'].initial = int(self.instance.duration.total_seconds() // 60)
            self.fields['room'].initial = self.instance.room
            self.fields['invigilator'].initial = self.instance.invigilator
            self.fields['academic_year'].initial = self.instance.academic_event.academic_year

    def clean(self):
        cleaned_data = super().clean()
        school_class = cleaned_data.get('school_class')
        subject = cleaned_data.get('subject')
        invigilator = cleaned_data.get('invigilator')

        if self.allowed_class and school_class and school_class.pk != self.allowed_class.pk:
            self.add_error('school_class', 'You can only manage exam schedules for your assigned class.')
        if self.school and school_class and school_class.school_id != self.school.id:
            self.add_error('school_class', 'This class is not managed under this school.')
        if self.school and subject and subject.school_id != self.school.id:
            self.add_error('subject', 'This subject is not managed under this school.')
        if self.school and invigilator and invigilator.school_id != self.school.id:
            self.add_error('invigilator', 'This invigilator is not managed under this school.')

        return cleaned_data
