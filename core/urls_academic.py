"""
URL patterns for Academic Management System
"""

from django.urls import path
from . import views_academic
from . import views_timetable

app_name = 'academic'

urlpatterns = [
    # Curriculum Management URLs
    path('curriculum/', views_academic.curriculum_list, name='curriculum_list'),
    path('curriculum/create/', views_academic.curriculum_create, name='curriculum_create'),
    path('curriculum/<int:curriculum_id>/', views_academic.curriculum_detail, name='curriculum_detail'),
    path('curriculum/<int:curriculum_id>/edit/', views_academic.curriculum_edit, name='curriculum_edit'),
    
    # Lesson Planning URLs
    path('lesson-plans/', views_academic.lesson_plan_list, name='lesson_plan_list'),
    path('lesson-plans/create/', views_academic.lesson_plan_create, name='lesson_plan_create'),
    path('lesson-plans/<int:lesson_plan_id>/', views_academic.lesson_plan_detail, name='lesson_plan_detail'),
    path('lesson-plans/<int:lesson_plan_id>/edit/', views_academic.lesson_plan_edit, name='lesson_plan_edit'),
    path('lesson-plans/<int:lesson_plan_id>/toggle-completion/', views_academic.toggle_lesson_completion, name='toggle_lesson_completion'),
    path('lesson-plans/<int:lesson_plan_id>/notes/', views_academic.lesson_plan_notes, name='lesson_plan_notes'),
    
    # Lesson Note URLs
    path('lesson-notes/', views_academic.lesson_note_list, name='lesson_note_list'),
    path('lesson-notes/create/', views_academic.lesson_note_create, name='lesson_note_create'),
    path('lesson-notes/<int:lesson_note_id>/', views_academic.lesson_note_detail, name='lesson_note_detail'),
    path('lesson-notes/<int:lesson_note_id>/edit/', views_academic.lesson_note_edit, name='lesson_note_edit'),
    path('lesson-notes/<int:lesson_note_id>/delete/', views_academic.lesson_note_delete, name='lesson_note_delete'),
    
    # Coverage Tracking URLs
    path('coverage-report/', views_academic.coverage_report, name='coverage_report'),
    
    # Assignment Management URLs
    path('assignments/', views_academic.assignment_list, name='assignment_list'),
    path('assignments/create/', views_academic.assignment_create, name='assignment_create'),
    path('assignments/<int:assignment_id>/', views_academic.assignment_detail, name='assignment_detail'),
    path('assignments/<int:assignment_id>/edit/', views_academic.assignment_edit, name='assignment_edit'),
    path('assignments/<int:assignment_id>/submit/', views_academic.submit_assignment, name='submit_assignment'),
    path('submissions/<int:submission_id>/grade/', views_academic.grade_submission, name='grade_submission'),
    
    # Academic Calendar URLs
    path('calendar/', views_academic.academic_calendar, name='calendar'),
    
    # Timetable Management URLs
    path('timetable/', views_academic.timetable_list, name='timetable_list'),
    path('timetable/create/', views_academic.timetable_create, name='timetable_create'),
    path('timetable/enhanced-create/', views_academic.enhanced_timetable_create, name='enhanced_timetable_create'),
    path('timetable/<int:timetable_id>/edit/', views_academic.timetable_edit, name='timetable_edit'),
    path('timetable/<int:timetable_id>/delete/', views_academic.timetable_delete, name='timetable_delete'),
    path('timetable/view/<int:class_id>/', views_academic.view_class_timetable, name='view_class_timetable'),
    
    # Enhanced Timetable Management URLs (commented out until views_timetable is ready)
    # path('timetable/dashboard/', views_timetable.timetable_dashboard, name='timetable_dashboard'),
    # path('timetable/enhanced-create/', views_timetable.enhanced_timetable_create, name='enhanced_timetable_create'),
    # path('timetable/bulk-create/', views_timetable.bulk_timetable_create, name='bulk_timetable_create'),
    # path('timetable/conflicts-check/', views_timetable.timetable_conflicts_check, name='timetable_conflicts_check'),
    # path('timetable/teacher/<int:teacher_id>/', views_timetable.teacher_timetable_view, name='teacher_timetable_view'),
    # path('timetable/my-timetable/', views_timetable.teacher_timetable_view, name='my_timetable'),
    
    # Time Slot Management URLs
    path('time-slots/', views_timetable.time_slot_list, name='time_slot_list'),
    path('time-slots/create/', views_timetable.time_slot_create, name='time_slot_create'),
    path('time-slots/<int:slot_id>/edit/', views_timetable.time_slot_edit, name='time_slot_edit'),
    path('time-slots/<int:slot_id>/delete/', views_timetable.time_slot_delete, name='time_slot_delete'),
    path('time-slots/bulk-create/', views_timetable.bulk_time_slot_create, name='bulk_time_slot_create'),
    
    # Room Management URLs
    path('rooms/', views_timetable.room_list, name='room_list'),
    path('rooms/create/', views_timetable.room_create, name='room_create'),
    path('rooms/<int:room_id>/edit/', views_timetable.room_edit, name='room_edit'),
    path('rooms/<int:room_id>/delete/', views_timetable.room_delete, name='room_delete'),
    
    # AJAX URLs
    path('api/learning-objectives/', views_academic.get_learning_objectives, name='get_learning_objectives'),
    path('timetable/conflicts-check/', views_academic.timetable_conflicts_check, name='timetable_conflicts_check'),
    
    # Student URLs
    path('student/curriculum/', views_academic.student_curriculum_view, name='student_curriculum'),
    path('student/lesson-plans/', views_academic.student_lesson_plans_view, name='student_lesson_plans'),
    path('student/timetable/', views_academic.student_timetable_view, name='student_timetable'),
]
