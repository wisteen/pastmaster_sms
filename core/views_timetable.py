"""
Enhanced Views for Timetable Management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json

from .models import (
    TimeSlot, Timetable, RoomAssignment, Subject, Teacher, SchoolClass, Term
)
from .forms_timetable import (
    TimeSlotForm, BulkTimeSlotForm, TimetableEntryForm, BulkTimetableForm,
    TimetableFilterForm, RoomAssignmentForm
)


# Time Slot Management Views

@login_required
def time_slot_list(request):
    """List and manage time slots"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to manage time slots.')
        return redirect('core:dashboard')
    
    time_slots = TimeSlot.objects.all().order_by('day_of_week', 'start_time')
    
    # Group by day
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    slots_by_day = {}
    
    for day_num, day_name in enumerate(days):
        slots_by_day[day_name] = time_slots.filter(day_of_week=day_num)
    
    context = {
        'slots_by_day': slots_by_day,
        'days': days,
        'total_slots': time_slots.count(),
        'active_slots': time_slots.filter(is_active=True).count(),
    }
    
    return render(request, 'academic/time_slot_list.html', context)


@login_required
def time_slot_create(request):
    """Create a new time slot"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to create time slots.')
        return redirect('academic:time_slot_list')
    
    if request.method == 'POST':
        form = TimeSlotForm(request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Time slot created successfully.')
            return redirect('academic:time_slot_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TimeSlotForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'academic/time_slot_form.html', context)


@login_required
def time_slot_edit(request, slot_id):
    """Edit an existing time slot"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to edit time slots.')
        return redirect('academic:time_slot_list')
    
    time_slot = get_object_or_404(TimeSlot, id=slot_id)
    
    if request.method == 'POST':
        form = TimeSlotForm(request.POST, instance=time_slot)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Time slot updated successfully.')
            return redirect('academic:time_slot_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TimeSlotForm(instance=time_slot)
    
    context = {
        'form': form,
        'time_slot': time_slot,
        'action': 'Edit',
    }
    
    return render(request, 'academic/time_slot_form.html', context)


@login_required
def time_slot_delete(request, slot_id):
    """Delete a time slot"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to delete time slots.')
        return redirect('academic:time_slot_list')
    
    time_slot = get_object_or_404(TimeSlot, id=slot_id)
    
    # Check if time slot is being used in timetables
    if Timetable.objects.filter(time_slot=time_slot, is_active=True).exists():
        messages.error(request, 'Cannot delete time slot as it is being used in active timetables.')
        return redirect('academic:time_slot_list')
    
    if request.method == 'POST':
        time_slot.delete()
        messages.success(request, 'Time slot deleted successfully.')
        return redirect('academic:time_slot_list')
    
    context = {
        'time_slot': time_slot,
    }
    
    return render(request, 'academic/time_slot_confirm_delete.html', context)


@login_required
def bulk_time_slot_create(request):
    """Create multiple time slots using templates"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to create time slots.')
        return redirect('academic:time_slot_list')
    
    if request.method == 'POST':
        form = BulkTimeSlotForm(request.POST)
        
        if form.is_valid():
            created_count = create_time_slots_from_template(form.cleaned_data)
            
            if created_count > 0:
                messages.success(request, f'Successfully created {created_count} time slots.')
            else:
                messages.warning(request, 'No new time slots were created (may already exist).')
            
            return redirect('academic:time_slot_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BulkTimeSlotForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'academic/bulk_time_slot_form.html', context)


def create_time_slots_from_template(data):
    """Helper function to create time slots from template data"""
    
    days = data['days']
    start_time = data['start_time']
    periods = data['periods']
    period_duration = data['period_duration']
    break_duration = data['break_duration']
    lunch_break_after = data['lunch_break_after']
    lunch_duration = data['lunch_duration']
    
    created_count = 0
    
    for day in days:
        current_time = datetime.combine(datetime.today(), start_time)
        
        for period in range(1, periods + 1):
            period_start = current_time.time()
            period_end = (current_time + timedelta(minutes=period_duration)).time()
            
            # Check if time slot already exists
            if not TimeSlot.objects.filter(
                day_of_week=day,
                start_time=period_start,
                end_time=period_end
            ).exists():
                TimeSlot.objects.create(
                    name=f'Period {period}',
                    start_time=period_start,
                    end_time=period_end,
                    day_of_week=day,
                    is_active=True
                )
                created_count += 1
            
            # Move to next period
            current_time += timedelta(minutes=period_duration)
            
            # Add lunch break if specified
            if lunch_break_after > 0 and period == lunch_break_after:
                current_time += timedelta(minutes=lunch_duration)
            else:
                current_time += timedelta(minutes=break_duration)
    
    return created_count


# Enhanced Timetable Management Views

@login_required
def enhanced_timetable_create(request):
    """Enhanced timetable creation with better UX"""
    
    if not request.user.has_any_role(['class_teacher', 'super_admin']):
        messages.error(request, 'Only class teachers and admins can create timetables.')
        return redirect('academic:timetable_list')
    
    # Get current active term
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found. Please set an active term first.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = TimetableEntryForm(request.POST, term=active_term, user=request.user)
        
        if form.is_valid():
            timetable = form.save(commit=False)
            timetable.term = active_term
            timetable.academic_year = f"{active_term.start_date.year}-{active_term.end_date.year}"
            timetable.save()
            
            messages.success(request, 'Timetable entry created successfully.')
            return redirect('academic:timetable_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TimetableEntryForm(term=active_term, user=request.user)
    
    # Get available options with conflict checking
    context = {
        'form': form,
        'active_term': active_term,
        'time_slots': TimeSlot.objects.filter(is_active=True).order_by('day_of_week', 'start_time'),
        'subjects': Subject.objects.all(),
        'teachers': Teacher.objects.all(),
        'classes': SchoolClass.objects.all(),
        'rooms': RoomAssignment.objects.filter(is_available=True),
    }
    
    # Filter based on user role
    if request.user.has_role('class_teacher'):
        try:
            class_teacher = request.user.teacher.classteacher
            context['classes'] = SchoolClass.objects.filter(id=class_teacher.school_class.id)
        except:
            context['classes'] = SchoolClass.objects.none()
    
    return render(request, 'academic/enhanced_timetable_create.html', context)


@login_required
def bulk_timetable_create(request):
    """Create timetable for an entire class"""
    
    if not request.user.has_any_role(['class_teacher', 'super_admin']):
        messages.error(request, 'Only class teachers and admins can create timetables.')
        return redirect('academic:timetable_list')
    
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = BulkTimetableForm(request.POST, user=request.user)
        
        if form.is_valid():
            school_class = form.cleaned_data['school_class']
            
            # Process the bulk timetable data from the form
            timetable_data = request.POST.getlist('timetable_entries')
            created_count = 0
            
            for entry_data in timetable_data:
                if entry_data:  # Skip empty entries
                    try:
                        data = json.loads(entry_data)
                        
                        # Create timetable entry
                        Timetable.objects.create(
                            time_slot_id=data['time_slot'],
                            subject_id=data['subject'],
                            teacher_id=data['teacher'],
                            school_class=school_class,
                            room_id=data['room'],
                            term=active_term,
                            academic_year=f"{active_term.start_date.year}-{active_term.end_date.year}"
                        )
                        created_count += 1
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        continue
            
            if created_count > 0:
                messages.success(request, f'Successfully created {created_count} timetable entries.')
            else:
                messages.warning(request, 'No timetable entries were created.')
            
            return redirect('academic:timetable_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BulkTimetableForm(user=request.user)
    
    # Get data for the bulk creation interface
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('day_of_week', 'start_time')
    subjects = Subject.objects.all()
    teachers = Teacher.objects.all()
    rooms = RoomAssignment.objects.filter(is_available=True)
    
    # Group time slots by day
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    slots_by_day = {}
    
    for day_num, day_name in enumerate(days):
        slots_by_day[day_name] = time_slots.filter(day_of_week=day_num)
    
    context = {
        'form': form,
        'active_term': active_term,
        'slots_by_day': slots_by_day,
        'days': days,
        'subjects': subjects,
        'teachers': teachers,
        'rooms': rooms,
    }
    
    return render(request, 'academic/bulk_timetable_create.html', context)


@login_required
def timetable_conflicts_check(request):
    """AJAX endpoint to check for timetable conflicts"""
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'})
    
    time_slot_id = request.GET.get('time_slot')
    teacher_id = request.GET.get('teacher')
    room_id = request.GET.get('room')
    class_id = request.GET.get('class')
    exclude_id = request.GET.get('exclude')  # For editing existing entries
    
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        return JsonResponse({'error': 'No active term found'})
    
    conflicts = []
    
    if time_slot_id:
        existing = Timetable.objects.filter(
            time_slot_id=time_slot_id,
            term=active_term,
            is_active=True
        )
        
        if exclude_id:
            existing = existing.exclude(id=exclude_id)
        
        # Check teacher conflict
        if teacher_id:
            teacher_conflict = existing.filter(teacher_id=teacher_id)
            if teacher_conflict.exists():
                teacher = Teacher.objects.get(id=teacher_id)
                conflicts.append({
                    'type': 'teacher',
                    'message': f'Teacher {teacher.user.get_full_name()} is already assigned during this time slot'
                })
        
        # Check room conflict
        if room_id:
            room_conflict = existing.filter(room_id=room_id)
            if room_conflict.exists():
                room = RoomAssignment.objects.get(id=room_id)
                conflicts.append({
                    'type': 'room',
                    'message': f'Room {room.room_name} is already booked during this time slot'
                })
        
        # Check class conflict
        if class_id:
            class_conflict = existing.filter(school_class_id=class_id)
            if class_conflict.exists():
                school_class = SchoolClass.objects.get(id=class_id)
                conflicts.append({
                    'type': 'class',
                    'message': f'Class {school_class} already has a subject during this time slot'
                })
    
    return JsonResponse({
        'conflicts': conflicts,
        'has_conflicts': len(conflicts) > 0
    })


@login_required
def teacher_timetable_view(request, teacher_id=None):
    """View timetable for a specific teacher"""
    
    if teacher_id:
        teacher = get_object_or_404(Teacher, id=teacher_id)
    else:
        # Show current user's timetable if they're a teacher
        if request.user.has_any_role(['subject_teacher', 'class_teacher']):
            teacher = get_object_or_404(Teacher, user=request.user)
        else:
            messages.error(request, 'Teacher not found.')
            return redirect('academic:timetable_list')
    
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found.')
        return redirect('core:dashboard')
    
    # Get teacher's timetable
    timetables = Timetable.objects.filter(
        teacher=teacher,
        term=active_term,
        is_active=True
    ).select_related('time_slot', 'subject', 'school_class', 'room').order_by(
        'time_slot__day_of_week', 'time_slot__start_time'
    )
    
    # Organize timetable by day and time
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    timetable_grid = {}
    for day_num, day_name in enumerate(days):
        timetable_grid[day_name] = {}
        for time_slot in time_slots.filter(day_of_week=day_num):
            timetable_entry = timetables.filter(time_slot=time_slot).first()
            timetable_grid[day_name][str(time_slot)] = timetable_entry
    
    context = {
        'teacher': teacher,
        'timetable_grid': timetable_grid,
        'time_slots': time_slots,
        'days': days,
        'active_term': active_term,
    }
    
    return render(request, 'academic/teacher_timetable.html', context)


# Room Management Views

@login_required
def room_list(request):
    """List all rooms"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to manage rooms.')
        return redirect('core:dashboard')
    
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    base_rooms = RoomAssignment.objects.all().order_by('room_name')
    rooms = base_rooms

    if search_query:
        rooms = rooms.filter(
            Q(room_name__icontains=search_query) |
            Q(room_type__icontains=search_query)
        )

    if status_filter == 'available':
        rooms = rooms.filter(is_available=True)
    elif status_filter == 'unavailable':
        rooms = rooms.filter(is_available=False)
    
    # Add usage statistics
    active_term = Term.objects.filter(is_active=True).first()
    total_usage = 0
    if active_term:
        total_usage = Timetable.objects.filter(
            room__in=base_rooms,
            term=active_term,
            is_active=True
        ).count()

    for room in rooms:
        room.usage_count = 0
        if active_term:
            room.usage_count = Timetable.objects.filter(
                room=room,
                term=active_term,
                is_active=True
            ).count()
    
    context = {
        'rooms': rooms,
        'total_rooms': base_rooms.count(),
        'available_rooms': base_rooms.filter(is_available=True).count(),
        'unavailable_rooms': base_rooms.filter(is_available=False).count(),
        'filtered_count': rooms.count(),
        'total_usage': total_usage,
        'active_term': active_term,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'academic/room_list.html', context)


@login_required
def room_create(request):
    """Create a new room"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to create rooms.')
        return redirect('academic:room_list')
    
    if request.method == 'POST':
        form = RoomAssignmentForm(request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Room created successfully.')
            return redirect('academic:room_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RoomAssignmentForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'academic/room_form.html', context)


@login_required
def room_edit(request, room_id):
    """Edit an existing room"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to edit rooms.')
        return redirect('academic:room_list')
    
    room = get_object_or_404(RoomAssignment, id=room_id)
    
    if request.method == 'POST':
        form = RoomAssignmentForm(request.POST, instance=room)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Room updated successfully.')
            return redirect('academic:room_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RoomAssignmentForm(instance=room)
    
    context = {
        'form': form,
        'room': room,
        'action': 'Edit',
    }
    
    return render(request, 'academic/room_form.html', context)


@login_required
def room_delete(request, room_id):
    """Delete a room"""
    
    if not request.user.has_any_role(['super_admin', 'class_teacher']):
        messages.error(request, 'You do not have permission to delete rooms.')
        return redirect('academic:room_list')
    
    room = get_object_or_404(RoomAssignment, id=room_id)
    
    # Check if room is being used in timetables
    if Timetable.objects.filter(room=room, is_active=True).exists():
        messages.error(request, 'Cannot delete room as it is being used in active timetables.')
        return redirect('academic:room_list')
    
    if request.method == 'POST':
        room.delete()
        messages.success(request, 'Room deleted successfully.')
        return redirect('academic:room_list')
    
    context = {
        'room': room,
    }
    
    return render(request, 'academic/room_confirm_delete.html', context)


@login_required
def timetable_dashboard(request):
    """Dashboard view for timetable management"""
    
    if not request.user.has_any_role(['class_teacher', 'super_admin', 'subject_teacher']):
        messages.error(request, 'You do not have permission to access timetable dashboard.')
        return redirect('core:dashboard')
    
    active_term = Term.objects.filter(is_active=True).first()
    if not active_term:
        messages.error(request, 'No active term found.')
        return redirect('core:dashboard')
    
    # Get statistics
    total_time_slots = TimeSlot.objects.filter(is_active=True).count()
    total_timetables = Timetable.objects.filter(term=active_term, is_active=True).count()
    total_classes = SchoolClass.objects.count()
    total_rooms = RoomAssignment.objects.filter(is_available=True).count()
    
    # Get recent activities
    recent_timetables = Timetable.objects.filter(
        term=active_term,
        is_active=True
    ).select_related(
        'time_slot', 'subject', 'teacher', 'school_class', 'room'
    ).order_by('-id')[:10]
    
    # Get classes with incomplete timetables
    classes_with_gaps = []
    for school_class in SchoolClass.objects.all():
        class_timetables = Timetable.objects.filter(
            school_class=school_class,
            term=active_term,
            is_active=True
        ).count()
        
        if class_timetables < total_time_slots:
            classes_with_gaps.append({
                'class': school_class,
                'filled_slots': class_timetables,
                'total_slots': total_time_slots,
                'completion_percentage': (class_timetables / total_time_slots * 100) if total_time_slots > 0 else 0
            })
    
    context = {
        'active_term': active_term,
        'stats': {
            'total_time_slots': total_time_slots,
            'total_timetables': total_timetables,
            'total_classes': total_classes,
            'total_rooms': total_rooms,
        },
        'recent_timetables': recent_timetables,
        'classes_with_gaps': classes_with_gaps,
    }
    
    return render(request, 'academic/timetable_dashboard.html', context)

