"""
Forms for Academic Management System
"""

from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from ckeditor.widgets import CKEditorWidget
from .models import (
    Curriculum, LearningObjective, SyllabusContent, LessonPlan, LessonNote,
    AcademicEvent, Holiday, ExamSchedule, TimeSlot, Timetable,
    Assignment, AssignmentSubmission, Subject, SchoolClass, Teacher, Term
)
from .academic_choices import existing_session_choices
from .services_academic import ensure_learning_objective, parse_learning_objective_titles
from .services_curriculum_installer import LEVEL_CHOICES


def _use_session_dropdown(form):
    included_sessions = []
    if getattr(form.instance, 'pk', None):
        included_sessions.append(form.instance.academic_year)
    form.fields['academic_year'].widget = forms.Select(
        choices=existing_session_choices(include=included_sessions)
    )


class CurriculumForm(forms.ModelForm):
    """Form for creating and editing curricula"""
    
    class Meta:
        model = Curriculum
        fields = ['title', 'description', 'academic_year', 'subjects', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Example: JSS 2 Mathematics Curriculum'}),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Summarize the topics, standards, and expected coverage for this academic year.',
            }),
            'academic_year': forms.Select(),
            'subjects': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        _use_session_dropdown(self)
        
        if self.user:
            if self.user.has_role('super_admin'):
                self.fields['subjects'].queryset = Subject.objects.all().order_by('name')
            elif self.user.has_role('subject_teacher'):
                teacher = getattr(self.user, 'teacher', None)
                self.fields['subjects'].queryset = (
                    teacher.subjects.all().order_by('name')
                    if teacher
                    else Subject.objects.none()
                )
    
    def clean(self):
        cleaned_data = super().clean()
        is_published = cleaned_data.get('is_published')
        
        # Objectives are added on the edit screen after the curriculum exists.
        if is_published and not self.instance.pk:
            raise ValidationError(
                "Create the curriculum as a draft, add at least one learning "
                "objective, then publish it."
            )
        if is_published and not self.instance.learning_objectives.exists():
            raise ValidationError("Cannot publish curriculum without learning objectives.")
        
        return cleaned_data


class LearningObjectiveForm(forms.ModelForm):
    """Form for creating and editing learning objectives"""
    
    class Meta:
        model = LearningObjective
        fields = ['title', 'description', 'subject', 'grade_level', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'order': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        curriculum = kwargs.pop('curriculum', None)
        super().__init__(*args, **kwargs)

        field_classes = (
            'w-full min-h-11 rounded-lg border border-gray-300 bg-white '
            'px-3 py-2 text-sm text-gray-900 shadow-sm '
            'focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600'
        )
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                f"{field.widget.attrs.get('class', '')} {field_classes}"
            ).strip()
        
        if curriculum:
            # Limit subjects to those in the curriculum
            self.fields['subject'].queryset = curriculum.subjects.all()

        grade_choices = [('', 'Select class / grade')]
        grade_choices.extend(
            (str(school_class), str(school_class))
            for school_class in SchoolClass.objects.all().order_by('name', 'stream')
        )
        current_grade = (
            self.data.get(self.add_prefix('grade_level'))
            or self.initial.get('grade_level')
            or getattr(self.instance, 'grade_level', '')
        )
        if current_grade and current_grade not in {value for value, _label in grade_choices}:
            grade_choices.append((current_grade, current_grade))
        self.fields['grade_level'].widget = forms.Select(
            choices=grade_choices,
            attrs={'class': field_classes},
        )
        self.fields['grade_level'].label = 'Class / grade'


class SyllabusContentForm(forms.ModelForm):
    """Form for creating and editing syllabus content"""
    
    class Meta:
        model = SyllabusContent
        fields = ['subject', 'content', 'order']
        widgets = {
            'content': CKEditorWidget(),
            'order': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        curriculum = kwargs.pop('curriculum', None)
        super().__init__(*args, **kwargs)

        field_classes = (
            'w-full min-h-11 rounded-lg border border-gray-300 bg-white '
            'px-3 py-2 text-sm text-gray-900 shadow-sm '
            'focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600'
        )
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                f"{field.widget.attrs.get('class', '')} {field_classes}"
            ).strip()
        
        if curriculum:
            self.fields['subject'].queryset = curriculum.subjects.all()


