from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from .models import (
    FeeStructure, StudentFee, FeePayment, Scholarship, 
    ScholarshipRecipient, PayrollStructure, StaffPayroll,
    Teacher, Student, SchoolClass, Term
)


class FinancialBaseForm(forms.ModelForm):
    """Base form with common financial validation"""
    
    def clean_amount_field(self, field_name):
        """Common validation for monetary fields"""
        amount = self.cleaned_data.get(field_name)
        if amount is not None:
            if amount < 0:
                raise ValidationError("Amount cannot be negative.")
            if amount > Decimal('999999.99'):
                raise ValidationError("Amount exceeds maximum allowed value.")
        return amount

    def clean_percentage_field(self, field_name):
        """Common validation for percentage fields"""
        percentage = self.cleaned_data.get(field_name)
        if percentage is not None:
            if percentage < 0 or percentage > 100:
                raise ValidationError("Percentage must be between 0 and 100.")
        return percentage


class FeeStructureForm(FinancialBaseForm):
    """Enhanced form for fee structure with monetary and uniqueness validation"""
    
    class Meta:
        model = FeeStructure
        fields = [
            'name', 'school_class', 'term', 'tuition_fee', 'development_fee',
            'exam_fee', 'library_fee', 'sports_fee', 'other_fees', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter fee structure name'
            }),
            'school_class': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'tuition_fee': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'development_fee': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'exam_fee': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'library_fee': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'sports_fee': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'other_fees': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_tuition_fee(self):
        return self.clean_amount_field('tuition_fee')

    def clean_development_fee(self):
        return self.clean_amount_field('development_fee')

    def clean_exam_fee(self):
        return self.clean_amount_field('exam_fee')

    def clean_library_fee(self):
        return self.clean_amount_field('library_fee')

    def clean_sports_fee(self):
        return self.clean_amount_field('sports_fee')

    def clean_other_fees(self):
        return self.clean_amount_field('other_fees')

    def clean(self):
        cleaned_data = super().clean()
        school_class = cleaned_data.get('school_class')
        term = cleaned_data.get('term')
        
        if school_class and term:
            # Check for duplicate fee structure
            existing = FeeStructure.objects.filter(
                school_class=school_class, 
                term=term
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError(
                    "Fee structure already exists for this class and term."
                )
        
        return cleaned_data


class FeePaymentForm(FinancialBaseForm):
    """Enhanced form for fee payment with balance and amount validation"""
    
    class Meta:
        model = FeePayment
        fields = ['student_fee', 'amount', 'payment_method', 'reference_number', 'notes']
        widgets = {
            'student_fee': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter reference number (optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes (optional)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter student fees to show only those with outstanding balance
        self.fields['student_fee'].queryset = StudentFee.objects.filter(
            status__in=['pending', 'partial', 'overdue']
        ).select_related('student', 'fee_structure')

    def clean_amount(self):
        amount = self.clean_amount_field('amount')
        student_fee = self.cleaned_data.get('student_fee')
        
        if amount and student_fee:
            if amount > student_fee.balance_amount:
                raise ValidationError(
                    f"Payment amount (${amount}) exceeds outstanding balance (${student_fee.balance_amount})."
                )
        
        return amount

    def clean_reference_number(self):
        reference_number = self.cleaned_data.get('reference_number')
        payment_method = self.cleaned_data.get('payment_method')
        
        # Require reference number for non-cash payments
        if payment_method in ['bank_transfer', 'card', 'online'] and not reference_number:
            raise ValidationError(
                f"Reference number is required for {payment_method} payments."
            )
        
        return reference_number


class ScholarshipForm(FinancialBaseForm):
    """Enhanced form for scholarship with percentage and amount validation"""
    
    class Meta:
        model = Scholarship
        fields = [
            'name', 'scholarship_type', 'description', 'amount', 'percentage',
            'max_recipients', 'is_active', 'academic_year'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter scholarship name'
            }),
            'scholarship_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the scholarship criteria and benefits'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-field',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'max_recipients': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': '1'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '2024-2025'
            }),
        }

    def clean_amount(self):
        return self.clean_amount_field('amount')

    def clean_percentage(self):
        return self.clean_percentage_field('percentage')

    def clean_max_recipients(self):
        max_recipients = self.cleaned_data.get('max_recipients')
        if max_recipients is not None and max_recipients < 1:
            raise ValidationError("Maximum recipients must be at least 1.")
        return max_recipients

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        percentage = cleaned_data.get('percentage')
        
        if not amount and not percentage:
            raise ValidationError(
                "Either amount or percentage must be specified."
            )
        
        if amount and percentage:
            raise ValidationError(
                "Specify either amount or percentage, not both."
            )
        
        return cleaned_data


