from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
from .models import Teacher, StaffPayroll
from .models_biodata import StaffBioData, StaffBankAccount, PaymentSchedule
from .decorators import role_required

@login_required
@role_required(['super_admin', 'accountant'])
def generate_payment_schedule(request):
    if request.method == 'POST':
        month = request.POST.get('month')
        month_date = datetime.strptime(month, '%Y-%m').date()
        
        # Get all staff with payroll and bank accounts
        staff_with_payroll = StaffPayroll.objects.filter(month=month_date).select_related(
            'teacher__user', 'teacher__bio_data__bank_account'
        )
        
        created_count = 0
        for payroll in staff_with_payroll:
            try:
                bank_account = payroll.teacher.bio_data.bank_account
                PaymentSchedule.objects.get_or_create(
                    teacher=payroll.teacher,
                    month=month_date,
                    defaults={
                        'staff_name': payroll.teacher.user.get_full_name(),
                        'bank_name': bank_account.bank_name,
                        'account_number': bank_account.account_number,
                        'amount': payroll.net_salary,
                        'status': 'pending'
                    }
                )
                created_count += 1
            except (StaffBioData.DoesNotExist, StaffBankAccount.DoesNotExist):
                continue
        
        messages.success(request, f'Payment schedule generated for {created_count} staff members')
        return redirect('payment_schedule_list')
    
    return render(request, 'financial/payroll/generate_payment_schedule.html')

@login_required
@role_required(['super_admin', 'accountant'])
def payment_schedule_list(request):
    month = request.GET.get('month')
    status = request.GET.get('status')
    
    schedules = PaymentSchedule.objects.select_related('teacher__user').all()
    
    if month:
        month_date = datetime.strptime(month, '%Y-%m').date()
        schedules = schedules.filter(month=month_date)
    
    if status:
        schedules = schedules.filter(status=status)
    
    context = {
        'schedules': schedules,
        'selected_month': month,
        'selected_status': status
    }
    return render(request, 'financial/payroll/payment_schedule_list.html', context)

@login_required
@role_required(['super_admin', 'accountant'])
def mark_payment_paid(request, schedule_id):
    schedule = get_object_or_404(PaymentSchedule, id=schedule_id)
    
    if request.method == 'POST':
        schedule.status = 'paid'
        schedule.payment_date = timezone.now()
        schedule.reference_number = request.POST.get('reference_number', '')
        schedule.save()
        
        messages.success(request, f'Payment marked as paid for {schedule.staff_name}')
        return redirect('payment_schedule_list')
    
    return render(request, 'financial/payroll/mark_payment_paid.html', {'schedule': schedule})