class LessonPlanForm(forms.ModelForm):
    """Form for creating and editing lesson plans"""

    estimated_duration = forms.IntegerField(
        label='Estimated duration (minutes)',
        min_value=1,
        max_value=480,
        widget=forms.NumberInput(attrs={
            'placeholder': '45',
            'inputmode': 'numeric',
            'step': '5',
        }),
        help_text='Enter the total number of minutes, for example 40 or 45.',
    )
    new_learning_objectives = forms.CharField(
        required=False,
        label='Write behavioural / learning objectives',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': (
                'By the end of the lesson, learners should be able to:\n'
                'Identify halves and quarters in everyday objects.\n'
                'Compare two fractions using concrete materials.'
            ),
        }),
        help_text='Type one observable objective per line.',
    )
    
    class Meta:
        model = LessonPlan
        fields = [
            'title', 'curriculum', 'subject', 'school_class', 'week_number',
            'average_age', 'previous_knowledge', 'learning_objectives',
            'content', 'reference_book', 'resources',
            'estimated_duration', 'is_completed'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Introduction to Fractions'}),
            'week_number': forms.NumberInput(attrs={'placeholder': '4', 'min': '1', 'max': '53'}),
            'average_age': forms.NumberInput(attrs={'placeholder': '9', 'min': '2', 'max': '30'}),
            'previous_knowledge': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Learners can identify halves and quarters from everyday objects.',
            }),
            'content': CKEditorWidget(),
            'reference_book': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'New General Mathematics Book 4, pages 42-45.',
            }),
            'resources': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Fraction chart, bottle tops, flash cards, whiteboard, worksheet.',
            }),
            'learning_objectives': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['title'].label = 'Topic / lesson title'
        self.fields['curriculum'].required = False
        self.fields['curriculum'].help_text = (
            'Optional. Attach a curriculum now or prepare the plan first.'
        )
        self.fields['learning_objectives'].label = 'Behavioural / learning objectives'
        self.fields['learning_objectives'].required = False

        if self.instance.pk and self.instance.estimated_duration:
            self.initial['estimated_duration'] = self.instance.estimated_duration_minutes

        if user and not user.has_role('super_admin') and user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Limit to teacher's subjects and classes
                self.fields['subject'].queryset = teacher.subjects.all()
                self.fields['school_class'].queryset = teacher.classes.all()
                
                # Filter curricula by teacher's subjects
                self.fields['curriculum'].queryset = Curriculum.objects.filter(
                    subjects__in=teacher.subjects.all(),
                    is_published=True
                ).distinct()
        
        # Bound values take priority so changing a curriculum during an edit works.
        curriculum_id = self.data.get('curriculum') if self.is_bound else self.instance.curriculum_id
        subject_id = self.data.get('subject') if self.is_bound else self.instance.subject_id
        if curriculum_id and subject_id:
            try:
                curriculum = Curriculum.objects.get(pk=curriculum_id)
                self.fields['learning_objectives'].queryset = curriculum.learning_objectives.filter(
                    subject_id=subject_id
                )
            except (Curriculum.DoesNotExist, ValueError):
                self.fields['learning_objectives'].queryset = LearningObjective.objects.none()
        elif subject_id:
            self.fields['learning_objectives'].queryset = LearningObjective.objects.filter(
                curriculum__isnull=True,
                subject_id=subject_id,
            )
        else:
            self.fields['learning_objectives'].queryset = LearningObjective.objects.none()

    def clean_estimated_duration(self):
        return timedelta(minutes=self.cleaned_data['estimated_duration'])

    def clean(self):
        cleaned_data = super().clean()
        selected = cleaned_data.get('learning_objectives')
        new_titles = parse_learning_objective_titles(
            cleaned_data.get('new_learning_objectives')
        )
        curriculum = cleaned_data.get('curriculum')
        subject = cleaned_data.get('subject')

        if new_titles and not subject:
            self.add_error(
                'new_learning_objectives',
                'Select a subject before adding new objectives.',
            )
        elif new_titles and curriculum and subject and curriculum.pk:
            if not curriculum.subjects.filter(pk=subject.pk).exists():
                self.add_error(
                    'subject',
                    'This subject is not part of the selected curriculum.',
                )

        if curriculum and not selected and not new_titles:
            self.add_error(
                'learning_objectives',
                'Add or select at least one objective for the selected curriculum.',
            )

        cleaned_data['parsed_new_objectives'] = new_titles
        return cleaned_data

    def _save_m2m(self):
        super()._save_m2m()
        self._attach_new_objectives()

    def _attach_new_objectives(self):
        titles = self.cleaned_data.get('parsed_new_objectives') or []
        if not titles:
            return

        curriculum = self.cleaned_data['curriculum']
        subject = self.cleaned_data['subject']
        school_class = self.cleaned_data.get('school_class')
        grade_level = str(school_class) if school_class else 'General'

        for title in titles:
            objective, _created = ensure_learning_objective(
                curriculum,
                subject,
                title,
                grade_level=grade_level,
            )
            self.instance.learning_objectives.add(objective)


