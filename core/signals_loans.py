from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from .models import StaffPayroll
from .models_loans import TeacherLoan, PayrollDeduction

@receiver(post_save, sender=StaffPayroll)
def auto_deduct_loans(sender, instance, created, **kwargs):
    """Automatically deduct active loans when payroll is created"""
    if created and not instance.is_paid:
        # Get active loans for this teacher
        active_loans = TeacherLoan.objects.filter(
            teacher=instance.teacher,
            status='active',
            balance__gt=0
        )
        
        total_loan_deduction = Decimal('0.00')
        
        for loan in active_loans:
            # Create deduction record
            PayrollDeduction.objects.create(
                payroll=instance,
                deduction_type='loan',
                description=f'Loan Repayment - {loan.description or "Loan"}',
                amount=loan.monthly_deduction
            )
            
            total_loan_deduction += loan.monthly_deduction
            
            # Update loan balance
            loan.balance -= loan.monthly_deduction
            if loan.balance <= 0:
                loan.balance = Decimal('0.00')
                loan.status = 'paid'
            loan.save()
        
        # Update payroll with loan deductions
        if total_loan_deduction > 0:
            instance.other_deductions += total_loan_deduction
            instance.net_salary = instance.gross_salary - instance.tax_deduction - instance.pension_deduction - instance.other_deductions
            # Use update to avoid triggering signal again
            StaffPayroll.objects.filter(id=instance.id).update(
                other_deductions=instance.other_deductions,
                net_salary=instance.net_salary
            )
