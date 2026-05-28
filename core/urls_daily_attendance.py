from django.urls import path
from . import views_daily_attendance

urlpatterns = [
    path('daily-attendance/', views_daily_attendance.daily_attendance_dashboard, name='daily_attendance_dashboard'),
    path('daily-attendance/mark/', views_daily_attendance.mark_daily_attendance, name='mark_daily_attendance'),
    path('daily-attendance/mark/<int:class_id>/', views_daily_attendance.mark_daily_attendance, name='mark_daily_attendance_class'),
    path('daily-attendance/view/<int:session_id>/', views_daily_attendance.view_daily_attendance, name='view_daily_attendance'),
    path('daily-attendance/term-analysis/', views_daily_attendance.term_attendance_analysis, name='term_attendance_analysis'),
    path('daily-attendance/term-analysis/<int:term_id>/', views_daily_attendance.term_attendance_analysis, name='term_attendance_analysis_term'),
    path('daily-attendance/student/<int:student_id>/', views_daily_attendance.student_attendance_detail, name='student_attendance_detail'),
    path('daily-attendance/student/<int:student_id>/<int:term_id>/', views_daily_attendance.student_attendance_detail, name='student_attendance_detail_term'),
    path('daily-attendance/class-report/<int:class_id>/', views_daily_attendance.class_attendance_report, name='class_attendance_report'),
    path('daily-attendance/class-report/<int:class_id>/<int:term_id>/', views_daily_attendance.class_attendance_report, name='class_attendance_report_term'),
    path('daily-attendance/export/<int:class_id>/<int:term_id>/', views_daily_attendance.export_attendance_csv, name='export_attendance_csv'),
]
