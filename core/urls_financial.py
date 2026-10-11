from django.urls import path
from . import views_financial, views_bulk, views_financial_integration, views_loans

app_name = 'financial'

urlpatterns = [
    # Financial Dashboard
    path('financial/', views_financial.financial_dashboard, name='financial_dashboard'),
    path('financial/legacy/', views_financial.financial_dashboard, name='financial_dashboard_legacy'),
    
    # Fee Management
    path('financial/fees/', views_financial.fee_management, name='fee_management'),
    path('financial/fees/create/', views_financial.create_fee_structure, name='create_fee_structure'),
    path('financial/fees/payment/', views_financial.record_payment, name='record_payment'),
    
    # Enhanced List Views with Filtering
    path('financial/student-fees/', views_financial.StudentFeeListView.as_view(), name='student_fee_list'),
    path('financial/payments/', views_financial.FeePaymentListView.as_view(), name='fee_payment_list'),
    path('financial/scholarships/list/', views_financial.ScholarshipListView.as_view(), name='scholarship_list'),
    path('financial/payroll/list/', views_financial.StaffPayrollListView.as_view(), name='staff_payroll_list'),
    path('financial/transactions/', views_financial.FinancialTransactionListView.as_view(), name='transaction_list'),
    path('financial/inventory/', views_financial.inventory_management, name='inventory_management'),
    
    # Scholarship Management
    path('financial/scholarships/', views_financial.scholarship_management, name='scholarship_management'),
    path('financial/scholarships/create/', views_financial.create_scholarship, name='create_scholarship'),
    path('financial/scholarships/<int:scholarship_id>/edit/', views_financial.edit_scholarship, name='edit_scholarship'),
    path('financial/scholarships/<int:scholarship_id>/delete/', views_financial.delete_scholarship, name='delete_scholarship'),
    path('financial/scholarships/<int:scholarship_id>/assign/', views_financial.assign_scholarship, name='assign_scholarship'),
    path('financial/scholarships/recipients/<int:recipient_id>/revoke/', views_financial.revoke_scholarship, name='revoke_scholarship'),
    path('financial/scholarships/recipients/<int:recipient_id>/delete/', views_financial.delete_scholarship_recipient, name='delete_scholarship_recipient'),
    path('financial/scholarships/recipients/<int:recipient_id>/view/', views_financial.view_scholarship_recipient, name='view_scholarship_recipient'),
   
    # Payroll Management
    path('financial/payroll/', views_financial.payroll_management, name='payroll_management'),
    path('financial/payroll/generate/', views_financial.generate_payroll, name='generate_payroll'),
    path('financial/payroll/structure/create/', views_financial.create_payroll_structure, name='create_payroll_structure'),
    # Enhanced Payroll Management
    path('financial/payroll/staff/assign/', views_financial.assign_staff_payroll_structure, name='assign_staff_payroll_structure'),
    path('financial/payroll/staff/<int:teacher_id>/edit/', views_financial.edit_staff_salary, name='edit_staff_salary'),
    path('financial/payroll/<int:payroll_id>/pay/', views_financial.mark_payroll_paid, name='mark_payroll_paid'),
    path('financial/payroll/<int:payroll_id>/delete/', views_financial.delete_payroll, name='delete_payroll'),
    path('financial/payroll/structure/<int:structure_id>/edit/', views_financial.edit_payroll_structure, name='edit_payroll_structure'),
    path('financial/payroll/structure/<int:structure_id>/delete/', views_financial.delete_payroll_structure, name='delete_payroll_structure'),

    # Teacher Loans & Deductions
    path('financial/loans/', views_loans.teacher_loans, name='teacher_loans'),
    path('financial/loans/create/', views_loans.create_loan, name='create_loan'),
    path('financial/payroll/<int:payroll_id>/add-deduction/', views_loans.add_payroll_deduction, name='add_payroll_deduction'),
    path('financial/payroll/<int:payroll_id>/payslip/', views_loans.generate_payslip, name='generate_payslip'),
    path('financial/payroll/<int:payroll_id>/send-payslip/', views_loans.send_payslip_email, name='send_payslip_email'),

    # Financial Reports
    path('financial/reports/', views_financial.financial_reports_dashboard, name='financial_reports_dashboard'),
    path('financial/reports/generate/', views_financial.generate_custom_report, name='generate_custom_report'),
    path('financial/reports/scheduled/', views_financial.scheduled_reports_list, name='scheduled_reports_list'),
    path('financial/reports/export/', views_financial.export_custom_report, name='export_custom_report'),
    path('financial/export/', views_financial.export_financial_report, name='export_financial_report'),
    
    # Enhanced Report Customization and Scheduling
    path('financial/reports/customization/<str:report_type>/', views_financial.report_customization_options, name='report_customization_options'),
    path('financial/reports/scheduled/create/', views_financial.create_scheduled_report, name='create_scheduled_report'),
    path('financial/reports/scheduled/<int:report_id>/update/', views_financial.update_scheduled_report, name='update_scheduled_report'),
    path('financial/reports/scheduled/<int:report_id>/delete/', views_financial.delete_scheduled_report, name='delete_scheduled_report'),
    path('financial/reports/scheduled/<int:report_id>/run/', views_financial.run_scheduled_report_now, name='run_scheduled_report_now'),
    path('financial/reports/scheduled/<int:report_id>/history/', views_financial.report_execution_history, name='report_execution_history'),
    path('financial/reports/templates/', views_financial.report_templates_list, name='report_templates_list'),
    path('financial/reports/templates/<str:template_key>/create/', views_financial.create_report_from_template, name='create_report_from_template'),
    path('financial/reports/validate-parameters/', views_financial.validate_report_parameters, name='validate_report_parameters'),
    
    # Analytics Dashboard
    path('financial/analytics/', views_financial.financial_analytics_dashboard, name='financial_analytics'),
    path('financial/analytics/data/', views_financial.analytics_data_ajax, name='analytics_data'),
    path('financial/analytics/export/', views_financial.export_analytics_report, name='export_analytics'),
    path('financial/analytics/data/<str:chart_type>/', views_financial.chart_data_api, name='chart_data_api'),
    
    # AJAX Endpoints for Filtering
    path('financial/ajax/filter-student-fees/', views_financial.filter_student_fees_ajax, name='filter_student_fees_ajax'),
    path('financial/ajax/filter-payments/', views_financial.filter_payments_ajax, name='filter_payments_ajax'),
    path('financial/ajax/filter-scholarships/', views_financial.filter_scholarships_ajax, name='filter_scholarships_ajax'),
    path('financial/ajax/filter-payroll/', views_financial.filter_payroll_ajax, name='filter_payroll_ajax'),
    path('financial/ajax/filter-transactions/', views_financial.filter_transactions_ajax, name='filter_transactions_ajax'),
    
    # AJAX Endpoints for Enhanced Search with Highlighting
    path('financial/ajax/search-student-fees/', views_financial.search_student_fees_ajax, name='search_student_fees_ajax'),
    path('financial/ajax/search-payments/', views_financial.search_payments_ajax, name='search_payments_ajax'),
    path('financial/ajax/search-scholarships/', views_financial.search_scholarships_ajax, name='search_scholarships_ajax'),
    path('financial/ajax/search-payroll/', views_financial.search_payroll_ajax, name='search_payroll_ajax'),
    path('financial/ajax/search-transactions/', views_financial.search_transactions_ajax, name='search_transactions_ajax'),
    
    path('financial/ajax/clear-filters/', views_financial.clear_filters_ajax, name='clear_filters_ajax'),
    
    # AJAX Endpoints for Auto-complete
    path('financial/ajax/autocomplete-students/', views_financial.autocomplete_students_ajax, name='autocomplete_students_ajax'),
    path('financial/ajax/autocomplete-teachers/', views_financial.autocomplete_teachers_ajax, name='autocomplete_teachers_ajax'),
    path('financial/ajax/autocomplete-references/', views_financial.autocomplete_references_ajax, name='autocomplete_references_ajax'),
    path('financial/ajax/autocomplete-general/', views_financial.autocomplete_general_ajax, name='autocomplete_general_ajax'),
    
    # AJAX Endpoints for Dependent Filters
    path('financial/ajax/terms-by-class/', views_financial.get_terms_by_class_ajax, name='get_terms_by_class_ajax'),
    
    # AJAX Endpoints for Search Highlighting
    path('financial/ajax/search-highlight/', views_financial.search_highlight_ajax, name='search_highlight_ajax'),
    
    # AJAX Endpoints for Export
    path('financial/ajax/export-filtered/', views_financial.export_filtered_data_ajax, name='export_filtered_data_ajax'),
    
    # Bulk Operations
    path('financial/bulk/', views_bulk.BulkOperationsView.as_view(), name='bulk_operations'),
    path('financial/bulk/fee-structures/', views_bulk.bulk_create_fee_structures, name='bulk_create_fee_structures'),
    path('financial/bulk/payments/', views_bulk.bulk_process_payments, name='bulk_process_payments'),
    path('financial/bulk/payroll/', views_bulk.bulk_generate_payroll, name='bulk_generate_payroll'),
    path('financial/bulk/progress/<str:operation_id>/', views_bulk.bulk_operation_progress, name='bulk_operation_progress'),
    path('financial/bulk/report/<str:operation_id>/', views_bulk.bulk_operation_report, name='bulk_operation_report'),
    path('financial/bulk/download/<str:operation_id>/', views_bulk.download_bulk_report, name='download_bulk_report'),
    path('financial/bulk/cancel/<str:operation_id>/', views_bulk.cancel_bulk_operation, name='cancel_bulk_operation'),
    path('financial/bulk/cleanup/<str:operation_id>/', views_bulk.cleanup_bulk_operation, name='cleanup_bulk_operation'),
    
    # Audit Logging
    path('financial/audit/', views_financial.audit_logs, name='audit_logs'),
    path('financial/audit/search/', views_financial.audit_search, name='audit_search'),
    path('financial/audit/object/<str:model_name>/<int:object_id>/', views_financial.object_audit_history, name='object_audit_history'),
    path('financial/audit/user/<int:user_id>/', views_financial.user_audit_activity, name='user_audit_activity'),
    path('financial/audit/summary/', views_financial.audit_operation_summary, name='audit_operation_summary'),
    
    # AJAX Endpoints for Audit Logs
    path('financial/ajax/audit-logs/', views_financial.audit_logs_ajax, name='audit_logs_ajax'),
    path('financial/ajax/audit-search-suggestions/', views_financial.audit_search_suggestions_ajax, name='audit_search_suggestions_ajax'),
    
    # Notification System
    path('financial/notifications/', views_financial.notification_dashboard, name='notification_dashboard'),
    path('financial/notifications/templates/', views_financial.notification_templates, name='notification_templates'),
    path('financial/notifications/logs/', views_financial.notification_logs, name='notification_logs'),
    path('financial/notifications/test-send/', views_financial.send_test_notification, name='send_test_notification'),
    
    # AJAX Endpoints for Notifications
    path('financial/ajax/retry-failed-notifications/', views_financial.retry_failed_notifications_ajax, name='retry_failed_notifications_ajax'),
    path('financial/ajax/send-bulk-reminders/', views_financial.send_bulk_reminders_ajax, name='send_bulk_reminders_ajax'),
    path('financial/ajax/notification-statistics/', views_financial.notification_statistics_ajax, name='notification_statistics_ajax'),
    path('financial/ajax/notification-cleanup/', views_financial.notification_cleanup_ajax, name='notification_cleanup_ajax'),
    
    # Integrated Views - Comprehensive System Wiring
    path('financial/integrated/payment/', views_financial_integration.integrated_payment_processing, name='integrated_payment'),
    path('financial/integrated/export/', views_financial_integration.integrated_export_interface, name='integrated_export'),
    path('financial/integrated/reconciliation/', views_financial_integration.integrated_reconciliation_dashboard, name='integrated_reconciliation'),
    path('financial/integrated/reconciliation/run/', views_financial_integration.run_manual_reconciliation, name='run_manual_reconciliation'),
]
