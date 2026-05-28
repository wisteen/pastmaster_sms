from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.template.loader import render_to_string
from decimal import Decimal
from datetime import datetime
from .models import Teacher, StaffPayroll, PayrollStructure
from .models_loans import TeacherLoan, PayrollDeduction
from .services_notification import NotificationService

@login_required
def teacher_loans(request):
    if not request.user.has_any_role(['super_admin']):
        return redirect('core:dashboard')
    
    # Show both active and paid loans
    loans = TeacherLoan.objects.select_related('teacher__user').all().order_by('-created_at')
    teachers = Teacher.objects.select_related('user').all()
    
    # Calculate totals for active loans only
    active_loans = loans.filter(status='active')
    
    context = {
        'loans': loans,
        'teachers': teachers,
        'total_loans': active_loans.count(),
        'total_amount': sum(loan.balance for loan in active_loans)
    }
    return render(request, 'financial/loans/teacher_loans.html', context)

@login_required
def create_loan(request):
    if not request.user.has_any_role(['super_admin']):
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        teacher_id = request.POST.get('teacher_id')
        amount = Decimal(request.POST.get('amount'))
        monthly_deduction = Decimal(request.POST.get('monthly_deduction'))
        description = request.POST.get('description', '')
        
        TeacherLoan.objects.create(
            teacher_id=teacher_id,
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
    if not request.user.has_any_role(['super_admin']):
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
        payroll.net_salary = payroll.gross_salary - payroll.tax_deduction - payroll.pension_deduction - payroll.other_deductions
        payroll.save()
        
        messages.success(request, 'Deduction added successfully')
        return redirect('financial:payroll_management')
    
    return render(request, 'financial/loans/add_deduction.html', {'payroll': payroll})

@login_required
def generate_payslip(request, payroll_id):
    if not request.user.has_any_role(['super_admin']):
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(StaffPayroll.objects.select_related('teacher__user', 'payroll_structure'), id=payroll_id)
    
    # Get loan deductions from PayrollDeduction records (not active loans)
    loan_deductions = payroll.custom_deductions.filter(deduction_type='loan')
    other_custom_deductions = payroll.custom_deductions.exclude(deduction_type='loan')
    
    # Calculate total deductions
    total_loan_deduction = sum(ded.amount for ded in loan_deductions)
    total_other_deduction = sum(ded.amount for ded in other_custom_deductions)
    total_deductions = payroll.tax_deduction + payroll.pension_deduction + total_other_deduction + total_loan_deduction
    
    # Calculate correct net pay
    correct_net_pay = payroll.gross_salary - total_deductions
    
    context = {
        'payroll': payroll,
        'loan_deductions': loan_deductions,
        'other_custom_deductions': other_custom_deductions,
        'total_loan_deduction': total_loan_deduction,
        'total_deductions': total_deductions,
        'correct_net_pay': correct_net_pay,
        'generated_date': timezone.now()
    }
    
    return render(request, 'financial/payslip.html', context)

@login_required
def send_payslip_email(request, payroll_id):
    if not request.user.has_any_role(['super_admin']):
        return redirect('core:dashboard')
    
    payroll = get_object_or_404(StaffPayroll.objects.select_related('teacher__user', 'payroll_structure'), id=payroll_id)
    
    # Get loan deductions from PayrollDeduction records (not active loans)
    loan_deductions = payroll.custom_deductions.filter(deduction_type='loan')
    other_custom_deductions = payroll.custom_deductions.exclude(deduction_type='loan')
    
    # Calculate total deductions
    total_loan_deduction = sum(ded.amount for ded in loan_deductions)
    total_other_deduction = sum(ded.amount for ded in other_custom_deductions)
    total_deductions = payroll.tax_deduction + payroll.pension_deduction + total_other_deduction + total_loan_deduction
    correct_net_pay = payroll.gross_salary - total_deductions
    
    # Generate HTML content
    html_content = render_to_string('financial/payslip_email.html', {
        'payroll': payroll,
        'loan_deductions': loan_deductions,
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


