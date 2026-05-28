from django.urls import path
from . import views_attendance

app_name = 'attendance'

urlpatterns = [
    # ID Card Management
    path('id-card/generate/<str:card_type>/<int:holder_id>/', views_attendance.generate_id_card, name='generate_id_card'),
    path('id-card/bulk-generate/', views_attendance.bulk_generate_id_cards, name='bulk_generate_cards'),
    path('id-card/list/', views_attendance.id_card_list, name='id_card_list'),
    path('id-card/download/<int:card_id>/', views_attendance.download_id_card, name='download_id_card'),
    
    # Attendance Marking
    path('mark/', views_attendance.mark_attendance_view, name='mark_attendance'),
    path('scan/', views_attendance.scan_barcode, name='scan_barcode'),
    
    # Reports
    path('report/', views_attendance.attendance_report, name='report'),
    path('student/<int:student_id>/', views_attendance.student_attendance_detail, name='student_detail'),
    
    # Visitor Management
    path('visitor/log/', views_attendance.visitor_log, name='visitor_log'),
    path('visitor/checkout/<int:visitor_id>/', views_attendance.visitor_checkout, name='visitor_checkout'),
    path('visitor/report/', views_attendance.visitor_report, name='visitor_report'),
]
