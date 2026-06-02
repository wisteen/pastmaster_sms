from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.template.loader import render_to_string
from decimal import Decimal, InvalidOperation
from datetime import datetime
from .models import Teacher, StaffPayroll, PayrollStructure
from .models_loans import TeacherLoan, PayrollDeduction
from .services_notification import NotificationService

@login_required
def teacher_loans(request):
    can_manage_loans = request.user.has_any_role(['super_admin', 'accountant', 'bursar'])
    if not can_manage_loans and not request.user.has_any_role(['subject_teacher', 'class_teacher']):
        return redirect('core:dashboard')
    
    # Show both active and paid loans
    loans = TeacherLoan.objects.select_related('teacher__user').all().order_by('-created_at')
    teachers = Teacher.objects.select_related('user').all()
    if not can_manage_loans:
        loans = loans.filter(teacher__user=request.user)
        teachers = teachers.none()
    
    # Calculate totals for active loans only
    active_loans = loans.filter(status='active')
    
    context = {
        'loans': loans,
        'teachers': teachers,
        'total_loans': active_loans.count(),
        'total_amount': sum(loan.balance for loan in active_loans),
        'can_manage_loans': can_manage_loans,
    }
    return render(request, 'financial/loans/teacher_loans.html', context)

@login_required
def create_loan(request):
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        teacher = get_object_or_404(Teacher, id=request.POST.get('teacher_id'))
        try:
            amount = Decimal(request.POST.get('amount'))
            monthly_deduction = Decimal(request.POST.get('monthly_deduction'))
        except (InvalidOperation, TypeError):
            messages.error(request, 'Enter valid loan and monthly deduction amounts.')
            return redirect('financial:teacher_loans')
        if amount <= 0 or monthly_deduction <= 0:
            messages.error(request, 'Loan and monthly deduction amounts must be greater than zero.')
            return redirect('financial:teacher_loans')
        if monthly_deduction > amount:
            messages.error(request, 'Monthly deduction cannot exceed the loan amount.')
            return redirect('financial:teacher_loans')
        description = request.POST.get('description', '')
        
        TeacherLoan.objects.create(
            teacher=teacher,
            amount=amount,
            monthly_deduction=monthly_deduction,
            balance=amount,
            start_date=timezone.now().date(),
            description=description
        )
        
        messages.success(request, 'Loan created successfully')
        return redirect('financial:teacher_loans')
    
    return redirect('financial:teacher_loans')

@login_required
def add_payroll_deduction(request, payroll_id):
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(StaffPayroll, id=payroll_id)
    
    if request.method == 'POST':
        deduction_type = request.POST.get('deduction_type')
        description = request.POST.get('description')
        amount = Decimal(request.POST.get('amount'))
        
        PayrollDeduction.objects.create(
            payroll=payroll,
            deduction_type=deduction_type,
            description=description,
            amount=amount
        )
        
        # Update payroll
        payroll.other_deductions += amount
        payroll.net_salary = payroll.gross_salary - payroll.total_deductions
        payroll.save()
        
        messages.success(request, 'Deduction added successfully')
        return redirect('financial:payroll_management')
    
    return render(request, 'financial/loans/add_deduction.html', {'payroll': payroll})

@login_required
def generate_payslip(request, payroll_id):
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(StaffPayroll.objects.select_related('teacher__user', 'payroll_structure'), id=payroll_id)
    
    # Get loan deductions from PayrollDeduction records (not active loans)
    loan_deductions = payroll.custom_deductions.filter(deduction_type='loan')
    other_custom_deductions = payroll.custom_deductions.exclude(deduction_type='loan')
    projected_loans = TeacherLoan.objects.none()
    if not loan_deductions.exists() and not payroll.is_paid:
        projected_loans = TeacherLoan.objects.filter(
            teacher=payroll.teacher,
            status='active',
            balance__gt=0,
        )
    
    # Calculate total deductions
    total_loan_deduction = sum(ded.amount for ded in loan_deductions)
    total_other_deduction = sum(ded.amount for ded in other_custom_deductions)
    total_deductions = payroll.total_deductions
    
    # Calculate correct net pay
    correct_net_pay = payroll.gross_salary - total_deductions
    
    context = {
        'payroll': payroll,
        'loan_deductions': loan_deductions,
        'projected_loans': projected_loans,
        'other_custom_deductions': other_custom_deductions,
        'total_loan_deduction': total_loan_deduction,
        'total_deductions': total_deductions,
        'correct_net_pay': correct_net_pay,
        'generated_date': timezone.now()
    }
    
    return render(request, 'financial/payslip.html', context)

@login_required
def send_payslip_email(request, payroll_id):
    if not request.user.has_any_role(['super_admin', 'accountant', 'bursar']):
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(StaffPayroll.objects.select_related('teacher__user', 'payroll_structure'), id=payroll_id)
    
    # Get loan deductions from PayrollDeduction records (not active loans)
    loan_deductions = payroll.custom_deductions.filter(deduction_type='loan')
    other_custom_deductions = payroll.custom_deductions.exclude(deduction_type='loan')
    projected_loans = TeacherLoan.objects.none()
    if not loan_deductions.exists() and not payroll.is_paid:
        projected_loans = TeacherLoan.objects.filter(
            teacher=payroll.teacher,
            status='active',
            balance__gt=0,
        )
    
    # Calculate total deductions
    total_loan_deduction = sum(ded.amount for ded in loan_deductions)
    total_other_deduction = sum(ded.amount for ded in other_custom_deductions)
    total_deductions = payroll.total_deductions
    correct_net_pay = payroll.gross_salary - total_deductions
    
    # Generate HTML content
    html_content = render_to_string('financial/payslip_email.html', {
        'payroll': payroll,
        'loan_deductions': loan_deductions,
        'projected_loans': projected_loans,
        'other_custom_deductions': other_custom_deductions,
        'total_loan_deduction': total_loan_deduction,
        'total_deductions': total_deductions,
        'correct_net_pay': correct_net_pay,
        'generated_date': timezone.now()
    })
    
    # Send email
    service = NotificationService()
    success = service.send_custom_email(
        recipient_email=payroll.teacher.user.email,
        recipient_name=payroll.teacher.user.get_full_name(),
        subject=f'Payslip for {payroll.month.strftime("%B %Y")}',
        html_content=html_content
    )
    
    if success:
        messages.success(request, f'Payslip sent to {payroll.teacher.user.email}')
    else:
        messages.error(request, 'Failed to send payslip')
    
    return redirect('financial:payroll_management')