class CurriculumInstallerForm(forms.Form):
    provider = forms.ChoiceField(
        choices=(
            ('federal', 'Federal / NERDC curriculum'),
            ('lagos', 'Lagos State curriculum and optional harmonised calendar'),
        ),
        widget=forms.RadioSelect,
        initial='federal',
    )
    levels = forms.MultipleChoiceField(
        choices=LEVEL_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        help_text='Choose only the class levels your school needs.',
    )
    include_calendar = forms.BooleanField(
        required=False,
        initial=True,
        label='Install the Lagos 2026/2027 terms and calendar',
    )
    activate_first_term = forms.BooleanField(
        required=False,
        label='Make the installed First Term active',
        help_text='Leave this off to preserve the school’s current active term.',
    )
    confirmation = forms.BooleanField(
        required=True,
        label='I have reviewed the provider and class levels above.',
    )

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get('provider')
        if provider == 'federal':
            cleaned['include_calendar'] = False
            cleaned['activate_first_term'] = False
        elif cleaned.get('activate_first_term') and not cleaned.get('include_calendar'):
            self.add_error(
                'activate_first_term',
                'Install the Lagos calendar before making its First Term active.',
            )
        return cleaned

class LessonNoteForm(forms.ModelForm):
    """Form for creating and editing lesson notes"""
    
    class Meta:
        model = LessonNote
        fields = [
            'lesson_plan', 'curriculum', 'date_taught', 'content_covered',
            'teaching_methods', 'student_engagement', 'challenges_faced',
            'homework_assigned', 'next_lesson_plan'
        ]
        widgets = {
            'content_covered': CKEditorWidget(),
            'teaching_methods': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Example: explanation, demonstration, group work, questioning, practical work.',
            }),
            'challenges_faced': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Example: learners struggled with multiplication of fractions; more practice is needed.',
            }),
            'homework_assigned': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Example: complete exercise 4, numbers 1-10, on page 32.',
            }),
            'next_lesson_plan': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Example: revise today\'s work, then introduce equivalent fractions.',
            }),
            'date_taught': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['curriculum'].required = False
        self.fields['curriculum'].label = 'Curriculum (optional)'

        if user and not user.has_role('super_admin') and user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Limit to teacher's lesson plans
                self.fields['lesson_plan'].queryset = LessonPlan.objects.filter(teacher=teacher)
                self.fields['curriculum'].queryset = Curriculum.objects.filter(
                    subjects__in=teacher.subjects.all(),
                    is_published=True
                ).distinct()


class AcademicEventForm(forms.ModelForm):
    """Form for creating and editing academic events"""
    
    class Meta:
        model = AcademicEvent
        fields = [
            'title', 'description', 'event_type', 'start_date', 'end_date',
            'is_recurring', 'recurrence_pattern', 'academic_year', 'terms'
        ]
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'terms': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _use_session_dropdown(self)
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and end_date <= start_date:
            raise ValidationError("End date must be after start date.")
        
        return cleaned_data


class HolidayForm(forms.ModelForm):
    """Form for creating and editing holidays"""
    
    class Meta:
        model = Holiday
        fields = ['name', 'date', 'is_recurring', 'academic_year']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _use_session_dropdown(self)


