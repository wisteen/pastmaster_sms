"""
Views for Bulk Operations with Error Handling and Progress Tracking

This module provides web views for handling bulk financial operations
with comprehensive error reporting, progress tracking, and user feedback.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
import json
import csv
import io
import uuid
from datetime import datetime
from decimal import Decimal

from .services_bulk import (
    BulkOperationService, BulkOperationResult, 
    create_progress_tracker, get_progress_tracker, remove_progress_tracker
)
from .bulk_error_handling import (
    BulkOperationValidator, ValidationErrorCollector, BulkOperationReporter,
    log_bulk_operation_start, log_bulk_operation_end
)
from .models import FeeStructure, StudentFee, PayrollStructure, Teacher, SchoolClass, Term


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('core.add_feestructure', raise_exception=True), name='dispatch')
class BulkOperationsView(TemplateView):
    """Main view for bulk operations interface"""
    template_name = 'financial/bulk/operations.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'school_classes': SchoolClass.objects.all(),
            'terms': Term.objects.all(),
            'payroll_structures': PayrollStructure.objects.filter(is_active=True),
            'teachers': Teacher.objects.all().select_related('user'),
        })
        return context


@login_required
@permission_required('core.add_feestructure', raise_exception=True)
@require_http_methods(["POST"])
def bulk_create_fee_structures(request):
    """Handle bulk fee structure creation"""
    try:
        # Parse the uploaded data
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']
            fee_data_list = parse_fee_structure_csv(csv_file)
        elif 'json_data' in request.POST:
            fee_data_list = json.loads(request.POST['json_data'])
        else:
            return JsonResponse({
                'success': False,
                'error': 'No data provided. Please upload a CSV file or provide JSON data.'
            })
        
        # Create operation ID for progress tracking
        operation_id = str(uuid.uuid4())
        
        # Validate data before processing
        validation_errors = BulkOperationValidator.validate_fee_structure_data(fee_data_list)
        
        if validation_errors.has_errors():
            return JsonResponse({
                'success': False,
                'operation_id': operation_id,
                'validation_errors': validation_errors.to_dict(),
                'error': 'Validation errors found. Please correct the data and try again.'
            })
        
        # Create progress tracker
        tracker = create_progress_tracker(operation_id, len(fee_data_list))
        
        # Log operation start
        log_bulk_operation_start('bulk_create_fee_structures', len(fee_data_list), request.user)
        
        # Process the bulk operation
        result = BulkOperationService.bulk_create_fee_structures_with_progress(
            fee_data_list, request.user, tracker
        )
        
        # Complete progress tracking
        tracker.complete('completed' if result.error_count == 0 else 'completed_with_errors')
        
        # Log operation end
        log_bulk_operation_end('bulk_create_fee_structures', result, request.user)
        
        # Generate detailed report
        report = BulkOperationReporter.generate_detailed_report(
            'bulk_create_fee_structures', result, validation_errors
        )
        
        # Store report for later retrieval (in production, use database or cache)
        request.session[f'bulk_report_{operation_id}'] = report
        
        return JsonResponse({
            'success': result.error_count == 0,
            'operation_id': operation_id,
            'summary': result.get_summary(),
            'report_url': f'/financial/bulk/report/{operation_id}/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })


@login_required
@permission_required('core.add_feepayment', raise_exception=True)
@require_http_methods(["POST"])
def bulk_process_payments(request):
    """Handle bulk payment processing"""
    try:
        # Parse the uploaded data
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']
            payment_data_list = parse_payment_csv(csv_file)
        elif 'json_data' in request.POST:
            payment_data_list = json.loads(request.POST['json_data'])
        else:
            return JsonResponse({
                'success': False,
                'error': 'No data provided. Please upload a CSV file or provide JSON data.'
            })
        
        # Create operation ID for progress tracking
        operation_id = str(uuid.uuid4())
        
        # Validate data before processing
        validation_errors = BulkOperationValidator.validate_payment_data(payment_data_list)
        
        if validation_errors.has_errors():
            return JsonResponse({
                'success': False,
                'operation_id': operation_id,
                'validation_errors': validation_errors.to_dict(),
                'error': 'Validation errors found. Please correct the data and try again.'
            })
        
        # Create progress tracker
        tracker = create_progress_tracker(operation_id, len(payment_data_list))
        
        # Log operation start
        log_bulk_operation_start('bulk_process_payments', len(payment_data_list), request.user)
        
        # Process the bulk operation
        result = BulkOperationService.bulk_process_payments(payment_data_list, request.user)
        
        # Complete progress tracking
        tracker.complete('completed' if result.error_count == 0 else 'completed_with_errors')
        
        # Log operation end
        log_bulk_operation_end('bulk_process_payments', result, request.user)
        
        # Generate detailed report
        report = BulkOperationReporter.generate_detailed_report(
            'bulk_process_payments', result, validation_errors
        )
        
        # Store report for later retrieval
        request.session[f'bulk_report_{operation_id}'] = report
        
        return JsonResponse({
            'success': result.error_count == 0,
            'operation_id': operation_id,
            'summary': result.get_summary(),
            'report_url': f'/financial/bulk/report/{operation_id}/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })


@login_required
@permission_required('core.add_staffpayroll', raise_exception=True)
@require_http_methods(["POST"])
def bulk_generate_payroll(request):
    """Handle bulk payroll generation"""
    try:
        # Parse request data
        month_str = request.POST.get('month')
        payroll_structure_id = request.POST.get('payroll_structure_id')
        teacher_ids_str = request.POST.get('teacher_ids', '')
        
        # Parse month
        try:
            month = datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
        except (ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid month format. Please use YYYY-MM format.'
            })
        
        # Parse teacher IDs
        teacher_ids = None
        if teacher_ids_str:
            try:
                teacher_ids = [int(id.strip()) for id in teacher_ids_str.split(',') if id.strip()]
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid teacher IDs format.'
                })
        
        # Create operation ID for progress tracking
        operation_id = str(uuid.uuid4())
        
        # Validate data before processing
        validation_errors = BulkOperationValidator.validate_payroll_data(
            month, payroll_structure_id, teacher_ids
        )
        
        if validation_errors.has_errors():
            return JsonResponse({
                'success': False,
                'operation_id': operation_id,
                'validation_errors': validation_errors.to_dict(),
                'error': 'Validation errors found. Please correct the parameters and try again.'
            })
        
        # Determine total items for progress tracking
        if teacher_ids:
            total_items = len(teacher_ids)
        else:
            total_items = Teacher.objects.count()
        
        # Create progress tracker
        tracker = create_progress_tracker(operation_id, total_items)
        
        # Log operation start
        log_bulk_operation_start('bulk_generate_payroll', total_items, request.user)
        
        # Process the bulk operation
        result = BulkOperationService.bulk_generate_payroll(
            month, payroll_structure_id, teacher_ids
        )
        
        # Complete progress tracking
        tracker.complete('completed' if result.error_count == 0 else 'completed_with_errors')
        
        # Log operation end
        log_bulk_operation_end('bulk_generate_payroll', result, request.user)
        
        # Generate detailed report
        report = BulkOperationReporter.generate_detailed_report(
            'bulk_generate_payroll', result, validation_errors
        )
        
        # Store report for later retrieval
        request.session[f'bulk_report_{operation_id}'] = report
        
        return JsonResponse({
            'success': result.error_count == 0,
            'operation_id': operation_id,
            'summary': result.get_summary(),
            'report_url': f'/financial/bulk/report/{operation_id}/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def bulk_operation_progress(request, operation_id):
    """Get progress status for a bulk operation"""
    try:
        tracker = get_progress_tracker(operation_id)
        if not tracker:
            return JsonResponse({
                'success': False,
                'error': 'Operation not found or expired.'
            })
        
        return JsonResponse({
            'success': True,
            'progress': tracker.to_dict()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error retrieving progress: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def bulk_operation_report(request, operation_id):
    """Display detailed report for a bulk operation"""
    try:
        # Retrieve report from session (in production, use database or cache)
        report = request.session.get(f'bulk_report_{operation_id}')
        if not report:
            messages.error(request, 'Report not found or expired.')
            return redirect('financial:bulk_operations')
        
        # Format report for display
        formatted_report = BulkOperationReporter.format_report_for_display(report)
        
        context = {
            'operation_id': operation_id,
            'report': report,
            'formatted_report': formatted_report,
            'can_download': True
        }
        
        return render(request, 'financial/bulk/report.html', context)
        
    except Exception as e:
        messages.error(request, f'Error displaying report: {str(e)}')
        return redirect('financial:bulk_operations')


@login_required
@require_http_methods(["GET"])
def download_bulk_report(request, operation_id):
    """Download bulk operation report as JSON"""
    try:
        # Retrieve report from session
        report = request.session.get(f'bulk_report_{operation_id}')
        if not report:
            return JsonResponse({
                'success': False,
                'error': 'Report not found or expired.'
            })
        
        # Create JSON response
        response = HttpResponse(
            json.dumps(report, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="bulk_report_{operation_id}.json"'
        
        return response
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error downloading report: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def cancel_bulk_operation(request, operation_id):
    """Cancel a running bulk operation"""
    try:
        tracker = get_progress_tracker(operation_id)
        if not tracker:
            return JsonResponse({
                'success': False,
                'error': 'Operation not found or already completed.'
            })
        
        if tracker.status == 'running':
            tracker.complete('cancelled')
            return JsonResponse({
                'success': True,
                'message': 'Operation cancelled successfully.'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Cannot cancel operation with status: {tracker.status}'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error cancelling operation: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def cleanup_bulk_operation(request, operation_id):
    """Clean up resources for a completed bulk operation"""
    try:
        # Remove progress tracker
        remove_progress_tracker(operation_id)
        
        # Remove report from session
        session_key = f'bulk_report_{operation_id}'
        if session_key in request.session:
            del request.session[session_key]
        
        return JsonResponse({
            'success': True,
            'message': 'Operation resources cleaned up successfully.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error cleaning up operation: {str(e)}'
        })


# Utility functions for parsing CSV data

def parse_fee_structure_csv(csv_file):
    """Parse fee structure data from CSV file"""
    fee_data_list = []
    
    try:
        # Read CSV content
        content = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        
        for row in csv_reader:
            # Convert monetary fields to Decimal
            monetary_fields = ['tuition_fee', 'development_fee', 'exam_fee', 
                             'library_fee', 'sports_fee', 'other_fees']
            
            fee_data = {}
            for key, value in row.items():
                if key in monetary_fields and value:
                    try:
                        fee_data[key] = Decimal(str(value))
                    except (ValueError, TypeError):
                        fee_data[key] = Decimal('0.00')
                else:
                    fee_data[key] = value.strip() if value else ''
            
            fee_data_list.append(fee_data)
            
    except Exception as e:
        raise ValidationError(f'Error parsing CSV file: {str(e)}')
    
    return fee_data_list


def parse_payment_csv(csv_file):
    """Parse payment data from CSV file"""
    payment_data_list = []
    
    try:
        # Read CSV content
        content = csv_file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(content))
        
        for row in csv_reader:
            payment_data = {}
            for key, value in row.items():
                if key == 'amount' and value:
                    try:
                        payment_data[key] = Decimal(str(value))
                    except (ValueError, TypeError):
                        payment_data[key] = Decimal('0.00')
                elif key == 'student_fee' and value:
                    try:
                        payment_data[key] = int(value)
                    except (ValueError, TypeError):
                        payment_data[key] = None
                else:
                    payment_data[key] = value.strip() if value else ''
            
            payment_data_list.append(payment_data)
            
    except Exception as e:
        raise ValidationError(f'Error parsing CSV file: {str(e)}')
    
    return payment_data_list