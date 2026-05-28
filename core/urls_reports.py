from django.urls import path
from . import views_reports

urlpatterns = [
    # Reports Dashboard
    path('reports/', views_reports.reports_dashboard, name='reports_dashboard'),
    
    # Academic Performance Report
    path('reports/academic-performance/', views_reports.academic_performance_report, name='academic_performance_report'),
    
    # Attendance Report
    path('reports/attendance/', views_reports.attendance_report, name='attendance_report'),
    
    # System Usage Report
    path('reports/system-usage/', views_reports.system_usage_report, name='system_usage_report'),
]