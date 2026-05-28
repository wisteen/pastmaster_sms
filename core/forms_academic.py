"""
Forms for Academic Management System
"""

from django import forms
from django.core.exceptions import ValidationError
from ckeditor.widgets import CKEditorWidget
from .models import (
    Curriculum, LearningObjective, SyllabusContent, LessonPlan, LessonNote,
    AcademicEvent, Holiday, ExamSchedule, TimeSlot, Timetable,
    Assignment, AssignmentSubmission, Subject, SchoolClass, Teacher, Term
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
            'academic_year': forms.TextInput(attrs={'placeholder': '2025-2026'}),
            'subjects': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Customize form based on user role
        if self.user and self.user.has_role('subject_teacher'):
            # Limit subjects to those taught by the teacher
            teacher = getattr(self.user, 'teacher', None)
            if teacher:
                self.fields['subjects'].queryset = teacher.subjects.all()
    
    def clean(self):
        cleaned_data = super().clean()
        is_published = cleaned_data.get('is_published')
        
        # If trying to publish, ensure we have learning objectives
        if is_published and self.instance.pk:
            if not self.instance.learning_objectives.exists():
                raise ValidationError("Cannot publish curriculum without learning objectives.")
        
        return cleaned_data


class LearningObjectiveForm(forms.ModelForm):
    """Form for creating and editing learning objectives"""
    
    class Meta:
        model = LearningObjective
        fields = ['title', 'description', 'subject', 'grade_level', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        curriculum = kwargs.pop('curriculum', None)
        super().__init__(*args, **kwargs)
        
        if curriculum:
            # Limit subjects to those in the curriculum
            self.fields['subject'].queryset = curriculum.subjects.all()


class SyllabusContentForm(forms.ModelForm):
    """Form for creating and editing syllabus content"""
    
    class Meta:
        model = SyllabusContent
        fields = ['subject', 'content', 'order']
        widgets = {
            'content': CKEditorWidget(),
        }
    
    def __init__(self, *args, **kwargs):
        curriculum = kwargs.pop('curriculum', None)
        super().__init__(*args, **kwargs)
        
        if curriculum:
            self.fields['subject'].queryset = curriculum.subjects.all()


class LessonPlanForm(forms.ModelForm):
    """Form for creating and editing lesson plans"""
    
    class Meta:
        model = LessonPlan
        fields = [
            'title', 'curriculum', 'subject', 'school_class', 
            'learning_objectives', 'content', 'resources', 
            'estimated_duration', 'is_completed'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Example: Introduction to Fractions'}),
            'content': CKEditorWidget(),
            'resources': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Example: textbook pages, charts, flash cards, lab materials, worksheet.',
            }),
            'learning_objectives': forms.CheckboxSelectMultiple(),
            'estimated_duration': forms.TextInput(attrs={'placeholder': 'HH:MM:SS (e.g., 01:30:00)'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.has_role('subject_teacher'):
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
        
        # Update learning objectives based on curriculum selection
        if self.instance.pk and self.instance.curriculum:
            self.fields['learning_objectives'].queryset = self.instance.curriculum.learning_objectives.filter(
                subject=self.instance.subject
            )
        elif self.data.get('curriculum') and self.data.get('subject'):
            # For POST requests, load objectives based on submitted data
            try:
                curriculum = Curriculum.objects.get(pk=self.data.get('curriculum'))
                self.fields['learning_objectives'].queryset = curriculum.learning_objectives.filter(
                    subject_id=self.data.get('subject')
                )
            except (Curriculum.DoesNotExist, ValueError):
                self.fields['learning_objectives'].queryset = LearningObjective.objects.none()
        else:
            self.fields['learning_objectives'].queryset = LearningObjective.objects.none()


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
        
        if user and user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Limit to teacher's lesson plans
                self.fields['lesson_plan'].queryset = LessonPlan.objects.filter(teacher=teacher)
                self.fields['curriculum'].queryset = Curriculum.objects.filter(
                    subjects__in=teacher.subjects.all(),
                    is_published=True
                ).distinct()
        
        # Auto-populate curriculum from lesson plan if editing
        if self.instance.pk and self.instance.lesson_plan:
            self.fields['curriculum'].initial = self.instance.lesson_plan.curriculum


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
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'school_classes': forms.CheckboxSelectMultiple(),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.has_role('subject_teacher'):
            teacher = getattr(user, 'teacher', None)
            if teacher:
                # Limit to teacher's subjects and classes
                self.fields['subject'].queryset = teacher.subjects.all()
                self.fields['school_classes'].queryset = teacher.classes.all()


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


# Formsets for inline editing
from django.forms import inlineformset_factory

LearningObjectiveFormSet = inlineformset_factory(
    Curriculum, LearningObjective,
    form=LearningObjectiveForm,
    extra=1,
    can_delete=True
)

SyllabusContentFormSet = inlineformset_factory(
    Curriculum, SyllabusContent,
    form=SyllabusContentForm,
    extra=1,
    can_delete=True
)
