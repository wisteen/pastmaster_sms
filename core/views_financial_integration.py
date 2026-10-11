"""
Financial Management Integration Module
This module wires together all financial components for seamless operation.

Requirements: All requirements - Integration and system wiring
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta
import logging

from .models import *
from .filters_financial import (
    StudentFeeFilterMixin, FeePaymentFilterMixin, ScholarshipFilterMixin,
    StaffPayrollFilterMixin, FinancialTransactionFilterMixin, FilterStatePersistence
)
from .services_analytics import FinancialAnalyticsService
from .services_audit import AuditLogSearchService, AuditLogger
from .services_notification import NotificationService
from .services_notification_tracking import NotificationTrackingService
from .services_reports import ReportService
from .services_report_customization import ReportCustomizationService
from .services_export import ExportService
from .services_reconciliation import ReconciliationService
from .services_bulk import BulkOperationService
from .services_financial_integrity import sync_scholarship_fee_applications

logger = logging.getLogger(__name__)


class FinancialIntegrationService:
    """
    Central integration service that coordinates all financial components
    """

    @staticmethod
    def _student_fees(school=None):
        if school:
            return StudentFee.all_objects.filter(student__school=school)
        return StudentFee.objects.all()

    @staticmethod
    def _fee_payments(school=None):
        if school:
            return FeePayment.all_objects.filter(student_fee__student__school=school)
        return FeePayment.objects.all()

    @staticmethod
    def _payrolls(school=None):
        if school:
            return StaffPayroll.all_objects.filter(teacher__school=school)
        return StaffPayroll.objects.all()

    @staticmethod
    def _scholarship_recipients(school=None):
        if school:
            return ScholarshipRecipient.all_objects.filter(student__school=school)
        return ScholarshipRecipient.objects.all()
    
    @staticmethod
    def get_integrated_dashboard_data(user, school=None):
        """
        Get comprehensive dashboard data integrating all components
        Requirements: All requirements - Integrated dashboard view
        """
        current_month = timezone.now().date().replace(day=1)
        
        # Fee collection data with filtering
        student_fees = FinancialIntegrationService._student_fees(school)
        fee_data = {
            'total_fees_due': student_fees.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'total_fees_collected': student_fees.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0,
            'pending_fees': 0,
            'collection_rate': 0
        }
        fee_data['pending_fees'] = fee_data['total_fees_due'] - fee_data['total_fees_collected']
        if fee_data['total_fees_due'] > 0:
            fee_data['collection_rate'] = (fee_data['total_fees_collected'] * 100 / fee_data['total_fees_due'])
        
        # Analytics data
        analytics_data = {
            'fee_trends': FinancialAnalyticsService.get_fee_collection_trends(months=6, school=school),
            'expense_breakdown': FinancialAnalyticsService.get_expense_breakdown(school=school),
            'income_vs_expenses': FinancialAnalyticsService.get_monthly_income_vs_expenses(months=6, school=school),
            'payment_status': FinancialAnalyticsService.get_payment_status_distribution(school=school),
            'scholarship_distribution': FinancialAnalyticsService.get_scholarship_distribution(school=school)
        }
        
        # Notification statistics
        notification_service = NotificationTrackingService()
        notification_stats = notification_service.get_delivery_statistics(days=30)
        
        # Audit activity summary
        audit_service = AuditLogSearchService()
        recent_audit_logs = audit_service.get_recent_activity(limit=10)
        
        # Reconciliation status
        reconciliation_service = ReconciliationService()
        reconciliation_status = reconciliation_service.get_reconciliation_summary()
        
        # Payroll summary
        payrolls = FinancialIntegrationService._payrolls(school)
        payroll_data = {
            'monthly_payroll': payrolls.filter(
                month=current_month
            ).aggregate(Sum('net_salary'))['net_salary__sum'] or 0,
            'processed_count': payrolls.filter(month=current_month).count(),
            'paid_count': payrolls.filter(month=current_month, is_paid=True).count()
        }
        
        # Scholarship summary
        scholarship_recipients = FinancialIntegrationService._scholarship_recipients(school)
        scholarship_data = {
            'active_scholarships': Scholarship.all_objects.filter(school=school, is_active=True).count() if school else Scholarship.objects.filter(is_active=True).count(),
            'total_recipients': scholarship_recipients.filter(status='active').count(),
            'total_awarded': scholarship_recipients.filter(
                status='active'
            ).aggregate(Sum('awarded_amount'))['awarded_amount__sum'] or 0
        }
        
        return {
            'fee_data': fee_data,
            'analytics_data': analytics_data,
            'notification_stats': notification_stats,
            'recent_audit_logs': recent_audit_logs,
            'reconciliation_status': reconciliation_status,
            'payroll_data': payroll_data,
            'scholarship_data': scholarship_data,
            'current_month': current_month
        }
    
    @staticmethod
    def process_payment_with_integration(payment_data, user, school=None):
        """
        Process payment with full integration: audit logging, notifications, reconciliation
        Requirements: 4.1-4.7, 7.1-7.7, 8.1-8.7, 11.1-11.7
        """
        try:
            # Create payment
            student_fee = FinancialIntegrationService._student_fees(school).get(id=payment_data['student_fee_id'])
            
            # Validate payment amount
            amount = float(payment_data['amount'])
            if amount > student_fee.balance_amount:
                raise ValueError(f"Payment amount exceeds outstanding balance")
            
            # Create payment record
            payment = FeePayment.all_objects.create(
                student_fee=student_fee,
                amount=amount,
                payment_method=payment_data['payment_method'],
                reference_number=payment_data.get('reference_number', ''),
                received_by=user,
                notes=payment_data.get('notes', '')
            )
            
            # Audit logging
            AuditLogger.log_payment(payment, user, 'create')
            
            # Send payment confirmation notification
            notification_service = NotificationService()
            notification_service.send_payment_confirmation(payment)
            
            # Trigger reconciliation check
            reconciliation_service = ReconciliationService()
            reconciliation_service.verify_payment_record(payment)
            
            return {
                'success': True,
                'payment': payment,
                'message': 'Payment processed successfully'
            }
            
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def create_fee_structure_with_integration(fee_data, user, school=None):
        """
        Create fee structure with full integration
        Requirements: 4.1-4.7, 7.1-7.7, 8.1-8.7
        """
        try:
            # Validate uniqueness
            existing = FeeStructure.all_objects.filter(
                school_class__school=school,
                school_class_id=fee_data['school_class_id'],
                term_id=fee_data['term_id']
            ).exists() if school else FeeStructure.objects.filter(
                school_class_id=fee_data['school_class_id'],
                term_id=fee_data['term_id']
            ).exists()
            
            if existing:
                raise ValueError("Fee structure already exists for this class and term")
            
            # Create fee structure
            fee_structure = FeeStructure.all_objects.create(**fee_data)
            
            # Create student fees for all students in the class
            from .staffing import active_students
            students = active_students(school).filter(school_class=fee_structure.school_class)
            created_count = 0
            
            for student in students:
                StudentFee.all_objects.get_or_create(
                    student=student,
                    fee_structure=fee_structure,
                    defaults={
                        'total_amount': fee_structure.total_fee,
                        'due_date': timezone.now().date() + timedelta(days=30)
                    }
                )
                created_count += 1
            
            # Audit logging
            AuditLogger.log_fee_structure(fee_structure, user, 'create')
            
            # Send notifications to parents
            notification_service = NotificationService()
            notification_service.send_bulk_fee_structure_notifications(fee_structure)
            
            return {
                'success': True,
                'fee_structure': fee_structure,
                'students_count': created_count,
                'message': f'Fee structure created for {created_count} students'
            }
            
        except Exception as e:
            logger.error(f"Fee structure creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def generate_payroll_with_integration(month, payroll_structure_id, user, school=None):
        """
        Generate payroll with full integration
        Requirements: 4.5, 7.1-7.7, 8.4, 11.2
        """
        try:
            payroll_structure = PayrollStructure.all_objects.get(id=payroll_structure_id, school=school) if school else PayrollStructure.objects.get(id=payroll_structure_id)
            from .staffing import active_staff
            teachers = active_staff(school)
            
            created_count = 0
            errors = []
            
            for teacher in teachers:
                try:
                    payroll, created = StaffPayroll.all_objects.get_or_create(
                        teacher=teacher,
                        month=month,
                        defaults={
                            'payroll_structure': payroll_structure,
                            'gross_salary': payroll_structure.gross_salary,
                            'net_salary': 0
                        }
                    )
                    
                    if created:
                        payroll.calculate_net_salary()
                        created_count += 1
                        
                        # Audit logging
                        AuditLogger.log_payroll(payroll, user, 'create')
                        
                except Exception as e:
                    errors.append(f"Teacher {teacher}: {str(e)}")
            
            # Send payroll notifications
            notification_service = NotificationService()
            notification_service.send_bulk_payroll_notifications(month)
            
            # Trigger reconciliation
            reconciliation_service = ReconciliationService()
            reconciliation_service.verify_payroll_calculations(month)
            
            return {
                'success': True,
                'created_count': created_count,
                'total_teachers': teachers.count(),
                'errors': errors,
                'message': f'Payroll generated for {created_count} staff members'
            }
            
        except Exception as e:
            logger.error(f"Payroll generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def award_scholarship_with_integration(scholarship_data, user, school=None):
        """
        Award scholarship with full integration
        Requirements: 4.4, 7.1-7.7, 8.3, 11.3
        """
        try:
            scholarship = Scholarship.all_objects.get(id=scholarship_data['scholarship_id'], school=school) if school else Scholarship.objects.get(id=scholarship_data['scholarship_id'])
            student = Student.all_objects.get(id=scholarship_data['student_id'], school=school) if school else Student.objects.get(id=scholarship_data['student_id'])
            
            # Check if student already has this scholarship
            existing = FinancialIntegrationService._scholarship_recipients(school).filter(
                scholarship=scholarship,
                student=student,
                status='active'
            ).exists()
            
            if existing:
                raise ValueError("Student already has this scholarship")
            
            # Check max recipients
            current_recipients = FinancialIntegrationService._scholarship_recipients(school).filter(
                scholarship=scholarship,
                status='active'
            ).count()
            
            if current_recipients >= scholarship.max_recipients:
                raise ValueError("Maximum recipients reached for this scholarship")
            
            # Create scholarship recipient
            recipient = ScholarshipRecipient.all_objects.create(
                scholarship=scholarship,
                student=student,
                awarded_amount=scholarship_data['awarded_amount'],
                start_date=scholarship_data.get('start_date', timezone.now().date()),
                end_date=scholarship_data.get('end_date'),
                status='active'
            )
            
            sync_scholarship_fee_applications(recipient)
            
            # Audit logging
            AuditLogger.log_scholarship(recipient, user, 'award')
            
            # Send scholarship award notification
            notification_service = NotificationService()
            notification_service.send_scholarship_award_notification(recipient)
            
            # Trigger reconciliation
            reconciliation_service = ReconciliationService()
            reconciliation_service.verify_scholarship_application(recipient)
            
            return {
                'success': True,
                'recipient': recipient,
                'message': 'Scholarship awarded successfully'
            }
            
        except Exception as e:
            logger.error(f"Scholarship award failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def export_financial_data_with_integration(export_params, user, school=None):
        """
        Export financial data with full integration
        Requirements: 10.1-10.7
        """
        try:
            export_service = ExportService()
            
            export_type = export_params['export_type']
            format_type = export_params['format']  # pdf, excel, csv
            
            # Get data based on export type
            if export_type == 'fee_collection':
                data = FinancialIntegrationService._student_fees(school).select_related(
                    'student__user', 'student__school_class', 'fee_structure'
                )
                
                if format_type == 'pdf':
                    result = export_service.export_fee_collection_pdf(data, export_params)
                elif format_type == 'excel':
                    result = export_service.export_fee_collection_excel(data, export_params)
                else:
                    result = export_service.export_fee_collection_csv(data, export_params)
            
            elif export_type == 'payroll':
                data = FinancialIntegrationService._payrolls(school).select_related(
                    'teacher__user', 'payroll_structure'
                ).filter(month=export_params.get('month'))
                
                if format_type == 'pdf':
                    result = export_service.export_payroll_pdf(data, export_params)
                elif format_type == 'excel':
                    result = export_service.export_payroll_excel(data, export_params)
                else:
                    result = export_service.export_payroll_csv(data, export_params)
            
            elif export_type == 'scholarship':
                data = FinancialIntegrationService._scholarship_recipients(school).select_related(
                    'student__user', 'scholarship'
                ).filter(status='active')
                
                if format_type == 'pdf':
                    result = export_service.export_scholarship_pdf(data, export_params)
                elif format_type == 'excel':
                    result = export_service.export_scholarship_excel(data, export_params)
                else:
                    result = export_service.export_scholarship_csv(data, export_params)
            
            else:
                raise ValueError(f"Unknown export type: {export_type}")
            
            # Audit logging
            AuditLogger.log_export(export_type, format_type, user)
            
            return {
                'success': True,
                'file_path': result['file_path'],
                'file_name': result['file_name'],
                'message': 'Export completed successfully'
            }
            
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Integrated View Functions

@login_required
def integrated_financial_dashboard(request):
    """
    Integrated financial dashboard with all components
    Requirements: All requirements - Comprehensive dashboard
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
        return redirect('core:dashboard')
    
    # Get integrated dashboard data
    dashboard_data = FinancialIntegrationService.get_integrated_dashboard_data(request.user, school=school)
    
    context = {
        **dashboard_data['fee_data'],
        'monthly_income': dashboard_data['fee_data']['total_fees_collected'],
        'monthly_expenses': 0,
        'monthly_payroll': dashboard_data['payroll_data']['monthly_payroll'],
        'net_income': dashboard_data['fee_data']['total_fees_collected'] - dashboard_data['payroll_data']['monthly_payroll'],
        'page_title': 'Financial Management Dashboard'
    }
    
    return render(request, 'financial/dashboard.html', context)