class TimeSlotForm(forms.ModelForm):
    """Form for creating and editing time slots"""
    
    class Meta:
        model = TimeSlot
        fields = ['name', 'start_time', 'end_time', 'day_of_week', 'is_active']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'day_of_week': forms.Select(choices=[
                (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
                (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
            ]),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        
        return cleaned_data


class TimetableForm(forms.ModelForm):
    """Form for creating and editing timetable entries"""
    
    class Meta:
        model = Timetable
        fields = [
            'time_slot', 'subject', 'teacher', 'school_class', 
            'room', 'term', 'academic_year', 'is_active'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _use_session_dropdown(self)
        
        # Only show active time slots and available rooms
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(is_active=True)
        self.fields['room'].queryset = self.fields['room'].queryset.filter(is_available=True)


class AssignmentForm(forms.ModelForm):
    """Form for creating and editing assignments"""
    
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'subject', 'school_classes', 'due_date',
            'max_score', 'allow_late_submission', 'late_penalty_percentage', 'attachment'
        ]
        widgets = {
            'description': CKEditorWidget(),
            'due_date': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
            'school_classes': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.none()
        self.fields['school_classes'].queryset = SchoolClass.objects.none()
        teacher = getattr(user, 'teacher', None) if user else None
        if teacher and user.has_any_role(['subject_teacher', 'class_teacher']):
            from .views import _get_teacher_assessment_scope
            classes, subjects = _get_teacher_assessment_scope(teacher)
            self.fields['subject'].queryset = subjects
            self.fields['school_classes'].queryset = classes
            self.instance.teacher = teacher
        if self.instance.pk and self.instance.submissions.exists():
            for name in ('subject', 'school_classes', 'max_score', 'late_penalty_percentage'):
                self.fields[name].disabled = True
                self.fields[name].help_text = 'Locked because students have submitted work.'

    def clean(self):
        data = super().clean()
        if data.get('max_score') is not None and data['max_score'] <= 0:
            self.add_error('max_score', 'Maximum score must be greater than zero, or left blank for feedback only.')
        penalty = data.get('late_penalty_percentage')
        if penalty is not None and not 0 <= penalty <= 100:
            self.add_error('late_penalty_percentage', 'Choose a penalty between 0 and 100 percent.')
        return data


class AssignmentSubmissionForm(forms.ModelForm):
    """Form for student assignment submissions"""
    
    class Meta:
        model = AssignmentSubmission
        fields = ['submission_text']
        widgets = {
            'submission_text': CKEditorWidget(),
        }
    
    def __init__(self, *args, **kwargs):
        assignment = kwargs.pop('assignment', None)
        super().__init__(*args, **kwargs)
        
        self.fields['submission_text'].required = False
        
        if assignment:
            # Check if assignment allows submissions
            if assignment.is_overdue() and not assignment.allow_late_submission:
                # Disable form if past due and late submissions not allowed
                for field in self.fields.values():
                    field.disabled = True


class SubmissionFileForm(forms.Form):
    """Form for uploading submission files"""
    
    file = forms.FileField(
        required=False,
        help_text="Select a file to upload with your submission."
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if file:
            # Validate file size (max 10MB per file)
            max_size = 10 * 1024 * 1024  # 10MB
            if file.size > max_size:
                raise ValidationError(f"File size cannot exceed 10MB. Current size: {file.size / (1024*1024):.1f}MB")
            
            # Validate file type (basic security check)
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.zip']
            file_extension = file.name.lower().split('.')[-1] if '.' in file.name else ''
            
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError(f"File type '.{file_extension}' is not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        return file


class AssignmentGradeForm(forms.Form):
    score = forms.DecimalField(min_value=0, max_digits=5, decimal_places=2, required=False)
    feedback = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        self.fields['score'].required = assignment.max_score is not None
        self.fields['score'].disabled = assignment.max_score is None
        if assignment.max_score is not None:
            self.fields['score'].widget.attrs['max'] = assignment.max_score

    def clean_score(self):
        score = self.cleaned_data['score']
        if score is not None and self.assignment.max_score is not None and score > self.assignment.max_score:
            raise ValidationError(f'Score cannot exceed {self.assignment.max_score}.')
        return score


# Formsets for inline editing
from django.forms import inlineformset_factory

LearningObjectiveFormSet = inlineformset_factory(
    Curriculum, LearningObjective,
    form=LearningObjectiveForm,
    extra=0,
    can_delete=True
)

SyllabusContentFormSet = inlineformset_factory(
    Curriculum, SyllabusContent,
    form=SyllabusContentForm,
    extra=0,
    can_delete=True
)