class PayrollForm(FinancialBaseForm):
    """Enhanced form for payroll with calculation validation"""
    
    class Meta:
        model = StaffPayroll
        fields = [
            'teacher', 'payroll_structure', 'month', 'other_deductions'
        ]
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'payroll_structure': forms.Select(attrs={'class': 'form-control'}),
            'month': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'month'
            }),
            'other_deductions': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
        }

    def clean_other_deductions(self):
        return self.clean_amount_field('other_deductions')

    def clean_month(self):
        month = self.cleaned_data.get('month')
        if month:
            # Ensure month is not in the future
            if month > timezone.now().date():
                raise ValidationError("Payroll month cannot be in the future.")
            
            # Ensure month is not too far in the past (e.g., more than 2 years)
            two_years_ago = timezone.now().date() - timedelta(days=730)
            if month < two_years_ago:
                raise ValidationError("Payroll month cannot be more than 2 years in the past.")
        
        return month

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        month = cleaned_data.get('month')
        
        if teacher and month:
            # Check for duplicate payroll for same teacher and month
            existing = StaffPayroll.objects.filter(
                teacher=teacher,
                month=month
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError(
                    f"Payroll already exists for {teacher} in {month.strftime('%B %Y')}."
                )
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Calculate payroll amounts based on payroll structure
        if instance.payroll_structure:
            instance.calculate_net_salary()
        
        if commit:
            instance.save()
        
        return instance


class PayrollStructureForm(FinancialBaseForm):
    """Enhanced form for payroll structure with calculation validation"""
    
    class Meta:
        model = PayrollStructure
        fields = [
            'name', 'basic_salary', 'house_allowance', 'transport_allowance',
            'medical_allowance', 'other_allowances', 'tax_rate', 'pension_rate',
            'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter payroll structure name'
            }),
            'basic_salary': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'house_allowance': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'transport_allowance': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'medical_allowance': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'other_allowances': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control percentage-field',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'pension_rate': forms.NumberInput(attrs={
                'class': 'form-control percentage-field',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_basic_salary(self):
        return self.clean_amount_field('basic_salary')

    def clean_house_allowance(self):
        return self.clean_amount_field('house_allowance')

    def clean_transport_allowance(self):
        return self.clean_amount_field('transport_allowance')

    def clean_medical_allowance(self):
        return self.clean_amount_field('medical_allowance')

    def clean_other_allowances(self):
        return self.clean_amount_field('other_allowances')

    def clean_tax_rate(self):
        return self.clean_percentage_field('tax_rate')

    def clean_pension_rate(self):
        return self.clean_percentage_field('pension_rate')

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate that total deduction rates don't exceed 100%
        tax_rate = cleaned_data.get('tax_rate', 0)
        pension_rate = cleaned_data.get('pension_rate', 0)
        
        if tax_rate + pension_rate > 100:
            raise ValidationError(
                "Combined tax and pension rates cannot exceed 100%."
            )
        
        return cleaned_data


class ScholarshipRecipientForm(FinancialBaseForm):
    """Enhanced form for scholarship recipient with date and amount validation"""
    
    class Meta:
        model = ScholarshipRecipient
        fields = [
            'scholarship', 'student', 'awarded_amount', 'start_date', 'end_date',
            'status', 'notes'
        ]
        widgets = {
            'scholarship': forms.Select(attrs={'class': 'form-control'}),
            'student': forms.Select(attrs={'class': 'form-control'}),
            'awarded_amount': forms.NumberInput(attrs={
                'class': 'form-control monetary-field',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes (optional)'
            }),
        }

    def clean_awarded_amount(self):
        return self.clean_amount_field('awarded_amount')

    def clean_end_date(self):
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        
        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")
        
        return end_date

    def clean(self):
        cleaned_data = super().clean()
        scholarship = cleaned_data.get('scholarship')
        student = cleaned_data.get('student')
        awarded_amount = cleaned_data.get('awarded_amount')
        
        if scholarship and awarded_amount:
            # Validate awarded amount against scholarship limits
            if scholarship.amount and awarded_amount > scholarship.amount:
                raise ValidationError(
                    f"Awarded amount cannot exceed scholarship amount of ${scholarship.amount}."
                )
        
        if scholarship and student:
            # Check for duplicate scholarship recipient
            existing = ScholarshipRecipient.objects.filter(
                scholarship=scholarship,
                student=student
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError(
                    f"{student} is already a recipient of {scholarship.name}."
                )
        
        return cleaned_data