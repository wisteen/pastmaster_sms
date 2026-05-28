from django.urls import path
from . import views_attendance_api

urlpatterns = [
    path('api/attendance/mark/', views_attendance_api.mark_attendance, name='api_mark_attendance'),
    path('api/attendance/active-session/', views_attendance_api.get_active_session, name='api_active_session'),
    path('api/attendance/today/<int:session_id>/', views_attendance_api.get_today_attendance, name='api_today_attendance'),
]
