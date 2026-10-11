from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Sum, Count, Q, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import json
from .models import *
from .filters_financial import (
    StudentFeeFilterMixin, FeePaymentFilterMixin, ScholarshipFilterMixin,
    StaffPayrollFilterMixin, FinancialTransactionFilterMixin, FilterStatePersistence
)
from .services_analytics import FinancialAnalyticsService
from .services_audit import AuditLogSearchService
from .services_notification import NotificationService
from .services_notification_tracking import NotificationTrackingService
from .services_reports import ReportService
from .services_financial_integrity import (
    clear_scholarship_fee_applications,
    sync_active_scholarships_for_student,
    sync_scholarship_fee_applications,
)
from .services_report_customization import ReportCustomizationService, ScheduledReport, ReportExecution
from .academic_choices import existing_session_choices
from .staffing import active_staff, active_students

from .decorators import role_required
from .decorators_features import feature_required
from .forms_financial import (
    InventoryCategoryForm,
    InventorySupplierForm,
    InventoryItemForm,
    InventoryStockMovementForm,
)


def _financial_school_or_redirect(request):
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
    return school


def _school_student_fees(school):
    return StudentFee.all_objects.filter(student_id__in=active_students(school).values_list('pk', flat=True))


def _school_fee_structures(school):
    return FeeStructure.all_objects.filter(school_class__school=school)


def _school_fee_payments(school):
    return FeePayment.all_objects.filter(student_fee__student_id__in=active_students(school).values_list('pk', flat=True))


def _school_payrolls(school):
    return StaffPayroll.all_objects.filter(teacher_id__in=active_staff(school).values_list('pk', flat=True))


def _school_scholarship_recipients(school):
    return ScholarshipRecipient.all_objects.filter(student_id__in=active_students(school).values_list('pk', flat=True))


