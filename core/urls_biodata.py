from django.urls import path
from . import views_biodata, views_payroll

urlpatterns = [
    # Student Bio-data
    path('student/<int:student_id>/biodata/', views_biodata.student_biodata_view, name='student_biodata_view'),
    path('student/<int:student_id>/guardian/add/', views_biodata.add_guardian, name='add_guardian'),
    path('guardian/<int:guardian_id>/edit/', views_biodata.edit_guardian, name='edit_guardian'),
    path('students/biodata/', views_biodata.student_list_biodata, name='student_list_biodata'),
    
    # Staff Bio-data
    path('staff/<int:teacher_id>/biodata/', views_biodata.staff_biodata_view, name='staff_biodata_view'),
    path('staff/<int:teacher_id>/qualification/add/', views_biodata.add_qualification, name='add_qualification'),
    path('staff/<int:teacher_id>/guarantor/add/', views_biodata.add_guarantor, name='add_guarantor'),
    path('staff/<int:teacher_id>/bank-account/', views_biodata.manage_bank_account, name='manage_bank_account'),
    path('staff/biodata/', views_biodata.staff_list_biodata, name='staff_list_biodata'),
    
    # Payment Schedule
    path('payment-schedule/generate/', views_payroll.generate_payment_schedule, name='generate_payment_schedule'),
    path('payment-schedule/', views_payroll.payment_schedule_list, name='payment_schedule_list'),
    path('payment-schedule/<int:schedule_id>/mark-paid/', views_payroll.mark_payment_paid, name='mark_payment_paid'),
]
