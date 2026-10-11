"""
Enhanced Forms for Timetable Management
"""

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import (
    ClassTeacher, TimeSlot, Timetable, RoomAssignment, Subject, Teacher, SchoolClass, Term
)


class TimeSlotForm(forms.ModelForm):
    """Form for creating and editing time slots"""
    
    class Meta:
        model = TimeSlot
        fields = ['name', 'start_time', 'end_time', 'day_of_week', 'is_active']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'day_of_week': forms.Select(choices=[
                (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
                (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
            ], attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Period 1'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        day_of_week = cleaned_data.get('day_of_week')
        
        if start_time and end_time and end_time <= start_time:
            raise ValidationError("End time must be after start time.")
        
        # Check for overlapping time slots on the same day
        if start_time and end_time and day_of_week is not None:
            overlapping = TimeSlot.objects.filter(
                day_of_week=day_of_week,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            
            if overlapping.exists():
                raise ValidationError(f"This time slot overlaps with existing slot: {overlapping.first()}")
        
        return cleaned_data


class BulkTimeSlotForm(forms.Form):
    """Form for creating multiple time slots at once"""
    
    SCHEDULE_TEMPLATES = [
        ('', 'Select a template'),
        ('primary', 'Primary School (8 periods, 40 min each)'),
        ('secondary', 'Secondary School (8 periods, 45 min each)'),
        ('university', 'University (6 periods, 1 hour each)'),
        ('custom', 'Custom Schedule'),
    ]
    
    template = forms.ChoiceField(
        choices=SCHEDULE_TEMPLATES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    days = forms.MultipleChoiceField(
        choices=[
            (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
            (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
        ],
        widget=forms.CheckboxSelectMultiple(),
        initial=[0, 1, 2, 3, 4]  # Monday to Friday by default
    )
    
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        initial='08:00'
    )
    
    periods = forms.IntegerField(
        min_value=1,
        max_value=12,
        initial=8,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    period_duration = forms.IntegerField(
        min_value=30,
        max_value=120,
        initial=40,
        help_text="Duration in minutes",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    break_duration = forms.IntegerField(
        min_value=5,
        max_value=60,
        initial=10,
        help_text="Break duration in minutes",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    lunch_break_after = forms.IntegerField(
        min_value=0,
        max_value=12,
        initial=4,
        help_text="Add lunch break after this period (0 for no lunch break)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    lunch_duration = forms.IntegerField(
        min_value=30,
        max_value=120,
        initial=60,
        help_text="Lunch break duration in minutes",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class TimetableEntryForm(forms.ModelForm):
    """Enhanced form for creating individual timetable entries"""
    
    class Meta:
        model = Timetable
        fields = ['time_slot', 'subject', 'teacher', 'school_class', 'room']
        widgets = {
            'time_slot': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'school_class': forms.Select(attrs={'class': 'form-select'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        term = kwargs.pop('term', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter based on user role
        if user and user.has_role('class_teacher'):
            try:
                class_ids = ClassTeacher.objects.filter(
                    teacher=user.teacher
                ).values_list('school_class_id', flat=True)
                self.fields['school_class'].queryset = SchoolClass.objects.filter(
                    id__in=class_ids
                )
            except:
                self.fields['school_class'].queryset = SchoolClass.objects.none()
        
        # Only show active time slots
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(is_active=True).order_by(
            'day_of_week', 'start_time'
        )
        
        # Only show available rooms
        self.fields['room'].queryset = RoomAssignment.objects.filter(is_available=True)
        
        # Add empty labels
        self.fields['time_slot'].empty_label = "Select Time Slot"
        self.fields['subject'].empty_label = "Select Subject"
        self.fields['teacher'].empty_label = "Select Teacher"
        self.fields['school_class'].empty_label = "Select Class"
        self.fields['room'].empty_label = "Select Room"
    
    def clean(self):
        cleaned_data = super().clean()
        time_slot = cleaned_data.get('time_slot')
        teacher = cleaned_data.get('teacher')
        room = cleaned_data.get('room')
        school_class = cleaned_data.get('school_class')
        
        if not all([time_slot, teacher, room, school_class]):
            return cleaned_data
        
        # Get current term
        term = Term.objects.filter(is_active=True).first()
        if not term:
            raise ValidationError("No active term found.")
        
        # Check for conflicts
        conflicts = Timetable.objects.filter(
            time_slot=time_slot,
            term=term,
            is_active=True
        )
        
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)
        
        # Teacher conflict
        teacher_conflict = conflicts.filter(teacher=teacher)
        if teacher_conflict.exists():
            raise ValidationError(f"Teacher {teacher} is already assigned during {time_slot}")
        
        # Room conflict
        room_conflict = conflicts.filter(room=room)
        if room_conflict.exists():
            raise ValidationError(f"Room {room.room_name} is already booked during {time_slot}")
        
        # Class conflict
        class_conflict = conflicts.filter(school_class=school_class)
        if class_conflict.exists():
            raise ValidationError(f"Class {school_class} already has a subject during {time_slot}")
        
        return cleaned_data


class BulkTimetableForm(forms.Form):
    """Form for creating multiple timetable entries for a class"""
    
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select Class"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter classes based on user role
        if user and user.has_role('class_teacher'):
            try:
                class_ids = ClassTeacher.objects.filter(
                    teacher=user.teacher
                ).values_list('school_class_id', flat=True)
                self.fields['school_class'].queryset = SchoolClass.objects.filter(
                    id__in=class_ids
                )
            except:
                self.fields['school_class'].queryset = SchoolClass.objects.none()


class TimetableFilterForm(forms.Form):
    """Form for filtering timetable views"""
    
    class_filter = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(),
        required=False,
        empty_label="All Classes",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    teacher_filter = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        required=False,
        empty_label="All Teachers",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    subject_filter = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        empty_label="All Subjects",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    day_filter = forms.ChoiceField(
        choices=[('', 'All Days')] + [
            (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
            (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


ROOM_FIELD_CLASS = 'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100'


class RoomAssignmentForm(forms.ModelForm):
    """Form for creating and editing room assignments"""
    
    class Meta:
        model = RoomAssignment
        fields = ['room_name', 'capacity', 'room_type', 'is_available']
        widgets = {
            'room_name': forms.TextInput(attrs={
                'class': ROOM_FIELD_CLASS,
                'placeholder': 'e.g. Room 101, Science Lab A',
            }),
            'capacity': forms.NumberInput(attrs={
                'class': ROOM_FIELD_CLASS,
                'min': '1',
                'placeholder': 'e.g. 35',
            }),
            'room_type': forms.TextInput(attrs={
                'class': ROOM_FIELD_CLASS,
                'placeholder': 'e.g. Classroom, Laboratory, Hall',
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500',
            }),
        }
    
    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity and capacity < 1:
            raise ValidationError("Capacity must be at least 1.")
        return capacity
