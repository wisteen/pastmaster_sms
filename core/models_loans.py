from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class TeacherLoan(models.Model):
    LOAN_STATUS = [
        ('active', 'Active'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ]
    
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, related_name='loans')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    monthly_deduction = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=LOAN_STATUS, default='active')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - ₦{self.amount}"
    
    @property
    def total_paid(self):
        return self.amount - self.balance
    
    @property
    def repayment_percentage(self):
        if self.amount > 0:
            return (self.total_paid / self.amount) * 100
        return 0
    
    def deduct_payment(self, amount):
        """Deduct payment from loan balance"""
        amount = min(self.balance, Decimal(str(amount)))
        self.balance -= amount
        if self.balance <= 0:
            self.balance = Decimal('0')
            self.status = 'paid'
        self.save()
        return amount

    @property
    def next_deduction_amount(self):
        return min(self.balance, self.monthly_deduction)

class PayrollDeduction(models.Model):
    DEDUCTION_TYPE = [
        ('loan', 'Loan Repayment'),
        ('contribution', 'Contribution'),
        ('advance', 'Salary Advance'),
        ('other', 'Other')
    ]
    
    payroll = models.ForeignKey('StaffPayroll', on_delete=models.CASCADE, related_name='custom_deductions')
    loan = models.ForeignKey(
        TeacherLoan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll_deductions',
    )
    deduction_type = models.CharField(max_length=20, choices=DEDUCTION_TYPE)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['payroll', 'loan'],
                condition=models.Q(loan__isnull=False),
                name='unique_payroll_loan_deduction',
            ),
        ]
    
    def __str__(self):
        return f"{self.get_deduction_type_display()} - ₦{self.amount}"