@login_required
def integrated_payment_processing(request):
    """
    Integrated payment processing with all features
    Requirements: 4.1-4.7, 7.1-7.7, 8.1-8.7, 11.1-11.7
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        payment_data = {
            'student_fee_id': request.POST.get('student_fee_id'),
            'amount': request.POST.get('amount'),
            'payment_method': request.POST.get('payment_method'),
            'reference_number': request.POST.get('reference_number', ''),
            'notes': request.POST.get('notes', '')
        }
        
        result = FinancialIntegrationService.process_payment_with_integration(
            payment_data, request.user, school=school
        )
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('fee_management')
        else:
            messages.error(request, result['error'])
    
    # Get student fees with filtering
    filter_mixin = StudentFeeFilterMixin()
    current_filters = filter_mixin.get_filter_state(request)
    
    student_fees = FinancialIntegrationService._student_fees(school).select_related(
        'student__user', 'fee_structure'
    ).exclude(status='paid')
    
    student_fees = filter_mixin.apply_filters(student_fees, current_filters)
    
    context = {
        'student_fees': student_fees,
        'filter_context': filter_mixin.get_filter_context(),
        'current_filters': current_filters,
        'page_title': 'Process Payment'
    }
    
    return render(request, 'financial/integrated_payment.html', context)


@login_required
def integrated_export_interface(request):
    """
    Integrated export interface with all formats and options
    Requirements: 10.1-10.7
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        export_params = {
            'export_type': request.POST.get('export_type'),
            'format': request.POST.get('format'),
            'date_from': request.POST.get('date_from'),
            'date_to': request.POST.get('date_to'),
            'include_charts': request.POST.get('include_charts') == 'on',
            'month': request.POST.get('month')
        }
        
        result = FinancialIntegrationService.export_financial_data_with_integration(
            export_params, request.user, school=school
        )
        
        if result['success']:
            # Return file for download
            from django.http import FileResponse
            import os
            
            file_path = result['file_path']
            if os.path.exists(file_path):
                response = FileResponse(open(file_path, 'rb'))
                response['Content-Disposition'] = f'attachment; filename="{result["file_name"]}"'
                return response
            else:
                messages.error(request, 'Export file not found')
        else:
            messages.error(request, result['error'])
    
    context = {
        'export_types': ['fee_collection', 'payroll', 'scholarship', 'transactions'],
        'formats': ['pdf', 'excel', 'csv'],
        'page_title': 'Export Financial Data'
    }
    
    return render(request, 'financial/integrated_export.html', context)


@login_required
def integrated_reconciliation_dashboard(request):
    """
    Integrated reconciliation dashboard
    Requirements: 11.1-11.7
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    reconciliation_service = ReconciliationService()
    
    # Get reconciliation summary
    summary = reconciliation_service.get_reconciliation_summary()
    
    # Get recent reconciliation runs
    recent_runs = reconciliation_service.get_recent_reconciliation_runs(limit=10)
    
    # Get discrepancies
    discrepancies = reconciliation_service.get_all_discrepancies()
    
    context = {
        'summary': summary,
        'recent_runs': recent_runs,
        'discrepancies': discrepancies,
        'page_title': 'Financial Reconciliation'
    }
    
    return render(request, 'financial/integrated_reconciliation.html', context)


@login_required
def run_manual_reconciliation(request):
    """
    Run manual reconciliation check
    Requirements: 11.1-11.7
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            reconciliation_service = ReconciliationService()
            
            # Run all reconciliation checks
            results = reconciliation_service.run_all_reconciliation_checks()
            
            # Audit logging
            AuditLogger.log_reconciliation(results, request.user)
            
            return JsonResponse({
                'success': True,
                'results': results,
                'message': 'Reconciliation completed successfully'
            })
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