@login_required
@role_required(['super_admin', 'accountant', 'bursar'])
@feature_required('financial_management')
def financial_dashboard(request):
    """Main financial dashboard"""
    # Access already checked by decorator
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    # Financial summary
    current_month = timezone.now().date().replace(day=1)
    student_fees = _school_student_fees(school)
    
    # Fee collection summary
    total_fees_due = student_fees.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_fees_collected = student_fees.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
    total_discounts = student_fees.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0
    pending_fees = total_fees_due - total_fees_collected - total_discounts
    
    # Monthly revenue/expenses
    monthly_income = FinancialTransaction.all_objects.filter(
        school=school,
        transaction_type='income',
        transaction_date__gte=current_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    monthly_expenses = FinancialTransaction.all_objects.filter(
        school=school,
        transaction_type='expense',
        transaction_date__gte=current_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Payroll summary
    monthly_payroll = _school_payrolls(school).filter(
        month=current_month
    ).aggregate(Sum('net_salary'))['net_salary__sum'] or 0
    
    # Calculate collection rate
    collection_rate = (total_fees_collected * 100 / total_fees_due) if total_fees_due > 0 else 0
    
    context = {
        'total_fees_due': total_fees_due,
        'total_fees_collected': total_fees_collected,
        'total_discounts': total_discounts,
        'pending_fees': pending_fees,
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'monthly_payroll': monthly_payroll,
        'net_income': monthly_income - monthly_expenses,
        'collection_rate': collection_rate,
    }
    
    return render(request, 'financial/dashboard.html', context)


@login_required
@role_required(['super_admin', 'accountant', 'bursar'])
@feature_required('financial_management')
def inventory_management(request):
    school = getattr(request, 'school', None)
    if not school:
        messages.error(request, 'Select a school first.')
        return redirect('core:dashboard')

    editing_item = None
    category_form = InventoryCategoryForm(prefix='category')
    supplier_form = InventorySupplierForm(prefix='supplier')
    item_form = InventoryItemForm(prefix='item', school=school)
    movement_form = InventoryStockMovementForm(prefix='movement', school=school)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_category':
            category_form = InventoryCategoryForm(request.POST, prefix='category')
            if category_form.is_valid():
                category = category_form.save(commit=False)
                category.school = school
                try:
                    category.save()
                    messages.success(request, 'Inventory category saved successfully.')
                    return redirect('financial:inventory_management')
                except IntegrityError:
                    category_form.add_error('name', 'A category with this name already exists.')

        elif action == 'save_supplier':
            supplier_form = InventorySupplierForm(request.POST, prefix='supplier')
            if supplier_form.is_valid():
                supplier = supplier_form.save(commit=False)
                supplier.school = school
                try:
                    supplier.save()
                    messages.success(request, 'Supplier saved successfully.')
                    return redirect('financial:inventory_management')
                except IntegrityError:
                    supplier_form.add_error('name', 'A supplier with this name already exists.')

        elif action == 'save_item':
            item_id = request.POST.get('item_id')
            editing_item = InventoryItem.all_objects.filter(id=item_id, school=school).first() if item_id else None
            if item_id and not editing_item:
                messages.error(request, 'That inventory item is not managed under this school.')
                return redirect('financial:inventory_management')

            item_form = InventoryItemForm(request.POST, prefix='item', school=school, instance=editing_item)
            if item_form.is_valid():
                item = item_form.save(commit=False)
                item.school = school
                item.save()
                messages.success(request, 'Inventory item saved successfully.')
                return redirect('financial:inventory_management')

        elif action == 'delete_item':
            item = InventoryItem.all_objects.filter(id=request.POST.get('item_id'), school=school).first()
            if not item:
                messages.error(request, 'That inventory item is not managed under this school.')
            else:
                item.delete()
                messages.success(request, 'Inventory item deleted successfully.')
            return redirect('financial:inventory_management')

        elif action == 'save_movement':
            movement_form = InventoryStockMovementForm(request.POST, prefix='movement', school=school)
            if movement_form.is_valid():
                movement = movement_form.save(commit=False)
                movement.school = school
                movement.created_by = request.user
                try:
                    movement.save()
                    messages.success(request, 'Stock movement recorded successfully.')
                    return redirect('financial:inventory_management')
                except ValidationError as exc:
                    movement_form.add_error(None, exc)

    else:
        item_id = request.GET.get('item')
        if item_id:
            editing_item = InventoryItem.all_objects.filter(id=item_id, school=school).first()
            if not editing_item:
                messages.error(request, 'That inventory item is not managed under this school.')
                return redirect('financial:inventory_management')
            item_form = InventoryItemForm(prefix='item', school=school, instance=editing_item)

    items = InventoryItem.all_objects.filter(school=school).select_related('category', 'supplier')
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    category_id = request.GET.get('category', '').strip()

    if search:
        items = items.filter(
            Q(name__icontains=search) |
            Q(sku__icontains=search) |
            Q(location__icontains=search) |
            Q(category__name__icontains=search) |
            Q(supplier__name__icontains=search)
        )
    if status:
        items = items.filter(status=status)
    if category_id:
        items = items.filter(category_id=category_id)

    paginator = Paginator(items.order_by('name'), 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    inventory_summary = InventoryItem.all_objects.filter(school=school).aggregate(
        total_items=Count('id'),
        total_quantity=Sum('quantity_on_hand'),
        total_stock_value=Sum(ExpressionWrapper(
            F('quantity_on_hand') * F('unit_cost'),
            output_field=DecimalField(max_digits=22, decimal_places=4),
        )),
    )
    low_stock_count = sum(1 for item in InventoryItem.all_objects.filter(school=school) if item.needs_reorder)
    recent_movements = InventoryStockMovement.all_objects.filter(
        school=school,
    ).select_related('item', 'created_by').order_by('-created_at')[:10]

    return render(request, 'financial/inventory_management.html', {
        'category_form': category_form,
        'supplier_form': supplier_form,
        'item_form': item_form,
        'movement_form': movement_form,
        'editing_item': editing_item,
        'items': page_obj,
        'categories': InventoryCategory.all_objects.filter(school=school).order_by('name'),
        'suppliers': InventorySupplier.all_objects.filter(school=school).order_by('name'),
        'recent_movements': recent_movements,
        'search': search,
        'status': status,
        'category_id': category_id,
        'total_items': inventory_summary['total_items'] or 0,
        'total_quantity': inventory_summary['total_quantity'] or 0,
        'total_stock_value': inventory_summary['total_stock_value'] or 0,
        'low_stock_count': low_stock_count,
    })

@login_required
def fee_management(request):
    """Fee structure and payment management with advanced filtering"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    # Initialize filter mixin
    filter_mixin = StudentFeeFilterMixin()
    
    # Get current filters from request
    current_filters = filter_mixin.get_filter_state(request)
    
    # Load saved filters from session if no current filters
    if not any(current_filters.values()):
        saved_filters = FilterStatePersistence.load_filter_state(request, 'fee_management')
        current_filters = FilterStatePersistence.merge_filters(saved_filters, current_filters)
    
    # Save current filters to session
    FilterStatePersistence.save_filter_state(request, 'fee_management', current_filters)
    
    # Get base queryset
    student_fees = _school_student_fees(school).select_related(
        'student__user', 'student__school_class', 'fee_structure__term'
    ).prefetch_related('payments').order_by('student__user__last_name', 'student__user__first_name', 'id')
    
    # Apply filters
    student_fees = filter_mixin.apply_filters(student_fees, current_filters)
    
    # Get fee structures
    fee_structures = _school_fee_structures(school).filter(is_active=True)
    recent_payments = _school_fee_payments(school).select_related(
        'student_fee__student__user'
    ).order_by('-payment_date')[:10]
    
    # Payment statistics (filtered)
    total_students = student_fees.count()
    paid_students = student_fees.filter(status='paid').count()
    pending_students = student_fees.filter(status='pending').count()
    overdue_students = student_fees.filter(status='overdue').count()
    partial_students = student_fees.filter(status='partial').count()
    
    # Financial summary (filtered)
    financial_summary = student_fees.aggregate(
        total_fees=Sum('total_amount'),
        total_paid=Sum('paid_amount'),
        total_discount=Sum('discount_amount')
    )
    
    total_fees = financial_summary['total_fees'] or 0
    total_paid = financial_summary['total_paid'] or 0
    total_discount = financial_summary['total_discount'] or 0
    outstanding_balance = total_fees - total_paid - total_discount
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(student_fees, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'fee_structures': fee_structures,
        'recent_payments': recent_payments,
        'student_fees': page_obj,
        'total_students': total_students,
        'paid_students': paid_students,
        'pending_students': pending_students,
        'overdue_students': overdue_students,
        'partial_students': partial_students,
        'total_fees': total_fees,
        'total_paid': total_paid,
        'total_discount': total_discount,
        'outstanding_balance': outstanding_balance,
        'collection_rate': (total_paid * 100 / total_fees) if total_fees > 0 else 0,
        # Filter context
        'filter_context': filter_mixin.get_filter_context(),
        'current_filters': current_filters,
        'has_filters': any(current_filters.values()),
    }
    
    return render(request, 'financial/fee_management.html', context)

@login_required
def create_fee_structure(request):
    """Create new fee structure"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')

    classes = SchoolClass.all_objects.filter(school=school).order_by('name')
    terms = Term.all_objects.filter(school=school).order_by('-start_date', 'name')
    
    if request.method == 'POST':
        # Helper function to safely convert to decimal
        def safe_decimal(value, default=0):
            try:
                return float(value) if value else default
            except (ValueError, TypeError):
                return default
        
        school_class_id = request.POST.get('school_class')
        term_id = request.POST.get('term')
        school_class = get_object_or_404(SchoolClass.all_objects.filter(school=school), id=school_class_id)
        term = get_object_or_404(Term.all_objects.filter(school=school), id=term_id)
        
        # Check if fee structure already exists
        existing_fee = _school_fee_structures(school).filter(
            school_class=school_class,
            term=term
        ).first()
        
        if existing_fee:
            messages.error(request, 'Fee structure already exists for this class and term')
            return render(request, 'financial/create_fee_structure.html', {'classes': classes, 'terms': terms})
        
        fee_structure = FeeStructure.all_objects.create(
            name=request.POST.get('name'),
            school_class=school_class,
            term=term,
            tuition_fee=safe_decimal(request.POST.get('tuition_fee')),
            development_fee=safe_decimal(request.POST.get('development_fee')),
            exam_fee=safe_decimal(request.POST.get('exam_fee')),
            library_fee=safe_decimal(request.POST.get('library_fee')),
            sports_fee=safe_decimal(request.POST.get('sports_fee')),
            other_fees=safe_decimal(request.POST.get('other_fees')),
        )
        
        # Create student fees for all students in the class
        students = active_students(school).filter(school_class=fee_structure.school_class)
        for student in students:
            StudentFee.all_objects.get_or_create(
                student=student,
                fee_structure=fee_structure,
                defaults={
                    'total_amount': fee_structure.total_fee,
                    'due_date': timezone.now().date() + timedelta(days=30)
                }
            )
            sync_active_scholarships_for_student(student)
        
        messages.success(request, f'Fee structure created for {students.count()} students')
        return redirect('financial:fee_management')
    
    return render(request, 'financial/create_fee_structure.html', {'classes': classes, 'terms': terms})

@login_required
def record_payment(request):
    """Record fee payment"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        student_fee = get_object_or_404(_school_student_fees(school), id=request.POST.get('student_fee_id'))
        try:
            payment_amount = Decimal(request.POST.get('amount'))
        except (ArithmeticError, TypeError):
            messages.error(request, 'Enter a valid payment amount.')
            return redirect('financial:record_payment')
        if payment_amount <= 0:
            messages.error(request, 'Payment amount must be greater than zero.')
            return redirect('financial:record_payment')
        if payment_amount > student_fee.balance_amount:
            messages.error(request, f'Payment cannot exceed the outstanding balance of {student_fee.balance_amount}.')
            return redirect('financial:record_payment')

        FeePayment.all_objects.create(
            student_fee=student_fee,
            amount=payment_amount,
            payment_method=request.POST.get('payment_method'),
            reference_number=request.POST.get('reference_number', ''),
            received_by=request.user,
            notes=request.POST.get('notes', '')
        )
        
        messages.success(request, 'Payment recorded successfully')
        return redirect('financial:fee_management')
    
    student_fees = _school_student_fees(school).select_related('student__user', 'fee_structure').exclude(status='paid')
    
    # If no student fees exist, show a helpful message
    if not student_fees.exists():
        messages.info(request, 'No student fees found. Please create fee structures first.')
    
    return render(request, 'financial/record_payment.html', {'student_fees': student_fees})

@login_required
def scholarship_management(request):
    """Scholarship management"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    scholarships = Scholarship.all_objects.filter(school=school, is_active=True)
    recipients = _school_scholarship_recipients(school).select_related('student__user', 'scholarship')
    active_recipients = recipients.filter(status='active')
    unapplied_recipients = active_recipients.filter(fee_applications__isnull=True).distinct()
    
    context = {
        'scholarships': scholarships,
        'recipients': recipients,
        'total_scholarships': scholarships.count(),
        'total_recipients': active_recipients.count(),
        'total_amount': active_recipients.aggregate(Sum('awarded_amount'))['awarded_amount__sum'] or 0,
        'unapplied_recipients': unapplied_recipients,
    }
    
    return render(request, 'financial/scholarship_management.html', context)

@login_required
def create_scholarship(request):
    """Create new scholarship"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    sessions = existing_session_choices(school=school)
    if request.method == 'POST':
        try:
            academic_year = request.POST.get('academic_year')
            if academic_year not in dict(sessions):
                raise ValidationError('Select an academic session configured under school terms.')
            Scholarship.all_objects.create(
                school=school,
                name=request.POST.get('name'),
                scholarship_type=request.POST.get('scholarship_type'),
                description=request.POST.get('description', ''),
                amount=request.POST.get('amount') or 0,
                percentage=request.POST.get('percentage') or None,
                max_recipients=request.POST.get('max_recipients', 1),
                academic_year=academic_year,
            )
        except (ValidationError, ValueError) as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Scholarship created successfully')
            return redirect('financial:scholarship_management')
    
    return render(request, 'financial/create_scholarship.html', {'sessions': sessions})

@login_required
def payroll_management(request):
    """Staff payroll management"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = getattr(request, 'school', None)
    if not school and not request.user.is_superuser:
        messages.error(request, 'Select a school first.')
        return redirect('core:dashboard')
    
    # Get selected month from query params or default to current month
    selected_month_str = request.GET.get('month')
    if selected_month_str:
        selected_month = datetime.strptime(selected_month_str, '%Y-%m').date().replace(day=1)
    else:
        selected_month = timezone.now().date().replace(day=1)
    
    payroll_structures = PayrollStructure.all_objects.filter(school=school, is_active=True)
    current_payrolls = _school_payrolls(school).filter(month=selected_month).select_related('teacher__user', 'payroll_structure')
    
    # Payroll statistics
    from .staffing import active_staff
    eligible_staff = active_staff(school)
    total_staff = eligible_staff.count()
    processed_payrolls = current_payrolls.count()
    total_payroll_amount = current_payrolls.aggregate(Sum('net_salary'))['net_salary__sum'] or 0
    paid_payrolls = current_payrolls.filter(is_paid=True).count()
    unpaid_payrolls = current_payrolls.filter(is_paid=False).count()
    
    # Staff without payroll this month
    staff_with_payroll = current_payrolls.values_list('teacher_id', flat=True)
    staff_without_payroll = eligible_staff.exclude(id__in=staff_with_payroll).select_related('user')
    
    context = {
        'payroll_structures': payroll_structures,
        'current_payrolls': current_payrolls,
        'current_month': selected_month,
        'selected_month': selected_month,
        'total_staff': total_staff,
        'processed_payrolls': processed_payrolls,
        'total_payroll_amount': total_payroll_amount,
        'paid_payrolls': paid_payrolls,
        'unpaid_payrolls': unpaid_payrolls,
        'staff_without_payroll': staff_without_payroll,
    }
    
    return render(request, 'financial/payroll_management.html', context)

@login_required
def create_payroll_structure(request):
    """Create payroll structure"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        
        def safe_decimal(value):
            if not value or value.strip() == '':
                return Decimal('0')
            try:
                return Decimal(value.replace(',', ''))
            except (InvalidOperation, ValueError, AttributeError):
                return Decimal('0')
        
        PayrollStructure.all_objects.create(
            school=school,
            name=request.POST.get('name', ''),
            basic_salary=safe_decimal(request.POST.get('basic_salary', '0')),
            house_allowance=safe_decimal(request.POST.get('house_allowance', '0')),
            transport_allowance=safe_decimal(request.POST.get('transport_allowance', '0')),
            medical_allowance=safe_decimal(request.POST.get('medical_allowance', '0')),
            other_allowances=safe_decimal(request.POST.get('other_allowances', '0')),
            tax_rate=safe_decimal(request.POST.get('tax_rate', '0')),
            pension_rate=safe_decimal(request.POST.get('pension_rate', '0'))
        )
        messages.success(request, 'Payroll structure created successfully')
        return redirect('financial:payroll_management')
    
    return render(request, 'financial/create_payroll_structure.html')

@login_required
def generate_payroll(request):
    """Generate monthly payroll"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        month = datetime.strptime(request.POST.get('month'), '%Y-%m').date().replace(day=1)
        payroll_structure_id = request.POST.get('payroll_structure')
        teacher_ids = request.POST.getlist('teachers')
        
        payroll_structure = get_object_or_404(PayrollStructure.all_objects.filter(school=school), id=payroll_structure_id)
        
        if teacher_ids:
            from .staffing import active_staff
            teachers = active_staff(school).filter(id__in=teacher_ids)
        else:
            from .staffing import active_staff
            teachers = active_staff(school)
        
        created_count = 0
        skipped_count = 0
        
        for teacher in teachers:
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
            else:
                skipped_count += 1
        
        messages.success(request, f'Payroll generated for {created_count} staff. {skipped_count} already existed.')
        return redirect('financial:payroll_management')
    
    payroll_structures = PayrollStructure.all_objects.filter(school=school, is_active=True)
    from .staffing import active_staff
    teachers = active_staff(school).select_related('user')
    
    return render(request, 'financial/generate_payroll.html', {
        'payroll_structures': payroll_structures,
        'teachers': teachers,
        'current_month': timezone.now().date()
    })

@login_required
def financial_reports(request):
    """Financial reports and analytics"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    # Date range filter
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        start_date = timezone.now().date().replace(day=1)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Revenue analysis
    fee_income = _school_fee_payments(school).filter(
        payment_date__date__range=[start_date, end_date]
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    other_income = FinancialTransaction.all_objects.filter(
        school=school,
        transaction_type='income',
        transaction_date__range=[start_date, end_date]
    ).exclude(category='fees').aggregate(Sum('amount'))['amount__sum'] or 0
    
    total_income = fee_income + other_income
    
    # Expense analysis
    salary_expenses = _school_payrolls(school).filter(
        month__range=[start_date, end_date],
        is_paid=True
    ).aggregate(Sum('net_salary'))['net_salary__sum'] or 0
    
    other_expenses = FinancialTransaction.all_objects.filter(
        school=school,
        transaction_type='expense',
        transaction_date__range=[start_date, end_date]
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    total_expenses = salary_expenses + other_expenses
    
    # Outstanding fees
    outstanding_fees = _school_student_fees(school).filter(
        status__in=['pending', 'partial', 'overdue']
    ).aggregate(
        total=Sum('total_amount') - Sum('paid_amount') - Sum('discount_amount')
    )['total'] or 0
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'fee_income': fee_income,
        'other_income': other_income,
        'total_income': total_income,
        'salary_expenses': salary_expenses,
        'other_expenses': other_expenses,
        'total_expenses': total_expenses,
        'net_profit': total_income - total_expenses,
        'outstanding_fees': outstanding_fees,
    }
    
    return render(request, 'financial/reports.html', context)

@login_required
def export_financial_report(request):
    """Export financial report as CSV"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="financial_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Financial Report'])
    writer.writerow(['Generated on:', timezone.now().strftime('%Y-%m-%d %H:%M')])
    writer.writerow([])
    
    # Fee collection summary
    writer.writerow(['Fee Collection Summary'])
    writer.writerow(['Student', 'Class', 'Total Fee', 'Paid Amount', 'Balance', 'Status'])
    
    student_fees = _school_student_fees(school).select_related('student__user', 'student__school_class')
    for fee in student_fees:
        writer.writerow([
            fee.student.user.get_full_name(),
            fee.student.school_class.name,
            fee.total_amount,
            fee.paid_amount,
            fee.balance_amount,
            fee.get_status_display()
        ])
    
    return response

# Enhanced Class-Based Views with Filtering

class StudentFeeListView(LoginRequiredMixin, StudentFeeFilterMixin, ListView):
    """Enhanced student fee listing with advanced filtering"""
    model = StudentFee
    template_name = 'financial/student_fee_list.html'
    context_object_name = 'student_fees'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        school = getattr(self.request, 'school', None)
        queryset = _school_student_fees(school).select_related(
            'student__user', 'student__school_class', 'fee_structure__term'
        ).prefetch_related('payments') if school else StudentFee.objects.none()
        
        # Get current filters
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'student_fee_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Save current filters
        FilterStatePersistence.save_filter_state(
            self.request, 'student_fee_list', current_filters
        )
        
        # Apply filters
        return self.apply_filters(queryset, current_filters)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'student_fee_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Add filter context
        context.update({
            'filter_context': self.get_filter_context(),
            'current_filters': current_filters,
            'has_filters': any(current_filters.values()),
        })
        
        # Add summary statistics
        queryset = self.get_queryset()
        context.update({
            'total_count': queryset.count(),
            'paid_count': queryset.filter(status='paid').count(),
            'pending_count': queryset.filter(status='pending').count(),
            'overdue_count': queryset.filter(status='overdue').count(),
            'partial_count': queryset.filter(status='partial').count(),
        })
        
        # Financial summary
        financial_summary = queryset.aggregate(
            total_fees=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
            total_discount=Sum('discount_amount')
        )
        
        total_fees = financial_summary['total_fees'] or 0
        total_paid = financial_summary['total_paid'] or 0
        
        context.update({
            'total_fees': total_fees,
            'total_paid': total_paid,
            'outstanding_balance': total_fees - total_paid,
            'collection_rate': (total_paid * 100 / total_fees) if total_fees > 0 else 0,
        })
        
        return context


class FeePaymentListView(LoginRequiredMixin, FeePaymentFilterMixin, ListView):
    """Enhanced fee payment listing with advanced filtering"""
    model = FeePayment
    template_name = 'financial/fee_payment_list.html'
    context_object_name = 'payments'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        school = getattr(self.request, 'school', None)
        queryset = _school_fee_payments(school).select_related(
            'student_fee__student__user',
            'student_fee__student__school_class',
            'student_fee__fee_structure__term',
            'received_by'
        ).order_by('-payment_date') if school else FeePayment.objects.none()
        
        # Get current filters
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'fee_payment_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Save current filters
        FilterStatePersistence.save_filter_state(
            self.request, 'fee_payment_list', current_filters
        )
        
        # Apply filters
        return self.apply_filters(queryset, current_filters)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'fee_payment_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Add filter context
        context.update({
            'filter_context': self.get_filter_context(),
            'current_filters': current_filters,
            'has_filters': any(current_filters.values()),
        })
        
        # Add summary statistics
        queryset = self.get_queryset()
        payment_summary = queryset.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id')
        )
        
        context.update({
            'total_payments': payment_summary['total_count'] or 0,
            'total_amount': payment_summary['total_amount'] or 0,
        })
        
        # Payment method breakdown
        payment_methods = queryset.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-total')
        
        context['payment_methods'] = payment_methods
        
        return context


class ScholarshipListView(LoginRequiredMixin, ScholarshipFilterMixin, ListView):
    """Enhanced scholarship listing with advanced filtering"""
    model = Scholarship
    template_name = 'financial/scholarship_list.html'
    context_object_name = 'scholarships'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        school = getattr(self.request, 'school', None)
        queryset = Scholarship.all_objects.filter(school=school).prefetch_related('scholarshiprecipient_set') if school else Scholarship.objects.none()
        
        # Get current filters
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'scholarship_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Save current filters
        FilterStatePersistence.save_filter_state(
            self.request, 'scholarship_list', current_filters
        )
        
        # Apply filters
        return self.apply_filters(queryset, current_filters)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'scholarship_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Add filter context
        context.update({
            'filter_context': self.get_filter_context(),
            'current_filters': current_filters,
            'has_filters': any(current_filters.values()),
        })
        
        # Add summary statistics
        queryset = self.get_queryset()
        context.update({
            'total_scholarships': queryset.count(),
            'active_scholarships': queryset.filter(is_active=True).count(),
        })
        
        # Recipients summary
        recipients = _school_scholarship_recipients(getattr(self.request, 'school', None)).filter(
            scholarship__in=queryset,
            status='active'
        )
        
        recipients_summary = recipients.aggregate(
            total_recipients=Count('id'),
            total_amount=Sum('awarded_amount')
        )
        
        context.update({
            'total_recipients': recipients_summary['total_recipients'] or 0,
            'total_awarded': recipients_summary['total_amount'] or 0,
        })
        
        return context


class StaffPayrollListView(LoginRequiredMixin, StaffPayrollFilterMixin, ListView):
    """Enhanced staff payroll listing with advanced filtering"""
    model = StaffPayroll
    template_name = 'financial/staff_payroll_list.html'
    context_object_name = 'payrolls'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        school = getattr(self.request, 'school', None)
        queryset = _school_payrolls(school).select_related(
            'teacher__user', 'payroll_structure'
        ).order_by('-month', 'teacher__user__first_name') if school else StaffPayroll.objects.none()
        
        # Get current filters
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'staff_payroll_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Save current filters
        FilterStatePersistence.save_filter_state(
            self.request, 'staff_payroll_list', current_filters
        )
        
        # Apply filters
        return self.apply_filters(queryset, current_filters)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_filters = self.get_filter_state(self.request)
        
        # Load saved filters if no current filters
        if not any(current_filters.values()):
            saved_filters = FilterStatePersistence.load_filter_state(
                self.request, 'staff_payroll_list'
            )
            current_filters = FilterStatePersistence.merge_filters(
                saved_filters, current_filters
            )
        
        # Add filter context
        context.update({
            'filter_context': self.get_filter_context(),
            'current_filters': current_filters,
            'has_filters': any(current_filters.values()),
        })
        
        # Add summary statistics
        queryset = self.get_queryset()
        payroll_summary = queryset.aggregate(
            total_gross=Sum('gross_salary'),
            total_net=Sum('net_salary'),
            total_tax=Sum('tax_deduction'),
            total_pension=Sum('pension_deduction'),
            total_count=Count('id')
        )
        
        context.update({
            'total_payrolls': payroll_summary['total_count'] or 0,
            'total_gross_salary': payroll_summary['total_gross'] or 0,
            'total_net_salary': payroll_summary['total_net'] or 0,
            'total_tax_deduction': payroll_summary['total_tax'] or 0,
            'total_pension_deduction': payroll_summary['total_pension'] or 0,
            'paid_count': queryset.filter(is_paid=True).count(),
            'unpaid_count': queryset.filter(is_paid=False).count(),
        })
        
        return context


class FinancialTransactionListView(LoginRequiredMixin, FinancialTransactionFilterMixin, ListView):
    """Enhanced financial transaction listing with advanced filtering"""
    model = FinancialTransaction
    template_name = 'financial/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 25
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle adding new transaction"""
        school = getattr(request, 'school', None)
        if not school:
            messages.error(request, 'Select a school first.')
            return redirect('core:dashboard')
        try:
            from datetime import datetime
            transaction_date = request.POST.get('transaction_date')
            # Parse date string to date object
            if isinstance(transaction_date, str):
                transaction_date = datetime.strptime(transaction_date, '%Y-%m-%d').date()
            
            transaction = FinancialTransaction.all_objects.create(
                school=school,
                transaction_type=request.POST.get('transaction_type'),
                category=request.POST.get('category'),
                description=request.POST.get('description'),
                amount=request.POST.get('amount'),
                reference_number=request.POST.get('reference_number', ''),
                transaction_date=transaction_date,
                created_by=request.user
            )
            messages.success(request, f'Transaction added successfully: {transaction.description}')
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messages.error(request, f'Error adding transaction: {str(e)}')
            print(f"Transaction error: {error_details}")  # For debugging
        return redirect('financial:transaction_list')
    
    def get_queryset(self):
        school = getattr(self.request, 'school', None)
        queryset = FinancialTransaction.all_objects.filter(school=school).select_related('created_by') if school else FinancialTransaction.objects.none()
        
        # Get current filters from GET parameters only
        current_filters = self.get_filter_state(self.request)
        
        # Only apply filters if at least one filter is provided
        if any(current_filters.values()):
            # Save current filters
            FilterStatePersistence.save_filter_state(
                self.request, 'transaction_list', current_filters
            )
            # Apply filters
            queryset = self.apply_filters(queryset, current_filters)
        else:
            # Clear saved filters when no filters are provided
            FilterStatePersistence.clear_filter_state(self.request, 'transaction_list')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_filters = self.get_filter_state(self.request)
        
        # Add filter context
        context.update({
            'filter_context': self.get_filter_context(),
            'current_filters': current_filters,
            'has_filters': any(current_filters.values()),
            'today': timezone.now().date(),
        })
        
        # Add summary statistics
        queryset = self.get_queryset()
        
        income_summary = queryset.filter(transaction_type='income').aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        expense_summary = queryset.filter(transaction_type='expense').aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        total_income = income_summary['total'] or 0
        total_expenses = expense_summary['total'] or 0
        
        context.update({
            'total_transactions': queryset.count(),
            'total_income': total_income,
            'income_count': income_summary['count'] or 0,
            'total_expenses': total_expenses,
            'total_expense': total_expenses,  # Template compatibility
            'expense_count': expense_summary['count'] or 0,
            'net_amount': total_income - total_expenses,
            'net_balance': total_income - total_expenses,  # Template compatibility
        })
        
        # Category breakdown
        categories = queryset.values('category', 'transaction_type').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('transaction_type', '-total')
        
        context['categories'] = categories
        
        return context


# AJAX endpoints for real-time filtering

@login_required
def filter_student_fees_ajax(request):
    """AJAX endpoint for filtering student fees"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = StudentFeeFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    
    queryset = _school_student_fees(school).select_related(
        'student__user', 'student__school_class', 'fee_structure__term'
    )
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Prepare response data
    data = []
    for fee in filtered_queryset[:50]:  # Limit to 50 results for performance
        data.append({
            'id': fee.id,
            'student_name': fee.student.user.get_full_name(),
            'student_id': fee.student.student_id,
            'class_name': fee.student.school_class.name,
            'fee_structure': fee.fee_structure.name,
            'total_amount': float(fee.total_amount),
            'paid_amount': float(fee.paid_amount),
            'balance_amount': float(fee.balance_amount),
            'status': fee.get_status_display(),
            'due_date': fee.due_date.strftime('%Y-%m-%d'),
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50
    })


@login_required
def clear_filters_ajax(request):
    """AJAX endpoint for clearing filters"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    view_name = request.GET.get('view_name')
    if view_name:
        FilterStatePersistence.clear_filter_state(request, view_name)
    
    return JsonResponse({'success': True})

# Auto-complete AJAX endpoints

@login_required
def autocomplete_students_ajax(request):
    """AJAX endpoint for student auto-complete"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'suggestions': []})
    
    term = request.GET.get('term', '').strip()
    limit = int(request.GET.get('limit', 10))
    
    if len(term) < 2:
        return JsonResponse({'suggestions': []})
    
    students = active_students(school).select_related('user', 'school_class').filter(
        Q(user__first_name__icontains=term) |
        Q(user__last_name__icontains=term) |
        Q(student_id__icontains=term)
    )[:limit]
    
    suggestions = []
    for student in students:
        suggestions.append({
            'id': student.id,
            'name': student.user.get_full_name(),
            'student_id': student.student_id,
            'class_name': student.school_class.name,
            'label': f"{student.user.get_full_name()} ({student.student_id}) - {student.school_class.name}",
            'value': student.user.get_full_name()
        })
    
    return JsonResponse({'suggestions': suggestions})


@login_required
def autocomplete_teachers_ajax(request):
    """AJAX endpoint for teacher auto-complete"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'suggestions': []})
    
    term = request.GET.get('term', '').strip()
    limit = int(request.GET.get('limit', 10))
    
    if len(term) < 2:
        return JsonResponse({'suggestions': []})
    
    teachers = active_staff(school).select_related('user').filter(
        Q(user__first_name__icontains=term) |
        Q(user__last_name__icontains=term) |
        Q(employee_id__icontains=term)
    )[:limit]
    
    suggestions = []
    for teacher in teachers:
        suggestions.append({
            'id': teacher.id,
            'name': teacher.user.get_full_name(),
            'employee_id': teacher.employee_id,
            'label': f"{teacher.user.get_full_name()} ({teacher.employee_id})",
            'value': teacher.user.get_full_name()
        })
    
    return JsonResponse({'suggestions': suggestions})


@login_required
def autocomplete_references_ajax(request):
    """AJAX endpoint for reference number auto-complete"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'suggestions': []})
    
    term = request.GET.get('term', '').strip()
    limit = int(request.GET.get('limit', 10))
    
    if len(term) < 2:
        return JsonResponse({'suggestions': []})
    
    # Search in fee payments and financial transactions
    payments = _school_fee_payments(school).select_related('student_fee__student__user').filter(
        reference_number__icontains=term
    ).exclude(reference_number='')[:limit//2]
    
    transactions = FinancialTransaction.all_objects.filter(
        school=school,
        reference_number__icontains=term
    ).exclude(reference_number='')[:limit//2]
    
    suggestions = []
    
    for payment in payments:
        suggestions.append({
            'reference_number': payment.reference_number,
            'description': f"Payment - {payment.student_fee.student.user.get_full_name()}",
            'amount': float(payment.amount),
            'date': payment.payment_date.strftime('%Y-%m-%d'),
            'label': f"{payment.reference_number} - Payment - {payment.student_fee.student.user.get_full_name()}",
            'value': payment.reference_number
        })
    
    for transaction in transactions:
        suggestions.append({
            'reference_number': transaction.reference_number,
            'description': f"{transaction.get_transaction_type_display()} - {transaction.description}",
            'amount': float(transaction.amount),
            'date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'label': f"{transaction.reference_number} - {transaction.description}",
            'value': transaction.reference_number
        })
    
    return JsonResponse({'suggestions': suggestions[:limit]})


@login_required
def autocomplete_general_ajax(request):
    """AJAX endpoint for general auto-complete"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'suggestions': []})
    
    term = request.GET.get('term', '').strip()
    search_type = request.GET.get('search_type', 'general')
    limit = int(request.GET.get('limit', 10))
    
    if len(term) < 2:
        return JsonResponse({'suggestions': []})
    
    suggestions = []
    
    if search_type == 'fee_structure':
        fee_structures = _school_fee_structures(school).filter(
            name__icontains=term
        )[:limit]
        
        for fs in fee_structures:
            suggestions.append({
                'id': fs.id,
                'name': fs.name,
                'class_name': fs.school_class.name,
                'term_name': fs.term.name,
                'label': f"{fs.name} - {fs.school_class.name} - {fs.term.name}",
                'value': fs.name
            })
    
    elif search_type == 'scholarship':
        scholarships = Scholarship.all_objects.filter(
            school=school,
            name__icontains=term
        )[:limit]
        
        for scholarship in scholarships:
            suggestions.append({
                'id': scholarship.id,
                'name': scholarship.name,
                'type': scholarship.get_scholarship_type_display(),
                'academic_year': scholarship.academic_year,
                'label': f"{scholarship.name} - {scholarship.get_scholarship_type_display()}",
                'value': scholarship.name
            })
    
    return JsonResponse({'suggestions': suggestions})


@login_required
def get_terms_by_class_ajax(request):
    """AJAX endpoint to get terms for a specific class"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'terms': []})
    
    class_id = request.GET.get('class_id')
    if not class_id:
        return JsonResponse({'terms': []})
    
    # Get terms that have fee structures for this class
    if not SchoolClass.all_objects.filter(id=class_id, school=school).exists():
        return JsonResponse({'terms': []})

    terms = Term.all_objects.filter(
        school=school,
        feestructure__school_class_id=class_id
    ).distinct().values('id', 'name').order_by('name')
    
    return JsonResponse({'terms': list(terms)})


@login_required
def search_highlight_ajax(request):
    """AJAX endpoint for search result highlighting"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    search_term = request.GET.get('search_term', '').strip()
    content = request.GET.get('content', '')
    
    if not search_term or not content:
        return JsonResponse({'highlighted_content': content})
    
    import re
    
    # Escape special regex characters in search term
    escaped_term = re.escape(search_term)
    
    # Create case-insensitive regex pattern
    pattern = re.compile(f'({escaped_term})', re.IGNORECASE)
    
    # Replace matches with highlighted version
    highlighted_content = pattern.sub(r'<mark>\1</mark>', content)
    
    return JsonResponse({'highlighted_content': highlighted_content})


# Enhanced search endpoints with result highlighting

@login_required
def search_student_fees_ajax(request):
    """Enhanced AJAX endpoint for searching student fees with highlighting"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = StudentFeeFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    search_term = filters.get('search', '').strip()
    
    queryset = _school_student_fees(school).select_related(
        'student__user', 'student__school_class', 'fee_structure__term'
    )
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Limit results for performance
    results = filtered_queryset[:50]
    
    # Prepare response data with highlighting
    data = []
    for fee in results:
        student_name = fee.student.user.get_full_name()
        
        # Highlight search term in results
        if search_term:
            import re
            pattern = re.compile(f'({re.escape(search_term)})', re.IGNORECASE)
            student_name = pattern.sub(r'<mark>\1</mark>', student_name)
        
        data.append({
            'id': fee.id,
            'student_name': student_name,
            'student_id': fee.student.student_id,
            'class_name': fee.student.school_class.name,
            'fee_structure': fee.fee_structure.name,
            'total_amount': float(fee.total_amount),
            'paid_amount': float(fee.paid_amount),
            'balance_amount': float(fee.balance_amount),
            'status': fee.get_status_display(),
            'status_class': fee.status,
            'due_date': fee.due_date.strftime('%Y-%m-%d'),
            'created_at': fee.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50,
        'search_term': search_term
    })


@login_required
def export_filtered_data_ajax(request):
    """AJAX endpoint for exporting filtered data"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    export_type = request.GET.get('export_type', 'student_fees')
    export_format = request.GET.get('export_format', 'csv')
    
    # Get appropriate filter mixin based on export type
    filter_mixins = {
        'student_fees': StudentFeeFilterMixin(),
        'payments': FeePaymentFilterMixin(),
        'scholarships': ScholarshipFilterMixin(),
        'payroll': StaffPayrollFilterMixin(),
        'transactions': FinancialTransactionFilterMixin(),
    }
    
    filter_mixin = filter_mixins.get(export_type)
    if not filter_mixin:
        return JsonResponse({'error': 'Invalid export type'}, status=400)
    
    filters = filter_mixin.get_filter_state(request)
    
    # Generate export URL with filters
    export_url = f"/financial/export/{export_type}/"
    query_params = []
    
    for key, value in filters.items():
        if value:
            query_params.append(f"{key}={value}")
    
    query_params.append(f"format={export_format}")
    
    if query_params:
        export_url += "?" + "&".join(query_params)
    
    return JsonResponse({
        'export_url': export_url,
        'filters_applied': len([v for v in filters.values() if v])
    })


# Additional AJAX endpoints for other financial models

@login_required
def filter_payments_ajax(request):
    """AJAX endpoint for filtering fee payments"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = FeePaymentFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    
    queryset = _school_fee_payments(school).select_related(
        'student_fee__student__user',
        'student_fee__student__school_class',
        'student_fee__fee_structure__term',
        'received_by'
    )
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Prepare response data
    data = []
    for payment in filtered_queryset[:50]:  # Limit to 50 results for performance
        data.append({
            'id': payment.id,
            'student_name': payment.student_fee.student.user.get_full_name(),
            'student_id': payment.student_fee.student.student_id,
            'class_name': payment.student_fee.student.school_class.name,
            'amount': float(payment.amount),
            'payment_method': payment.get_payment_method_display(),
            'reference_number': payment.reference_number,
            'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M'),
            'received_by': payment.received_by.get_full_name() if payment.received_by else '',
            'notes': payment.notes,
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50
    })


@login_required
def filter_scholarships_ajax(request):
    """AJAX endpoint for filtering scholarships"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = ScholarshipFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    
    queryset = Scholarship.all_objects.filter(school=school).prefetch_related('scholarshiprecipient_set')
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Prepare response data
    data = []
    for scholarship in filtered_queryset[:50]:  # Limit to 50 results for performance
        active_recipients = scholarship.scholarshiprecipient_set.filter(student__school=school, status='active').count()
        total_awarded = scholarship.scholarshiprecipient_set.filter(
            student__school=school,
            status='active'
        ).aggregate(Sum('awarded_amount'))['awarded_amount__sum'] or 0
        
        data.append({
            'id': scholarship.id,
            'name': scholarship.name,
            'scholarship_type': scholarship.get_scholarship_type_display(),
            'description': scholarship.description,
            'amount': float(scholarship.amount) if scholarship.amount else None,
            'percentage': float(scholarship.percentage) if scholarship.percentage else None,
            'max_recipients': scholarship.max_recipients,
            'active_recipients': active_recipients,
            'total_awarded': float(total_awarded),
            'academic_year': scholarship.academic_year,
            'is_active': scholarship.is_active,
            'created_at': scholarship.created_at.strftime('%Y-%m-%d'),
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50
    })


@login_required
def filter_payroll_ajax(request):
    """AJAX endpoint for filtering staff payroll"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = StaffPayrollFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    
    queryset = _school_payrolls(school).select_related(
        'teacher__user', 'payroll_structure'
    )
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Prepare response data
    data = []
    for payroll in filtered_queryset[:50]:  # Limit to 50 results for performance
        data.append({
            'id': payroll.id,
            'teacher_name': payroll.teacher.user.get_full_name(),
            'employee_id': payroll.teacher.employee_id,
            'month': payroll.month.strftime('%Y-%m'),
            'gross_salary': float(payroll.gross_salary),
            'tax_deduction': float(payroll.tax_deduction),
            'pension_deduction': float(payroll.pension_deduction),
            'net_salary': float(payroll.net_salary),
            'is_paid': payroll.is_paid,
            'payment_date': payroll.payment_date.strftime('%Y-%m-%d') if payroll.payment_date else None,
            'created_at': payroll.created_at.strftime('%Y-%m-%d'),
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50
    })


@login_required
def filter_transactions_ajax(request):
    """AJAX endpoint for filtering financial transactions"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = FinancialTransactionFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    
    queryset = FinancialTransaction.all_objects.filter(school=school).select_related('created_by')
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Prepare response data
    data = []
    for transaction in filtered_queryset[:50]:  # Limit to 50 results for performance
        data.append({
            'id': transaction.id,
            'description': transaction.description,
            'transaction_type': transaction.get_transaction_type_display(),
            'category': transaction.category,
            'amount': float(transaction.amount),
            'reference_number': transaction.reference_number,
            'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'created_by': transaction.created_by.get_full_name() if transaction.created_by else '',
            'created_at': transaction.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50
    })


@login_required
def search_payments_ajax(request):
    """Enhanced AJAX endpoint for searching payments with highlighting"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = FeePaymentFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    search_term = filters.get('search', '').strip()
    
    queryset = _school_fee_payments(school).select_related(
        'student_fee__student__user',
        'student_fee__student__school_class',
        'student_fee__fee_structure__term',
        'received_by'
    )
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Limit results for performance
    results = filtered_queryset[:50]
    
    # Prepare response data with highlighting
    data = []
    for payment in results:
        student_name = payment.student_fee.student.user.get_full_name()
        reference_number = payment.reference_number
        
        # Highlight search term in results
        if search_term:
            import re
            pattern = re.compile(f'({re.escape(search_term)})', re.IGNORECASE)
            student_name = pattern.sub(r'<mark>\1</mark>', student_name)
            if reference_number:
                reference_number = pattern.sub(r'<mark>\1</mark>', reference_number)
        
        data.append({
            'id': payment.id,
            'student_name': student_name,
            'student_id': payment.student_fee.student.student_id,
            'class_name': payment.student_fee.student.school_class.name,
            'amount': float(payment.amount),
            'payment_method': payment.get_payment_method_display(),
            'reference_number': reference_number,
            'payment_date': payment.payment_date.strftime('%Y-%m-%d %H:%M'),
            'received_by': payment.received_by.get_full_name() if payment.received_by else '',
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50,
        'search_term': search_term
    })


@login_required
def search_scholarships_ajax(request):
    """Enhanced AJAX endpoint for searching scholarships with highlighting"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = ScholarshipFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    search_term = filters.get('search', '').strip()
    
    queryset = Scholarship.all_objects.filter(school=school).prefetch_related('scholarshiprecipient_set')
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Limit results for performance
    results = filtered_queryset[:50]
    
    # Prepare response data with highlighting
    data = []
    for scholarship in results:
        name = scholarship.name
        description = scholarship.description
        
        # Highlight search term in results
        if search_term:
            import re
            pattern = re.compile(f'({re.escape(search_term)})', re.IGNORECASE)
            name = pattern.sub(r'<mark>\1</mark>', name)
            if description:
                description = pattern.sub(r'<mark>\1</mark>', description)
        
        active_recipients = scholarship.scholarshiprecipient_set.filter(student__school=school, status='active').count()
        total_awarded = scholarship.scholarshiprecipient_set.filter(
            student__school=school,
            status='active'
        ).aggregate(Sum('awarded_amount'))['awarded_amount__sum'] or 0
        
        data.append({
            'id': scholarship.id,
            'name': name,
            'scholarship_type': scholarship.get_scholarship_type_display(),
            'description': description,
            'amount': float(scholarship.amount) if scholarship.amount else None,
            'percentage': float(scholarship.percentage) if scholarship.percentage else None,
            'active_recipients': active_recipients,
            'total_awarded': float(total_awarded),
            'academic_year': scholarship.academic_year,
            'is_active': scholarship.is_active,
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50,
        'search_term': search_term
    })


@login_required
def search_payroll_ajax(request):
    """Enhanced AJAX endpoint for searching payroll with highlighting"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = StaffPayrollFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    search_term = filters.get('search', '').strip()
    
    queryset = _school_payrolls(school).select_related(
        'teacher__user', 'payroll_structure'
    )
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Limit results for performance
    results = filtered_queryset[:50]
    
    # Prepare response data with highlighting
    data = []
    for payroll in results:
        teacher_name = payroll.teacher.user.get_full_name()
        employee_id = payroll.teacher.employee_id
        
        # Highlight search term in results
        if search_term:
            import re
            pattern = re.compile(f'({re.escape(search_term)})', re.IGNORECASE)
            teacher_name = pattern.sub(r'<mark>\1</mark>', teacher_name)
            if employee_id:
                employee_id = pattern.sub(r'<mark>\1</mark>', employee_id)
        
        data.append({
            'id': payroll.id,
            'teacher_name': teacher_name,
            'employee_id': employee_id,
            'month': payroll.month.strftime('%Y-%m'),
            'gross_salary': float(payroll.gross_salary),
            'net_salary': float(payroll.net_salary),
            'is_paid': payroll.is_paid,
            'payment_date': payroll.payment_date.strftime('%Y-%m-%d') if payroll.payment_date else None,
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50,
        'search_term': search_term
    })


@login_required
def search_transactions_ajax(request):
    """Enhanced AJAX endpoint for searching transactions with highlighting"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    filter_mixin = FinancialTransactionFilterMixin()
    filters = filter_mixin.get_filter_state(request)
    search_term = filters.get('search', '').strip()
    
    queryset = FinancialTransaction.all_objects.filter(school=school).select_related('created_by')
    
    filtered_queryset = filter_mixin.apply_filters(queryset, filters)
    
    # Limit results for performance
    results = filtered_queryset[:50]
    
    # Prepare response data with highlighting
    data = []
    for transaction in results:
        description = transaction.description
        reference_number = transaction.reference_number
        category = transaction.category
        
        # Highlight search term in results
        if search_term:
            import re
            pattern = re.compile(f'({re.escape(search_term)})', re.IGNORECASE)
            if description:
                description = pattern.sub(r'<mark>\1</mark>', description)
            if reference_number:
                reference_number = pattern.sub(r'<mark>\1</mark>', reference_number)
            if category:
                category = pattern.sub(r'<mark>\1</mark>', category)
        
        data.append({
            'id': transaction.id,
            'description': description,
            'transaction_type': transaction.get_transaction_type_display(),
            'category': category,
            'amount': float(transaction.amount),
            'reference_number': reference_number,
            'transaction_date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'created_by': transaction.created_by.get_full_name() if transaction.created_by else '',
        })
    
    return JsonResponse({
        'results': data,
        'total_count': filtered_queryset.count(),
        'has_more': filtered_queryset.count() > 50,
        'search_term': search_term
    })

# Analytics Views

@login_required
def financial_analytics_dashboard(request):
    """
    Financial analytics dashboard with Chart.js integration
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    # Get analytics data
    analytics_service = FinancialAnalyticsService()
    
    # Get chart data
    fee_trends = analytics_service.get_fee_collection_trends(months=6, school=school)
    payment_status = analytics_service.get_payment_status_distribution(school=school)
    income_expense = analytics_service.get_income_vs_expenses_comparison(months=12, school=school)
    expense_breakdown = analytics_service.get_expense_breakdown(school=school)
    scholarship_distribution = analytics_service.get_scholarship_distribution_analysis(school=school)
    dashboard_summary = analytics_service.get_financial_summary_dashboard(school=school)
    
    # Get recent transactions for the table
    recent_transactions = FinancialTransaction.all_objects.filter(school=school).select_related('created_by').order_by('-created_at')[:10]
    
    # Calculate monthly summaries for the table
    monthly_summaries = []
    for month_data in income_expense['detailed_data'][-6:]:  # Last 6 months
        profit_margin = 0
        if month_data['total_income'] > 0:
            profit_margin = (month_data['net_profit'] / month_data['total_income']) * 100
        
        monthly_summaries.append({
            'month': month_data['month_short'],
            'fee_income': month_data['fee_income'],
            'other_income': month_data['other_income'],
            'total_income': month_data['total_income'],
            'expenses': month_data['total_expenses'],
            'net_profit': month_data['net_profit'],
            'profit_margin': profit_margin
        })
    
    context = {
        # KPI data
        'total_revenue': dashboard_summary['fee_collection']['total_paid'] + dashboard_summary['fee_collection']['current_month_collections'],
        'revenue_change': 5.2,  # This would be calculated from previous month comparison
        'fees_collected': dashboard_summary['fee_collection']['total_paid'],
        'collection_rate': dashboard_summary['fee_collection']['collection_rate'],
        'outstanding_amount': dashboard_summary['outstanding_fees']['overdue_amount'],
        'overdue_count': dashboard_summary['outstanding_fees']['overdue_count'],
        'scholarship_amount': dashboard_summary['scholarships']['total_awarded'],
        'scholarship_recipients': dashboard_summary['scholarships']['active_recipients'],
        
        # Chart data
        'fee_trends': fee_trends,
        'payment_status': payment_status,
        'income_expense': income_expense,
        'expense_breakdown': expense_breakdown,
        'scholarship_distribution': scholarship_distribution['by_type'],
        
        # Table data
        'recent_transactions': recent_transactions,
        'monthly_summaries': monthly_summaries,
    }
    
    return render(request, 'financial/reports/analytics.html', context)

@login_required
def analytics_data_ajax(request):
    """
    AJAX endpoint for dynamic chart data updates
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    chart_type = request.GET.get('chart_type', 'fee_trends')
    months = int(request.GET.get('months', 6))
    
    analytics_service = FinancialAnalyticsService()
    
    try:
        if chart_type == 'fee_trends':
            data = analytics_service.get_fee_collection_trends(months=months, school=school)
        elif chart_type == 'income_expense':
            data = analytics_service.get_income_vs_expenses_comparison(months=months, school=school)
        elif chart_type == 'payment_status':
            data = analytics_service.get_payment_status_distribution(school=school)
        elif chart_type == 'expense_breakdown':
            data = analytics_service.get_expense_breakdown(school=school)
        elif chart_type == 'scholarship_distribution':
            data = analytics_service.get_scholarship_distribution_analysis(school=school)
        elif chart_type == 'class_wise':
            data = analytics_service.get_class_wise_fee_collection(school=school)
        elif chart_type == 'dashboard_summary':
            data = analytics_service.get_financial_summary_dashboard(school=school)
        else:
            return JsonResponse({'error': 'Invalid chart type'}, status=400)
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def financial_reports_dashboard(request):
    """
    Enhanced financial reports dashboard with customization options
    Requirements: 9.6, 9.7 - Report customization and visualization
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    from .services_reports import ReportService
    
    # Get available report types
    available_reports = {
        'monthly_summary': {
            'name': 'Monthly Financial Summary',
            'description': 'Comprehensive monthly income, expenses, and profit analysis'
        },
        'fee_collection': {
            'name': 'Fee Collection Report',
            'description': 'Detailed fee collection status by class, term, and student'
        },
        'scholarship_distribution': {
            'name': 'Scholarship Distribution',
            'description': 'Analysis of scholarship awards and recipients'
        },
        'payroll': {
            'name': 'Payroll Report',
            'description': 'Staff payroll summary with deductions and net pay'
        },
        'year_over_year': {
            'name': 'Year-over-Year Comparison',
            'description': 'Compare financial performance across multiple years'
        }
    }
    
    # Get filter options for dropdowns
    terms = Term.all_objects.filter(school=school).order_by('-start_date')
    classes = SchoolClass.all_objects.filter(school=school).order_by('name')
    current_year = timezone.now().year
    years = list(range(current_year - 5, current_year + 1))
    
    context = {
        'available_reports': available_reports,
        'terms': terms,
        'classes': classes,
        'sessions': existing_session_choices(school=school),
        'years': years,
        'current_year': current_year,
        'current_month': timezone.now().month,
        'months': [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]
    }
    
    return render(request, 'financial/reports/dashboard.html', context)

@login_required
def generate_custom_report(request):
    """
    Generate custom financial report with user-specified parameters
    Requirements: 9.6, 9.7 - Report customization functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        report_type = request.POST.get('report_type')
        
        if not report_type:
            messages.error(request, 'Please select a report type')
            return redirect('financial:financial_reports_dashboard')
        
        try:
            # Build parameters based on report type
            parameters = {}
            
            if report_type == 'monthly_summary':
                year = int(request.POST.get('year', timezone.now().year))
                month = int(request.POST.get('month', timezone.now().month))
                if not (2000 <= year <= 2100):
                    raise ValueError(f'Year must be between 2000 and 2100, got {year}')
                if not (1 <= month <= 12):
                    raise ValueError(f'Month must be between 1 and 12, got {month}')
                parameters.update({'year': year, 'month': month})
            elif report_type == 'fee_collection':
                if request.POST.get('term_id'):
                    parameters['term_id'] = int(request.POST.get('term_id'))
                if request.POST.get('class_id'):
                    parameters['class_id'] = int(request.POST.get('class_id'))
                if request.POST.get('status_filter'):
                    parameters['status_filter'] = request.POST.get('status_filter')
                if request.POST.get('date_from') and request.POST.get('date_to'):
                    parameters['date_range'] = [
                        datetime.strptime(request.POST.get('date_from'), '%Y-%m-%d').date(),
                        datetime.strptime(request.POST.get('date_to'), '%Y-%m-%d').date()
                    ]
            elif report_type == 'scholarship_distribution':
                if request.POST.get('academic_year'):
                    academic_year = request.POST.get('academic_year')
                    if academic_year not in dict(existing_session_choices(school=school)):
                        raise ValueError('Select an academic session configured under school terms.')
                    parameters['academic_year'] = academic_year
                if request.POST.get('scholarship_type'):
                    parameters['scholarship_type'] = request.POST.get('scholarship_type')
            elif report_type == 'payroll':
                year = int(request.POST.get('year', timezone.now().year))
                month = int(request.POST.get('month', timezone.now().month))
                if not (2000 <= year <= 2100):
                    raise ValueError(f'Year must be between 2000 and 2100, got {year}')
                if not (1 <= month <= 12):
                    raise ValueError(f'Month must be between 1 and 12, got {month}')
                parameters.update({'year': year, 'month': month})
                if request.POST.get('department'):
                    parameters['department'] = request.POST.get('department')
            elif report_type == 'year_over_year':
                parameters.update({
                    'current_year': int(request.POST.get('current_year', timezone.now().year)),
                    'comparison_years': int(request.POST.get('comparison_years', 1))
                })
            
            # Generate the report
            report_data = ReportService.generate_custom_report(report_type, school=school, **parameters)
            
            # Convert Decimal to float for JSON serialization
            def convert_decimals(obj):
                if isinstance(obj, dict):
                    return {k: convert_decimals(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_decimals(item) for item in obj]
                elif isinstance(obj, Decimal):
                    return float(obj)
                return obj
            
            # Store report data in session for potential export
            request.session['last_report_data'] = convert_decimals(report_data)
            request.session['last_report_type'] = report_type
            
            context = {
                'report_data': report_data,
                'report_type': report_type,
                'generated_at': timezone.now()
            }
            
            return render(request, 'financial/reports/custom_report.html', context)
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error generating report: {error_trace}")
            messages.error(request, f'Error generating report: {str(e)}')
            return redirect('financial:financial_reports_dashboard')
    
    return redirect('financial:financial_reports_dashboard')

@login_required
def scheduled_reports_list(request):
    """
    List and manage scheduled reports
    Requirements: 9.7 - Report scheduling functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    from .services_report_customization import ScheduledReport
    
    # Get all scheduled reports for the current user or all if super admin
    scheduled_reports = ScheduledReport.objects.all().order_by('-created_at')
    
    context = {
        'scheduled_reports': scheduled_reports,
        'available_frequencies': [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly')],
        'report_templates': ReportCustomizationService.get_report_templates()
    }
    
    return render(request, 'financial/reports/scheduled_reports.html', context)

@login_required
def export_custom_report(request):
    """
    Export the last generated custom report in various formats
    Requirements: 9.6, 9.7 - Report export functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Get report data from session
    report_data = request.session.get('last_report_data')
    report_type = request.session.get('last_report_type')
    export_format = request.POST.get('format', 'csv')
    
    if not report_data:
        return JsonResponse({'error': 'No report data available'}, status=400)
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write report header
        writer.writerow([report_data['report_info']['title']])
        writer.writerow(['Generated:', report_data['report_info']['generated_at']])
        writer.writerow([])
        
        # Write report-specific data
        if report_type == 'monthly_summary':
            writer.writerow(['INCOME SUMMARY'])
            writer.writerow(['Fee Income:', f"?{report_data['income_summary']['fee_income']['total_amount']:.2f}"])
            writer.writerow(['Other Income:', f"?{report_data['income_summary']['other_income']['total_amount']:.2f}"])
            writer.writerow(['Total Income:', f"?{report_data['income_summary']['total_income']:.2f}"])
            writer.writerow([])
            
            writer.writerow(['EXPENSE SUMMARY'])
            writer.writerow(['Operational Expenses:', f"?{report_data['expense_summary']['operational_expenses']['total_amount']:.2f}"])
            writer.writerow(['Payroll Expenses:', f"?{report_data['expense_summary']['payroll_expenses']['total_net']:.2f}"])
            writer.writerow(['Total Expenses:', f"?{report_data['expense_summary']['total_expenses']:.2f}"])
            writer.writerow([])
            
            writer.writerow(['PROFIT ANALYSIS'])
            writer.writerow(['Net Profit:', f"?{report_data['profit_analysis']['net_profit']:.2f}"])
            writer.writerow(['Profit Margin:', f"{report_data['profit_analysis']['profit_margin_percent']:.2f}%"])
            
        elif report_type == 'fee_collection':
            writer.writerow(['COLLECTION SUMMARY'])
            writer.writerow(['Total Fees:', report_data['summary']['total_fees']])
            writer.writerow(['Total Amount:', f"?{report_data['summary']['total_amount']:.2f}"])
            writer.writerow(['Total Paid:', f"?{report_data['summary']['total_paid']:.2f}"])
            writer.writerow(['Collection Rate:', f"{report_data['summary']['collection_rate_percent']:.2f}%"])
            writer.writerow([])
            
            writer.writerow(['STATUS BREAKDOWN'])
            writer.writerow(['Status', 'Count', 'Amount', 'Percentage'])
            for status in report_data['status_breakdown']:
                writer.writerow([
                    status['status'],
                    status['count'],
                    f"?{status['total_amount']:.2f}",
                    f"{status['percentage']:.2f}%"
                ])
        
        return response
    
    elif export_format == 'json':
        response = HttpResponse(content_type='application/json')
        filename = f"{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M')}.json"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        import json
        response.write(json.dumps(report_data, indent=2, default=str))
        return response
    
    else:
        return JsonResponse({'error': 'Unsupported format'}, status=400)

@login_required
def export_analytics_report(request):
    """
    Export analytics report in various formats
    Requirements: 6.5 - Chart export functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    report_type = request.POST.get('report_type', 'summary')
    start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
    end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
    export_format = request.POST.get('format', 'pdf')
    
    # Parse dates
    try:
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    analytics_service = FinancialAnalyticsService()
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="financial_analytics_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Financial Analytics Report'])
        writer.writerow(['Generated on:', timezone.now().strftime('%Y-%m-%d %H:%M')])
        writer.writerow([])
        
        if report_type in ['summary', 'detailed']:
            # Fee collection trends
            fee_trends = analytics_service.get_fee_collection_trends(months=12)
            writer.writerow(['Fee Collection Trends'])
            writer.writerow(['Month', 'Amount', 'Payment Count'])
            for i, label in enumerate(fee_trends['labels']):
                writer.writerow([
                    label,
                    fee_trends['data'][i],
                    fee_trends['payment_counts'][i]
                ])
            writer.writerow([])
            
            # Payment status distribution
            payment_status = analytics_service.get_payment_status_distribution()
            writer.writerow(['Payment Status Distribution'])
            writer.writerow(['Status', 'Count', 'Percentage'])
            for item in payment_status['detailed_data']:
                writer.writerow([
                    item['status'],
                    item['count'],
                    f"{item['percentage']:.1f}%"
                ])
            writer.writerow([])
            
            # Expense breakdown
            expense_breakdown = analytics_service.get_expense_breakdown()
            writer.writerow(['Expense Breakdown'])
            writer.writerow(['Category', 'Amount', 'Percentage'])
            for item in expense_breakdown['detailed_data']:
                writer.writerow([
                    item['category'],
                    item['amount'],
                    f"{item['percentage']:.1f}%"
                ])
        
        return response
    
    elif export_format == 'excel':
        # For Excel export, you would use openpyxl or xlsxwriter
        # This is a placeholder for Excel functionality
        return JsonResponse({'error': 'Excel export not implemented yet'}, status=501)
    
    elif export_format == 'pdf':
        # For PDF export, you would use reportlab or weasyprint
        # This is a placeholder for PDF functionality
        return JsonResponse({'error': 'PDF export not implemented yet'}, status=501)
    
    else:
        return JsonResponse({'error': 'Invalid export format'}, status=400)

@login_required
def chart_data_api(request, chart_type):
    """
    API endpoint for specific chart data
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    analytics_service = FinancialAnalyticsService()
    
    try:
        # Get parameters
        params = {}
        if 'months' in request.GET:
            params['months'] = int(request.GET.get('months'))
        
        data = analytics_service.get_chart_data_for_type(chart_type, **params)
        return JsonResponse(data)
    
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Internal server error'}, status=500)


# ============================================================================
# AUDIT LOG VIEWS
# ============================================================================

@login_required
def audit_logs(request):
    """Display financial audit logs with search and filtering"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('financial:financial_dashboard')
    
    # Get filter parameters from request
    filters = {
        'operation': request.GET.get('operation'),
        'model_name': request.GET.get('model_name'),
        'user_id': request.GET.get('user_id'),
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'search_term': request.GET.get('search_term'),
        'object_id': request.GET.get('object_id'),
    }
    
    # Remove empty filters
    filters = {k: v for k, v in filters.items() if v}
    
    # Get filtered audit logs
    audit_logs = AuditLogSearchService.search_logs(filters)
    
    # Handle CSV export
    if request.GET.get('export') == 'csv':
        return export_audit_logs_csv(request, audit_logs)
    
    # Pagination
    paginator = Paginator(audit_logs, 25)
    page_number = request.GET.get('page')
    audit_logs_page = paginator.get_page(page_number)
    
    # Get all users for filter dropdown
    users = User.objects.filter(
        id__in=FinancialAuditLog.objects.values_list('user_id', flat=True).distinct()
    ).exclude(id__isnull=True)
    
    # Get selected user for display
    selected_user = None
    if filters.get('user_id'):
        try:
            selected_user = User.objects.get(id=filters['user_id'])
        except User.DoesNotExist:
            pass
    
    context = {
        'audit_logs': audit_logs_page,
        'users': users,
        'selected_user': selected_user,
        'filters_applied': bool(filters),
        'total_count': audit_logs.count(),
    }
    
    return render(request, 'financial/audit/logs.html', context)


@login_required
def audit_search(request):
    """Advanced audit log search interface"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('financial:financial_dashboard')
    
    context = {
        'users': User.objects.filter(
            id__in=FinancialAuditLog.objects.values_list('user_id', flat=True).distinct()
        ).exclude(id__isnull=True),
        'operation_choices': FinancialAuditLog.OPERATION_CHOICES,
        'model_choices': FinancialAuditLog.MODEL_CHOICES,
    }
    
    return render(request, 'financial/audit/search.html', context)


@login_required
def object_audit_history(request, model_name, object_id):
    """Get audit history for a specific object"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        history = AuditLogSearchService.get_object_history(model_name, object_id)
        
        # Convert to JSON-serializable format
        history_data = []
        for log in history:
            history_data.append({
                'id': log.id,
                'operation': log.get_operation_display(),
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.get_full_name() if log.user else 'System',
                'changes': log.changes,
                'ip_address': log.ip_address,
            })
        
        return JsonResponse({
            'history': history_data,
            'total_count': len(history_data)
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def user_audit_activity(request, user_id):
    """Get recent audit activity for a specific user"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        days = int(request.GET.get('days', 30))
        activity = AuditLogSearchService.get_user_activity(user_id, days)
        
        # Convert to JSON-serializable format
        activity_data = []
        for log in activity:
            activity_data.append({
                'id': log.id,
                'operation': log.get_operation_display(),
                'model_name': log.get_model_name_display(),
                'object_id': log.object_id,
                'timestamp': log.timestamp.isoformat(),
                'changes': log.changes,
            })
        
        return JsonResponse({
            'activity': activity_data,
            'total_count': len(activity_data),
            'days': days
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def audit_operation_summary(request):
    """Get summary of audit operations within date range"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Parse dates
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        
        if date_to:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        summary = AuditLogSearchService.get_operation_summary(date_from_obj, date_to_obj)
        
        # Convert to JSON-serializable format
        summary_data = []
        for item in summary:
            summary_data.append({
                'operation': item['operation'],
                'operation_display': dict(FinancialAuditLog.OPERATION_CHOICES)[item['operation']],
                'count': item['count']
            })
        
        return JsonResponse({
            'summary': summary_data,
            'date_from': date_from,
            'date_to': date_to
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def export_audit_logs_csv(request, queryset):
    """Export audit logs to CSV format"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Timestamp', 'Operation', 'Model', 'Object ID', 'User', 
        'IP Address', 'Changes Summary'
    ])
    
    # Write data
    for log in queryset:
        changes_summary = ''
        if log.changes:
            if log.operation == 'create':
                changes_summary = 'Object created'
            elif log.operation == 'update':
                changed_fields = log.changes.get('changed_fields', [])
                changes_summary = f"Updated fields: {', '.join(changed_fields)}" if changed_fields else 'Updated'
            elif log.operation == 'delete':
                changes_summary = 'Object deleted'
            elif log.operation == 'payment':
                amount = log.changes.get('amount', 'N/A')
                method = log.changes.get('payment_method', 'N/A')
                changes_summary = f"Payment: {amount} via {method}"
            elif log.operation == 'bulk_operation':
                operation_type = log.changes.get('operation_type', 'N/A')
                affected_count = log.changes.get('affected_count', 0)
                changes_summary = f"Bulk {operation_type}: {affected_count} objects"
        
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.get_operation_display(),
            log.get_model_name_display(),
            log.object_id,
            log.user.get_full_name() if log.user else 'System',
            log.ip_address or '',
            changes_summary
        ])
    
    return response


# AJAX endpoints for audit log filtering and search

@login_required
def audit_logs_ajax(request):
    """AJAX endpoint for filtered audit logs"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Get filter parameters
        filters = {
            'operation': request.GET.get('operation'),
            'model_name': request.GET.get('model_name'),
            'user_id': request.GET.get('user_id'),
            'date_from': request.GET.get('date_from'),
            'date_to': request.GET.get('date_to'),
            'search_term': request.GET.get('search_term'),
            'object_id': request.GET.get('object_id'),
        }
        
        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}
        
        # Get filtered results
        audit_logs = AuditLogSearchService.search_logs(filters)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 25))
        
        paginator = Paginator(audit_logs, per_page)
        audit_logs_page = paginator.get_page(page)
        
        # Convert to JSON-serializable format
        logs_data = []
        for log in audit_logs_page:
            logs_data.append({
                'id': log.id,
                'operation': log.operation,
                'operation_display': log.get_operation_display(),
                'model_name': log.model_name,
                'model_name_display': log.get_model_name_display(),
                'object_id': log.object_id,
                'user': log.user.get_full_name() if log.user else 'System',
                'timestamp': log.timestamp.isoformat(),
                'changes': log.changes,
                'ip_address': log.ip_address,
            })
        
        return JsonResponse({
            'logs': logs_data,
            'pagination': {
                'current_page': audit_logs_page.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_previous': audit_logs_page.has_previous(),
                'has_next': audit_logs_page.has_next(),
                'previous_page': audit_logs_page.previous_page_number() if audit_logs_page.has_previous() else None,
                'next_page': audit_logs_page.next_page_number() if audit_logs_page.has_next() else None,
            }
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def audit_search_suggestions_ajax(request):
    """AJAX endpoint for audit search suggestions"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'suggestions': []})
        
        suggestions = []
        
        # Search in user names
        users = User.objects.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(username__icontains=query)
        ).distinct()[:5]
        
        for user in users:
            suggestions.append({
                'type': 'user',
                'label': f"User: {user.get_full_name() or user.username}",
                'value': user.get_full_name() or user.username,
                'filter_field': 'user_id',
                'filter_value': user.id
            })
        
        # Search in changes JSON (limited to avoid performance issues)
        if query.isdigit():
            # If query is numeric, suggest as object ID
            suggestions.append({
                'type': 'object_id',
                'label': f"Object ID: {query}",
                'value': query,
                'filter_field': 'object_id',
                'filter_value': query
            })
        
        return JsonResponse({'suggestions': suggestions})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Notification System Views

@login_required
def notification_dashboard(request):
    """
    Notification system dashboard with enhanced tracking
    Requirements: 8.5, 8.7 - Notification templates and tracking
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    # Initialize tracking service
    tracking_service = NotificationTrackingService()
    
    # Get comprehensive statistics
    stats = tracking_service.get_delivery_statistics(days=30)
    health = tracking_service.get_notification_health_score()
    failed_analysis = tracking_service.get_failed_notifications_analysis()
    trends = tracking_service.get_notification_trends(days=30)
    
    # Recent notifications
    recent_notifications = NotificationLog.objects.select_related().order_by('-created_at')[:20]
    
    # Templates
    active_templates = NotificationTemplate.objects.filter(is_active=True).count()
    total_templates = NotificationTemplate.objects.count()
    
    context = {
        # Enhanced statistics
        'total_sent': stats['by_status'].get('sent', 0),
        'total_failed': stats['by_status'].get('failed', 0),
        'total_pending': stats['by_status'].get('pending', 0),
        'total_retry': stats['by_status'].get('retry', 0),
        'success_rate': stats['success_rate'],
        'failure_rate': stats['failure_rate'],
        'avg_delivery_time': stats['average_delivery_time'],
        
        # Health information
        'health_score': health['health_score'],
        'health_status': health['health_status'],
        'health_color': health['health_color'],
        
        # Trends
        'success_trend': trends['trends']['success_rate']['trend'],
        'volume_trend': trends['trends']['volume']['trend'],
        
        # Failed analysis
        'retryable_failed': failed_analysis['retryable_count'],
        'common_errors': failed_analysis['common_errors'][:3],  # Top 3 error types
        
        # Existing data
        'recent_notifications': recent_notifications,
        'type_breakdown': stats['by_type'],
        'active_templates': active_templates,
        'total_templates': total_templates,
        
        # Chart data for dashboard
        'daily_stats': stats['daily_breakdown'][-7:],  # Last 7 days
        'template_performance': stats['template_performance'],
    }
    
    return render(request, 'financial/notifications/dashboard.html', context)


@login_required
def notification_templates(request):
    """
    Manage notification templates
    Requirements: 8.5 - Customizable notification templates
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    templates = NotificationTemplate.objects.all().order_by('template_type', 'name')
    
    context = {
        'templates': templates,
        'template_types': NotificationTemplate.TEMPLATE_TYPES,
    }
    
    return render(request, 'financial/notifications/templates.html', context)


@login_required
def notification_logs(request):
    """
    View notification logs with filtering
    Requirements: 8.7 - Delivery status tracking
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('notification_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Build queryset
    logs = NotificationLog.objects.all()
    
    if status_filter:
        logs = logs.filter(status=status_filter)
    
    if type_filter:
        logs = logs.filter(notification_type=type_filter)
    
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(created_at__date__gte=date_from_parsed)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(created_at__date__lte=date_to_parsed)
        except ValueError:
            pass
    
    if search:
        logs = logs.filter(
            Q(recipient_email__icontains=search) |
            Q(recipient_name__icontains=search) |
            Q(subject__icontains=search)
        )
    
    logs = logs.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unique notification types for filter dropdown
    notification_types = NotificationLog.objects.values_list('notification_type', flat=True).distinct()
    
    context = {
        'page_obj': page_obj,
        'status_choices': NotificationLog.STATUS_CHOICES,
        'notification_types': notification_types,
        'current_filters': {
            'status': status_filter,
            'notification_type': type_filter,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        }
    }
    
    return render(request, 'financial/notifications/logs.html', context)


@login_required
def send_test_notification(request):
    """
    Send test notification
    Requirements: 8.1, 8.2, 8.3, 8.4 - Various notification types
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'error': 'School context required'}, status=400)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    notification_type = request.POST.get('notification_type')
    recipient_email = request.POST.get('recipient_email')
    
    if not notification_type or not recipient_email:
        return JsonResponse({'error': 'Missing required parameters'}, status=400)
    
    service = NotificationService()
    
    try:
        # Create test data based on notification type
        if notification_type == 'payment_reminder':
            # Get a sample student fee for testing
            sample_fee = _school_student_fees(school).filter(status__in=['pending', 'partial']).first()
            if not sample_fee:
                return JsonResponse({'error': 'No sample fee found for testing'}, status=400)
            
            # Temporarily change email for testing
            original_email = sample_fee.student.user.email
            sample_fee.student.user.email = recipient_email
            sample_fee.student.user.save()
            
            success = service.send_payment_reminder(sample_fee)
            
            # Restore original email
            sample_fee.student.user.email = original_email
            sample_fee.student.user.save()
            
        elif notification_type == 'payment_confirmation':
            # Get a sample payment for testing
            sample_payment = _school_fee_payments(school).first()
            if not sample_payment:
                return JsonResponse({'error': 'No sample payment found for testing'}, status=400)
            
            # Temporarily change email for testing
            original_email = sample_payment.student_fee.student.user.email
            sample_payment.student_fee.student.user.email = recipient_email
            sample_payment.student_fee.student.user.save()
            
            success = service.send_payment_confirmation(sample_payment)
            
            # Restore original email
            sample_payment.student_fee.student.user.email = original_email
            sample_payment.student_fee.student.user.save()
            
        elif notification_type == 'scholarship_award':
            # Get a sample scholarship recipient for testing
            sample_recipient = _school_scholarship_recipients(school).filter(status='active').first()
            if not sample_recipient:
                return JsonResponse({'error': 'No sample scholarship recipient found for testing'}, status=400)
            
            # Temporarily change email for testing
            original_email = sample_recipient.student.user.email
            sample_recipient.student.user.email = recipient_email
            sample_recipient.student.user.save()
            
            success = service.send_scholarship_award_notification(sample_recipient)
            
            # Restore original email
            sample_recipient.student.user.email = original_email
            sample_recipient.student.user.save()
            
        elif notification_type == 'payroll_processing':
            # Get a sample payroll for testing
            sample_payroll = _school_payrolls(school).first()
            if not sample_payroll:
                return JsonResponse({'error': 'No sample payroll found for testing'}, status=400)
            
            # Temporarily change email for testing
            original_email = sample_payroll.teacher.user.email
            sample_payroll.teacher.user.email = recipient_email
            sample_payroll.teacher.user.save()
            
            success = service.send_payroll_processing_notification(sample_payroll)
            
            # Restore original email
            sample_payroll.teacher.user.email = original_email
            sample_payroll.teacher.user.save()
            
        else:
            return JsonResponse({'error': 'Invalid notification type'}, status=400)
        
        if success:
            return JsonResponse({'success': True, 'message': 'Test notification sent successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Failed to send test notification'})
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def retry_failed_notifications_ajax(request):
    """
    AJAX endpoint to retry failed notifications
    Requirements: 8.7 - Retry mechanisms for failed deliveries
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    service = NotificationService()
    
    try:
        results = service.retry_failed_notifications()
        return JsonResponse({
            'success': True,
            'message': f"Retry completed: {results['succeeded']} succeeded, {results['failed']} failed",
            'results': results
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def send_bulk_reminders_ajax(request):
    """
    AJAX endpoint to send bulk payment reminders
    Requirements: 8.1, 8.6 - Payment reminders and automated notifications
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    reminder_type = request.POST.get('reminder_type', 'upcoming')
    days_ahead = int(request.POST.get('days_ahead', 7))
    days_overdue = int(request.POST.get('days_overdue', 1))
    
    service = NotificationService()
    
    try:
        if reminder_type == 'upcoming':
            results = service.send_bulk_upcoming_due_reminders(days_ahead=days_ahead)
            message = f"Upcoming payment reminders: {results['sent']} sent, {results['failed']} failed"
        elif reminder_type == 'overdue':
            results = service.send_bulk_overdue_reminders(days_overdue=days_overdue)
            message = f"Overdue payment reminders: {results['sent']} sent, {results['failed']} failed"
        else:
            return JsonResponse({'error': 'Invalid reminder type'}, status=400)
        
        return JsonResponse({
            'success': True,
            'message': message,
            'results': results
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def notification_statistics_ajax(request):
    """
    AJAX endpoint for enhanced notification statistics
    Requirements: 8.7 - Delivery status tracking
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Get parameters
    days = int(request.GET.get('days', 30))
    report_type = request.GET.get('report_type', 'summary')
    
    tracking_service = NotificationTrackingService()
    
    try:
        if report_type == 'summary':
            data = tracking_service.get_delivery_statistics(days=days)
        elif report_type == 'health':
            data = tracking_service.get_notification_health_score()
        elif report_type == 'failed_analysis':
            data = tracking_service.get_failed_notifications_analysis()
        elif report_type == 'trends':
            data = tracking_service.get_notification_trends(days=days)
        elif report_type == 'full_report':
            data = tracking_service.generate_notification_report(days=days)
        else:
            return JsonResponse({'error': 'Invalid report type'}, status=400)
        
        return JsonResponse(data)
    
    except Exception as e:
        logger.error(f"Error generating notification statistics: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def notification_cleanup_ajax(request):
    """
    AJAX endpoint for cleaning up old notification logs
    Requirements: 8.7 - Delivery status tracking
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    days_old = int(request.POST.get('days_old', 90))
    
    tracking_service = NotificationTrackingService()
    
    try:
        result = tracking_service.schedule_notification_cleanup(days_old=days_old)
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'deleted_count': result['deleted']
        })
    except Exception as e:
        logger.error(f"Error cleaning up notifications: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# Report Generation and Customization Views
# Requirements: 9.6, 9.7 - Report customization and visualization

from .services_reports import ReportService
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.serializers.json import DjangoJSONEncoder

@login_required
def report_customization_options(request, report_type):
    """
    Get customization options for a specific report type
    Requirements: 9.6 - Report customization functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        options = ReportCustomizationService.get_available_customization_options(report_type)
        chart_configs = ReportCustomizationService.get_default_chart_configs(report_type)
        
        return JsonResponse({
            'success': True,
            'options': options,
            'chart_configs': [config.to_dict() for config in chart_configs]
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def create_scheduled_report(request):
    """
    Create a new scheduled report
    Requirements: 9.7 - Report scheduling functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        try:
            name = request.POST.get('report_name')
            description = request.POST.get('description', '')
            report_type = request.POST.get('report_type')
            frequency = request.POST.get('frequency')
            recipients_str = request.POST.get('recipients', '')
            
            # Parse recipients
            recipients = [email.strip() for email in recipients_str.split(',') if email.strip()]
            
            # Build parameters
            parameters = {}
            for key, value in request.POST.items():
                if key not in ['csrfmiddlewaretoken', 'name', 'description', 'report_type', 'frequency', 'recipients']:
                    if value:  # Only include non-empty values
                        parameters[key] = value
            
            # Create scheduled report
            scheduled_report = ReportCustomizationService.create_scheduled_report(
                name=name,
                report_type=report_type,
                parameters=parameters,
                frequency=frequency,
                recipients=recipients,
                user=request.user,
                description=description
            )
            
            messages.success(request, f'Scheduled report "{name}" created successfully.')
            return redirect('financial:scheduled_reports_list')
            
        except ValueError as e:
            messages.error(request, f'Validation error: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error creating scheduled report: {str(e)}')
    
    return redirect('financial:scheduled_reports_list')

@login_required
def update_scheduled_report(request, report_id):
    """
    Update an existing scheduled report
    Requirements: 9.7 - Report scheduling functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            updates = {}
            
            # Get fields to update
            if request.POST.get('name'):
                updates['name'] = request.POST.get('name')
            if request.POST.get('description'):
                updates['description'] = request.POST.get('description')
            if request.POST.get('frequency'):
                updates['frequency'] = request.POST.get('frequency')
            if request.POST.get('recipients'):
                recipients_str = request.POST.get('recipients')
                updates['recipients'] = [email.strip() for email in recipients_str.split(',') if email.strip()]
            if 'is_active' in request.POST:
                updates['is_active'] = request.POST.get('is_active') == 'true'
            
            # Update parameters if provided
            parameters = {}
            for key, value in request.POST.items():
                if key.startswith('param_') and value:
                    param_name = key.replace('param_', '')
                    parameters[param_name] = value
            
            if parameters:
                updates['parameters'] = parameters
            
            # Update the scheduled report
            scheduled_report = ReportCustomizationService.update_scheduled_report(report_id, **updates)
            
            return JsonResponse({
                'success': True,
                'message': 'Scheduled report updated successfully',
                'next_run': scheduled_report.next_run.isoformat()
            })
            
        except ScheduledReport.DoesNotExist:
            return JsonResponse({'error': 'Scheduled report not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def delete_scheduled_report(request, report_id):
    """
    Delete a scheduled report
    Requirements: 9.7 - Report scheduling functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            scheduled_report = ScheduledReport.objects.get(id=report_id)
            report_name = scheduled_report.name
            scheduled_report.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Scheduled report "{report_name}" deleted successfully'
            })
            
        except ScheduledReport.DoesNotExist:
            return JsonResponse({'error': 'Scheduled report not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def run_scheduled_report_now(request, report_id):
    """
    Execute a scheduled report immediately
    Requirements: 9.7 - Report scheduling functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            scheduled_report = ScheduledReport.objects.get(id=report_id)
            
            # Create execution record
            execution = ReportExecution.objects.create(
                scheduled_report=scheduled_report,
                status='running'
            )
            
            try:
                # Generate the report
                start_time = timezone.now()
                report_data = ReportService.generate_custom_report(
                    scheduled_report.report_type,
                    **scheduled_report.parameters
                )
                end_time = timezone.now()
                
                # Update execution record
                execution.status = 'success'
                execution.execution_time = end_time - start_time
                execution.report_data = report_data
                execution.save()
                
                # Update scheduled report
                scheduled_report.last_run = timezone.now()
                scheduled_report.save()
                
                # In a real implementation, you would also send the report via email
                # to the recipients listed in scheduled_report.recipients
                
                return JsonResponse({
                    'success': True,
                    'message': f'Report "{scheduled_report.name}" executed successfully',
                    'execution_id': execution.id,
                    'execution_time': str(execution.execution_time)
                })
                
            except Exception as e:
                # Update execution record with error
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.save()
                raise
                
        except ScheduledReport.DoesNotExist:
            return JsonResponse({'error': 'Scheduled report not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def report_execution_history(request, report_id):
    """
    Get execution history for a scheduled report
    Requirements: 9.7 - Report scheduling functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        scheduled_report = ScheduledReport.objects.get(id=report_id)
        executions = scheduled_report.executions.all()[:20]  # Last 20 executions
        
        execution_data = []
        for execution in executions:
            execution_data.append({
                'id': execution.id,
                'executed_at': execution.executed_at.isoformat(),
                'status': execution.status,
                'error_message': execution.error_message,
                'execution_time': str(execution.execution_time) if execution.execution_time else None
            })
        
        return JsonResponse({
            'success': True,
            'executions': execution_data
        })
        
    except ScheduledReport.DoesNotExist:
        return JsonResponse({'error': 'Scheduled report not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def report_templates_list(request):
    """
    Get available report templates
    Requirements: 9.6 - Report customization functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        templates = ReportCustomizationService.get_report_templates()
        
        return JsonResponse({
            'success': True,
            'templates': templates
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def create_report_from_template(request, template_key):
    """
    Create a scheduled report from a template
    Requirements: 9.6, 9.7 - Report customization and scheduling
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            templates = ReportCustomizationService.get_report_templates()
            
            if template_key not in templates:
                return JsonResponse({'error': 'Template not found'}, status=404)
            
            template = templates[template_key]
            
            # Get additional parameters from request
            recipients_str = request.POST.get('recipients', '')
            recipients = [email.strip() for email in recipients_str.split(',') if email.strip()]
            
            if not recipients:
                return JsonResponse({'error': 'At least one recipient email is required'}, status=400)
            
            # Create scheduled report from template
            scheduled_report = ReportCustomizationService.create_scheduled_report(
                name=template['name'],
                report_type=template['report_type'],
                parameters=template['parameters'],
                frequency=template['frequency'],
                recipients=recipients,
                user=request.user,
                description=template['description']
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Scheduled report created from template: {template["name"]}',
                'report_id': scheduled_report.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def validate_report_parameters(request):
    """
    Validate report parameters before creating/updating scheduled report
    Requirements: 9.6 - Report customization functionality
    """
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            report_type = request.POST.get('report_type')
            
            if not report_type:
                return JsonResponse({'error': 'Report type is required'}, status=400)
            
            # Build parameters from request
            parameters = {}
            for key, value in request.POST.items():
                if key not in ['csrfmiddlewaretoken', 'report_type'] and value:
                    parameters[key] = value
            
            # Validate parameters
            errors = ReportCustomizationService.validate_report_parameters(report_type, parameters)
            
            return JsonResponse({
                'success': len(errors) == 0,
                'errors': errors,
                'parameters': parameters
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def edit_scholarship(request, scholarship_id):
    """Edit existing scholarship"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    scholarship = get_object_or_404(Scholarship.all_objects.filter(school=school), id=scholarship_id)
    
    sessions = existing_session_choices(school=school, include=[scholarship.academic_year])
    if request.method == 'POST':
        try:
            academic_year = request.POST.get('academic_year')
            if academic_year not in dict(sessions):
                raise ValidationError('Select an academic session configured under school terms.')
            scholarship.name = request.POST.get('name')
            scholarship.scholarship_type = request.POST.get('scholarship_type')
            scholarship.description = request.POST.get('description', '')
            scholarship.amount = request.POST.get('amount') or 0
            scholarship.percentage = request.POST.get('percentage') or None
            scholarship.max_recipients = request.POST.get('max_recipients', 1)
            scholarship.academic_year = academic_year
            scholarship.save()
            for recipient in scholarship.scholarshiprecipient_set.filter(student__school=school, status='active'):
                sync_scholarship_fee_applications(recipient)
        except (ValidationError, ValueError) as exc:
            messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Scholarship updated successfully')
            return redirect('financial:scholarship_management')
    
    return render(request, 'financial/edit_scholarship.html', {'scholarship': scholarship, 'sessions': sessions})


@login_required
def delete_scholarship(request, scholarship_id):
    """Delete scholarship"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = getattr(request, 'school', None)
    if not school:
        return JsonResponse({'success': False, 'error': 'School context required.'}, status=400)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required.'}, status=405)

    scholarship = get_object_or_404(Scholarship.all_objects.filter(school=school), id=scholarship_id)
    for recipient in scholarship.scholarshiprecipient_set.filter(student__school=school):
        clear_scholarship_fee_applications(recipient)
    scholarship.delete()
    return JsonResponse({'success': True})


@login_required
def assign_scholarship(request, scholarship_id):
    """Assign scholarship to student"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    scholarship = get_object_or_404(Scholarship.all_objects.filter(school=school), id=scholarship_id)
    students = active_students(school).select_related('user', 'school_class')
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        
        if not scholarship.is_active:
            messages.error(request, 'This scholarship is inactive and cannot be assigned.')
            return redirect('financial:scholarship_management')

        student = get_object_or_404(students, id=student_id)

        if _school_scholarship_recipients(school).filter(scholarship=scholarship, student=student).exists():
            messages.error(request, 'This student already has this scholarship')
            return render(request, 'financial/assign_scholarship.html', {'scholarship': scholarship, 'students': students})
        
        awarded_amount = Decimal(request.POST.get('awarded_amount'))
        start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
        end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()

        if awarded_amount <= 0:
            messages.error(request, 'Awarded amount must be greater than zero.')
            return redirect('financial:assign_scholarship', scholarship_id=scholarship.id)
        if scholarship.amount and awarded_amount > scholarship.amount:
            messages.error(request, 'Awarded amount cannot exceed the scholarship amount.')
            return redirect('financial:assign_scholarship', scholarship_id=scholarship.id)
        if end_date < start_date:
            messages.error(request, 'End date must be on or after the start date.')
            return redirect('financial:assign_scholarship', scholarship_id=scholarship.id)
        if scholarship.scholarshiprecipient_set.filter(student__school=school, status='active').count() >= scholarship.max_recipients:
            messages.error(request, 'This scholarship has reached its maximum number of recipients.')
            return redirect('financial:scholarship_management')

        try:
            recipient = ScholarshipRecipient.all_objects.create(
                scholarship=scholarship,
                student=student,
                awarded_amount=awarded_amount,
                start_date=start_date,
                end_date=end_date,
                status='active'
            )
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('financial:scholarship_management')
        
        applications = sync_scholarship_fee_applications(recipient)
        
        messages.success(request, f'Scholarship assigned with {len(applications)} fee discount application(s).')
        return redirect('financial:scholarship_management')
    
    return render(request, 'financial/assign_scholarship.html', {'scholarship': scholarship, 'students': students})


@login_required
def revoke_scholarship(request, recipient_id):
    """Revoke scholarship from student"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    recipient = get_object_or_404(_school_scholarship_recipients(school), id=recipient_id)
    
    clear_scholarship_fee_applications(recipient)
    recipient.status = 'completed'
    recipient.save()
    messages.success(request, 'Scholarship revoked and removed from student fees')
    return redirect('financial:scholarship_management')


@login_required
def view_scholarship_recipient(request, recipient_id):
    """View scholarship recipient details"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    recipient = get_object_or_404(_school_scholarship_recipients(school).select_related('student__user', 'scholarship'), id=recipient_id)
    applications = recipient.fee_applications.filter(student_fee__student__school=school).select_related('student_fee__fee_structure__term')
    return render(request, 'financial/view_scholarship_recipient.html', {
        'recipient': recipient,
        'applications': applications,
    })




@login_required
def delete_scholarship_recipient(request, recipient_id):
    """Permanently delete scholarship recipient"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    recipient = get_object_or_404(_school_scholarship_recipients(school), id=recipient_id)
    clear_scholarship_fee_applications(recipient)
    recipient.delete()
    messages.success(request, 'Scholarship recipient deleted permanently')
    return redirect('financial:scholarship_management')







# Enhanced Payroll Management Views

@login_required
def assign_staff_payroll_structure(request):
    """Assign payroll structure to individual staff"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        structure_id = request.POST.get('payroll_structure_id')
        month = datetime.strptime(request.POST.get('month'), '%Y-%m').date()
        
        teacher = get_object_or_404(Teacher.all_objects.filter(school=school), id=teacher_id)
        structure = get_object_or_404(PayrollStructure.all_objects.filter(school=school), id=structure_id)
        
        # Check if payroll already exists
        if _school_payrolls(school).filter(teacher=teacher, month=month).exists():
            messages.error(request, f'Payroll for {teacher.user.get_full_name()} already exists for {month.strftime("%B %Y")}')
            return redirect('financial:payroll_management')
        
        # Create payroll
        payroll = StaffPayroll.all_objects.create(
            teacher=teacher,
            payroll_structure=structure,
            month=month,
            gross_salary=structure.gross_salary,
            net_salary=0
        )
        payroll.calculate_net_salary()
        
        messages.success(request, f'Payroll assigned to {teacher.user.get_full_name()}')
        return redirect('financial:payroll_management')
    
    teachers = active_staff(school).select_related('user')
    structures = PayrollStructure.all_objects.filter(school=school, is_active=True)
    
    return render(request, 'financial/assign_staff_payroll.html', {
        'teachers': teachers,
        'structures': structures,
        'current_month': timezone.now().date()
    })


@login_required
def edit_staff_salary(request, teacher_id):
    """Edit individual staff salary components"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    teacher = get_object_or_404(Teacher.all_objects.filter(school=school), id=teacher_id)
    
    if request.method == 'POST':
        month = datetime.strptime(request.POST.get('month'), '%Y-%m').date()
        payroll = get_object_or_404(_school_payrolls(school), teacher=teacher, month=month)
        
        # Update salary components
        payroll.gross_salary = request.POST.get('gross_salary', payroll.gross_salary)
        payroll.tax_deduction = request.POST.get('tax_deduction', payroll.tax_deduction)
        payroll.pension_deduction = request.POST.get('pension_deduction', payroll.pension_deduction)
        payroll.other_deductions = request.POST.get('other_deductions', payroll.other_deductions)
        
        # Recalculate net salary
        payroll.net_salary = (
            Decimal(payroll.gross_salary) - 
            Decimal(payroll.tax_deduction) - 
            Decimal(payroll.pension_deduction) - 
            Decimal(payroll.other_deductions)
        )
        payroll.save()
        
        messages.success(request, f'Salary updated for {teacher.user.get_full_name()}')
        return redirect('financial:payroll_management')
    
    # Get recent payrolls for this teacher
    payrolls = _school_payrolls(school).filter(teacher=teacher).order_by('-month')[:6]
    
    return render(request, 'financial/edit_staff_salary.html', {
        'teacher': teacher,
        'payrolls': payrolls
    })


@login_required
def mark_payroll_paid(request, payroll_id):
    """Mark payroll as paid"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = getattr(request, 'school', None)
    if not school and not request.user.is_superuser:
        messages.error(request, 'Select a school first.')
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(_school_payrolls(school), id=payroll_id)
    
    if request.method == 'POST':
        from django.db import transaction
        from .models_loans import TeacherLoan, PayrollDeduction

        with transaction.atomic():
            payroll = _school_payrolls(school).select_for_update().get(id=payroll.id)
            if payroll.is_paid:
                messages.info(request, 'This payroll was already marked as paid.')
                return redirect('financial:payroll_management')

            active_loans = TeacherLoan.objects.select_for_update().filter(
                teacher=payroll.teacher,
                status='active',
                balance__gt=0,
            )
            for loan in active_loans:
                deduction_amount = loan.next_deduction_amount
                _, created = PayrollDeduction.objects.get_or_create(
                    payroll=payroll,
                    loan=loan,
                    defaults={
                        'deduction_type': 'loan',
                        'description': f'Loan #{loan.id} repayment',
                        'amount': deduction_amount,
                    },
                )
                if created:
                    loan.deduct_payment(deduction_amount)

            payroll.is_paid = True
            payroll.payment_date = timezone.now()
            payroll.net_salary = payroll.gross_salary - payroll.total_deductions
            payroll.save(update_fields=['is_paid', 'payment_date', 'net_salary'])

        messages.success(request, f'Payroll marked as paid for {payroll.teacher.user.get_full_name()}')
        return redirect('financial:payroll_management')
    
    return render(request, 'financial/confirm_payroll_payment.html', {'payroll': payroll})


@login_required
def delete_payroll(request, payroll_id):
    """Delete payroll record"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(_school_payrolls(school), id=payroll_id)
    
    if payroll.is_paid:
        messages.error(request, 'Cannot delete paid payroll')
        return redirect('financial:payroll_management')
    
    teacher_name = payroll.teacher.user.get_full_name()
    payroll.delete()
    messages.success(request, f'Payroll deleted for {teacher_name}')
    return redirect('financial:payroll_management')


@login_required
def edit_payroll_structure(request, structure_id):
    """Edit payroll structure"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    structure = get_object_or_404(PayrollStructure.all_objects.filter(school=school), id=structure_id)
    
    if request.method == 'POST':
        structure.name = request.POST.get('name')
        structure.basic_salary = request.POST.get('basic_salary', 0)
        structure.house_allowance = request.POST.get('house_allowance', 0)
        structure.transport_allowance = request.POST.get('transport_allowance', 0)
        structure.medical_allowance = request.POST.get('medical_allowance', 0)
        structure.other_allowances = request.POST.get('other_allowances', 0)
        structure.tax_rate = request.POST.get('tax_rate', 0)
        structure.pension_rate = request.POST.get('pension_rate', 0)
        structure.save()
        
        messages.success(request, 'Payroll structure updated successfully')
        return redirect('financial:payroll_management')
    
    return render(request, 'financial/edit_payroll_structure.html', {'structure': structure})


@login_required
def delete_payroll_structure(request, structure_id):
    """Delete payroll structure"""
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    school = _financial_school_or_redirect(request)
    if not school:
        return redirect('core:dashboard')
    
    structure = get_object_or_404(PayrollStructure.all_objects.filter(school=school), id=structure_id)
    
    # Check if structure is in use
    if _school_payrolls(school).filter(payroll_structure=structure).exists():
        messages.error(request, 'Cannot delete payroll structure that is in use')
        return redirect('financial:payroll_management')
    
    structure_name = structure.name
    structure.delete()
    messages.success(request, f'Payroll structure "{structure_name}" deleted')
    return redirect('financial:payroll_management')





