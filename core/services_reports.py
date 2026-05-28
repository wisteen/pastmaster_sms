"""
Financial Report Generation Services for Financial Management Enhancement

This module provides comprehensive report generation capabilities for various financial report types
including monthly summaries, fee collection reports, scholarship distribution reports, payroll reports,
and comparative year-over-year reports.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

from django.db.models import Sum, Count, Q, Avg, Max, Min, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import json
from collections import defaultdict, OrderedDict
from .models import (
    StudentFee, FeePayment, FinancialTransaction, Scholarship, 
    ScholarshipRecipient, StaffPayroll, PayrollStructure, Term, SchoolClass,
    Student, Teacher, User
)
from .services_analytics import FinancialAnalyticsService


class ReportService:
    """
    Main service class for generating various types of financial reports
    Provides structured data for reports with customizable parameters
    
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
    """
    
    @staticmethod
    def generate_monthly_financial_summary(year=None, month=None, include_charts=True):
        """
        Generate comprehensive monthly financial summary report
        
        Requirements: 9.1 - Monthly financial summary reports with income, expenses, and profit analysis
        """
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
            
        # Create date range for the month
        report_date = date(year, month, 1)
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        
        # Fee Income Analysis
        fee_payments = FeePayment.objects.filter(
            payment_date__date__gte=report_date,
            payment_date__date__lt=next_month
        )
        
        fee_income_data = fee_payments.aggregate(
            total_amount=Sum('amount'),
            payment_count=Count('id'),
            avg_payment=Avg('amount')
        )
        
        # Payment method breakdown
        payment_methods = fee_payments.values('payment_method').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('-amount')
        
        # Other Income Analysis
        other_income = FinancialTransaction.objects.filter(
            transaction_type='income',
            transaction_date__gte=report_date,
            transaction_date__lt=next_month
        )
        
        other_income_data = other_income.aggregate(
            total_amount=Sum('amount'),
            transaction_count=Count('id')
        )
        
        # Income by category
        income_categories = other_income.values('category').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('-amount')
        
        # Expense Analysis
        expenses = FinancialTransaction.objects.filter(
            transaction_type='expense',
            transaction_date__gte=report_date,
            transaction_date__lt=next_month
        )
        
        expense_data = expenses.aggregate(
            total_amount=Sum('amount'),
            transaction_count=Count('id'),
            avg_expense=Avg('amount')
        )
        
        # Expense by category
        expense_categories = expenses.values('category').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('-amount')
        
        # Payroll Analysis
        payroll_data = StaffPayroll.objects.filter(
            month__gte=report_date,
            month__lt=next_month
        ).aggregate(
            total_gross=Sum('gross_salary'),
            total_net=Sum('net_salary'),
            total_tax=Sum('tax_deduction'),
            total_pension=Sum('pension_deduction'),
            staff_count=Count('id'),
            paid_count=Count('id', filter=Q(is_paid=True))
        )
        
        # Calculate totals and profit - convert all to float immediately
        total_fee_income = float(fee_income_data['total_amount'] or 0)
        total_other_income = float(other_income_data['total_amount'] or 0)
        total_income = total_fee_income + total_other_income
        
        total_expenses = float(expense_data['total_amount'] or 0)
        total_payroll = float(payroll_data['total_net'] or 0)
        total_costs = total_expenses + total_payroll
        
        net_profit = total_income - total_costs
        profit_margin = (float(net_profit) / float(total_income) * 100) if total_income > 0 else 0
        
        # Previous month comparison
        prev_month_date = report_date - timedelta(days=1)
        prev_month_start = prev_month_date.replace(day=1)
        
        prev_month_income = (
            FeePayment.objects.filter(
                payment_date__date__gte=prev_month_start,
                payment_date__date__lt=report_date
            ).aggregate(total=Sum('amount'))['total'] or 0
        ) + (
            FinancialTransaction.objects.filter(
                transaction_type='income',
                transaction_date__gte=prev_month_start,
                transaction_date__lt=report_date
            ).aggregate(total=Sum('amount'))['total'] or 0
        )
        
        income_change = ((float(total_income) - float(prev_month_income)) / float(prev_month_income) * 100) if prev_month_income > 0 else 0
        
        report_data = {
            'report_info': {
                'title': f'Monthly Financial Summary - {report_date.strftime("%B %Y")}',
                'report_date': report_date.isoformat(),
                'generated_at': timezone.now().isoformat(),
                'period': {
                    'start_date': report_date.isoformat(),
                    'end_date': (next_month - timedelta(days=1)).isoformat(),
                    'month_name': report_date.strftime('%B %Y')
                }
            },
            'income_summary': {
                'fee_income': {
                    'total_amount': float(total_fee_income),
                    'payment_count': fee_income_data['payment_count'] or 0,
                    'average_payment': float(fee_income_data['avg_payment'] or 0),
                    'payment_methods': [
                        {
                            'method': method['payment_method'].replace('_', ' ').title(),
                            'amount': float(method['amount']),
                            'count': method['count'],
                            'percentage': (float(method['amount']) / float(total_fee_income) * 100) if total_fee_income > 0 else 0
                        }
                        for method in payment_methods
                    ]
                },
                'other_income': {
                    'total_amount': float(total_other_income),
                    'transaction_count': other_income_data['transaction_count'] or 0,
                    'categories': [
                        {
                            'category': cat['category'].replace('_', ' ').title(),
                            'amount': float(cat['amount']),
                            'count': cat['count'],
                            'percentage': (float(cat['amount']) / float(total_other_income) * 100) if total_other_income > 0 else 0
                        }
                        for cat in income_categories
                    ]
                },
                'total_income': float(total_income),
                'income_change_percent': float(income_change)
            },
            'expense_summary': {
                'operational_expenses': {
                    'total_amount': float(total_expenses),
                    'transaction_count': expense_data['transaction_count'] or 0,
                    'average_expense': float(expense_data['avg_expense'] or 0),
                    'categories': [
                        {
                            'category': cat['category'].replace('_', ' ').title(),
                            'amount': float(cat['amount']),
                            'count': cat['count'],
                            'percentage': (float(cat['amount']) / float(total_expenses) * 100) if total_expenses > 0 else 0
                        }
                        for cat in expense_categories
                    ]
                },
                'payroll_expenses': {
                    'total_gross': float(payroll_data['total_gross'] or 0),
                    'total_net': float(total_payroll),
                    'total_deductions': float((payroll_data['total_tax'] or 0) + (payroll_data['total_pension'] or 0)),
                    'staff_count': payroll_data['staff_count'] or 0,
                    'paid_staff_count': payroll_data['paid_count'] or 0
                },
                'total_expenses': float(total_costs)
            },
            'profit_analysis': {
                'gross_profit': float(total_income),
                'total_costs': float(total_costs),
                'net_profit': float(net_profit),
                'profit_margin_percent': float(profit_margin),
                'profitability_status': 'Profitable' if net_profit > 0 else 'Loss' if net_profit < 0 else 'Break Even'
            }
        }
        
        # Add chart data if requested
        if include_charts:
            report_data['charts'] = {
                'income_breakdown': {
                    'labels': ['Fee Income', 'Other Income'],
                    'data': [float(total_fee_income), float(total_other_income)]
                },
                'expense_breakdown': {
                    'labels': ['Operational', 'Payroll'],
                    'data': [float(total_expenses), float(total_payroll)]
                },
                'profit_trend': FinancialAnalyticsService.get_income_vs_expenses_comparison(months=6)
            }
        
        return report_data
    
    @staticmethod
    def generate_fee_collection_report(term_id=None, class_id=None, status_filter=None, date_range=None):
        """
        Generate comprehensive fee collection report with payment status breakdowns and collection rates
        
        Requirements: 9.2 - Fee collection reports with payment status breakdowns and collection rates
        """
        # Build base queryset
        queryset = StudentFee.objects.select_related('student', 'fee_structure', 'student__school_class')
        
        # Apply filters
        filters = {}
        if term_id:
            filters['fee_structure__term_id'] = term_id
        if class_id:
            filters['student__school_class_id'] = class_id
        if status_filter:
            filters['status'] = status_filter
        if date_range and len(date_range) == 2:
            filters['created_at__date__gte'] = date_range[0]
            filters['created_at__date__lte'] = date_range[1]
        
        if filters:
            queryset = queryset.filter(**filters)
        
        # Overall statistics
        overall_stats = queryset.aggregate(
            total_fees=Count('id'),
            total_amount=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
            total_discount=Sum('discount_amount')
        )
        
        # Calculate balance separately
        total_amount = overall_stats['total_amount'] or 0
        total_paid = overall_stats['total_paid'] or 0
        total_discount = overall_stats['total_discount'] or 0
        overall_stats['total_balance'] = total_amount - total_paid - total_discount
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            discount_amount=Sum('discount_amount')
        ).order_by('status')
        
        # Add balance calculation to each status
        for item in status_breakdown:
            item['balance_amount'] = (item['total_amount'] or 0) - (item['paid_amount'] or 0) - (item['discount_amount'] or 0)
        
        # Class-wise breakdown
        class_breakdown = queryset.values(
            'student__school_class__name'
        ).annotate(
            student_count=Count('student', distinct=True),
            fee_count=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            discount_amount=Sum('discount_amount'),
            paid_fees=Count('id', filter=Q(status='paid')),
            pending_fees=Count('id', filter=Q(status='pending')),
            overdue_fees=Count('id', filter=Q(status='overdue'))
        ).order_by('student__school_class__name')
        
        # Add balance and collection rate to each class
        for item in class_breakdown:
            total = item['total_amount'] or 0
            paid = item['paid_amount'] or 0
            discount = item['discount_amount'] or 0
            item['balance_amount'] = total - paid - discount
            item['collection_rate'] = (float(paid) / float(total) * 100) if total > 0 else 0
        
        # Payment method analysis (from related payments)
        payment_methods = FeePayment.objects.filter(
            student_fee__in=queryset
        ).values('payment_method').annotate(
            amount=Sum('amount'),
            count=Count('id')
        ).order_by('-amount')
        
        # Recent payments
        recent_payments = FeePayment.objects.filter(
            student_fee__in=queryset
        ).select_related(
            'student_fee__student__user',
            'student_fee__student__school_class',
            'received_by'
        ).order_by('-payment_date')[:20]
        
        # Outstanding fees (overdue)
        overdue_fees = queryset.filter(
            status='overdue'
        ).select_related(
            'student__user',
            'student__school_class'
        ).order_by('-due_date')
        
        # Calculate collection rate
        total_amount = overall_stats['total_amount'] or 0
        total_paid = overall_stats['total_paid'] or 0
        collection_rate = (float(total_paid) / float(total_amount) * 100) if total_amount > 0 else 0
        
        report_data = {
            'report_info': {
                'title': 'Fee Collection Report',
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'term_id': term_id,
                    'class_id': class_id,
                    'status_filter': status_filter,
                    'date_range': date_range
                }
            },
            'summary': {
                'total_fees': overall_stats['total_fees'] or 0,
                'total_amount': float(total_amount),
                'total_paid': float(total_paid),
                'total_discount': float(overall_stats['total_discount'] or 0),
                'total_balance': float(overall_stats['total_balance'] or 0),
                'collection_rate_percent': float(collection_rate)
            },
            'status_breakdown': [
                {
                    'status': item['status'].title(),
                    'count': item['count'],
                    'total_amount': float(item['total_amount'] or 0),
                    'paid_amount': float(item['paid_amount'] or 0),
                    'balance_amount': float(item['balance_amount'] or 0),
                    'percentage': (item['count'] / overall_stats['total_fees'] * 100) if overall_stats['total_fees'] > 0 else 0
                }
                for item in status_breakdown
            ],
            'class_breakdown': [
                {
                    'class_name': item['student__school_class__name'],
                    'student_count': item['student_count'],
                    'fee_count': item['fee_count'],
                    'total_amount': float(item['total_amount'] or 0),
                    'paid_amount': float(item['paid_amount'] or 0),
                    'balance_amount': float(item['balance_amount'] or 0),
                    'collection_rate': (float(item['paid_amount'] or 0) / float(item['total_amount']) * 100) if item['total_amount'] else 0,
                    'paid_fees': item['paid_fees'],
                    'pending_fees': item['pending_fees'],
                    'overdue_fees': item['overdue_fees']
                }
                for item in class_breakdown
            ],
            'payment_methods': [
                {
                    'method': method['payment_method'].replace('_', ' ').title(),
                    'amount': float(method['amount']),
                    'count': method['count'],
                    'percentage': (float(method['amount']) / float(total_paid) * 100) if total_paid > 0 else 0
                }
                for method in payment_methods
            ],
            'recent_payments': [
                {
                    'student_name': payment.student_fee.student.user.get_full_name(),
                    'student_id': payment.student_fee.student.student_id,
                    'class_name': payment.student_fee.student.school_class.name,
                    'amount': float(payment.amount),
                    'payment_method': payment.get_payment_method_display(),
                    'payment_date': payment.payment_date.isoformat(),
                    'received_by': payment.received_by.get_full_name() if payment.received_by else 'System'
                }
                for payment in recent_payments
            ],
            'overdue_fees': [
                {
                    'student_name': fee.student.user.get_full_name(),
                    'student_id': fee.student.student_id,
                    'class_name': fee.student.school_class.name,
                    'total_amount': float(fee.total_amount),
                    'paid_amount': float(fee.paid_amount),
                    'balance_amount': float(fee.balance_amount),
                    'due_date': fee.due_date.isoformat(),
                    'days_overdue': (timezone.now().date() - fee.due_date).days
                }
                for fee in overdue_fees
            ]
        }
        
        return report_data
    
    @staticmethod
    def generate_scholarship_distribution_report(academic_year=None, scholarship_type=None):
        """
        Generate scholarship distribution report with recipient demographics and award amounts
        
        Requirements: 9.3 - Scholarship distribution reports with recipient demographics and award amounts
        """
        # Build base queryset
        queryset = ScholarshipRecipient.objects.select_related(
            'scholarship', 'student__user', 'student__school_class'
        )
        
        # Apply filters
        if academic_year:
            queryset = queryset.filter(scholarship__academic_year=academic_year)
        if scholarship_type:
            queryset = queryset.filter(scholarship__scholarship_type=scholarship_type)
        
        # Overall statistics
        overall_stats = queryset.aggregate(
            total_recipients=Count('id'),
            total_awarded=Sum('awarded_amount'),
            avg_award=Avg('awarded_amount'),
            active_recipients=Count('id', filter=Q(status='active'))
        )
        
        # Scholarship type breakdown
        type_breakdown = queryset.values(
            'scholarship__scholarship_type'
        ).annotate(
            recipient_count=Count('id'),
            total_amount=Sum('awarded_amount'),
            avg_amount=Avg('awarded_amount'),
            active_count=Count('id', filter=Q(status='active'))
        ).order_by('-total_amount')
        
        # Academic year breakdown
        year_breakdown = queryset.values(
            'scholarship__academic_year'
        ).annotate(
            recipient_count=Count('id'),
            scholarship_count=Count('scholarship', distinct=True),
            total_amount=Sum('awarded_amount'),
            active_count=Count('id', filter=Q(status='active'))
        ).order_by('-scholarship__academic_year')
        
        # Class-wise distribution
        class_breakdown = queryset.values(
            'student__school_class__name'
        ).annotate(
            recipient_count=Count('id'),
            total_amount=Sum('awarded_amount'),
            avg_amount=Avg('awarded_amount'),
            active_count=Count('id', filter=Q(status='active'))
        ).order_by('student__school_class__name')
        
        # Top scholarships by amount
        top_scholarships = Scholarship.objects.annotate(
            total_awarded=Sum('scholarshiprecipient__awarded_amount'),
            recipient_count=Count('scholarshiprecipient'),
            active_recipients=Count('scholarshiprecipient', filter=Q(scholarshiprecipient__status='active'))
        ).filter(total_awarded__gt=0).order_by('-total_awarded')[:10]
        
        # Recent awards
        recent_awards = queryset.filter(
            status='active'
        ).order_by('-created_at')[:20]
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('awarded_amount')
        ).order_by('status')
        
        report_data = {
            'report_info': {
                'title': 'Scholarship Distribution Report',
                'generated_at': timezone.now().isoformat(),
                'filters_applied': {
                    'academic_year': academic_year,
                    'scholarship_type': scholarship_type
                }
            },
            'summary': {
                'total_recipients': overall_stats['total_recipients'] or 0,
                'active_recipients': overall_stats['active_recipients'] or 0,
                'total_awarded': float(overall_stats['total_awarded'] or 0),
                'average_award': float(overall_stats['avg_award'] or 0)
            },
            'type_breakdown': [
                {
                    'scholarship_type': item['scholarship__scholarship_type'].replace('_', ' ').title(),
                    'recipient_count': item['recipient_count'],
                    'active_count': item['active_count'],
                    'total_amount': float(item['total_amount'] or 0),
                    'average_amount': float(item['avg_amount'] or 0),
                    'percentage': (item['recipient_count'] / overall_stats['total_recipients'] * 100) if overall_stats['total_recipients'] > 0 else 0
                }
                for item in type_breakdown
            ],
            'year_breakdown': [
                {
                    'academic_year': item['scholarship__academic_year'],
                    'recipient_count': item['recipient_count'],
                    'scholarship_count': item['scholarship_count'],
                    'active_count': item['active_count'],
                    'total_amount': float(item['total_amount'] or 0)
                }
                for item in year_breakdown
            ],
            'class_breakdown': [
                {
                    'class_name': item['student__school_class__name'],
                    'recipient_count': item['recipient_count'],
                    'active_count': item['active_count'],
                    'total_amount': float(item['total_amount'] or 0),
                    'average_amount': float(item['avg_amount'] or 0)
                }
                for item in class_breakdown
            ],
            'top_scholarships': [
                {
                    'name': scholarship.name,
                    'type': scholarship.get_scholarship_type_display(),
                    'academic_year': scholarship.academic_year,
                    'total_awarded': float(scholarship.total_awarded or 0),
                    'recipient_count': scholarship.recipient_count,
                    'active_recipients': scholarship.active_recipients,
                    'max_recipients': scholarship.max_recipients
                }
                for scholarship in top_scholarships
            ],
            'recent_awards': [
                {
                    'student_name': award.student.user.get_full_name(),
                    'student_id': award.student.student_id,
                    'class_name': award.student.school_class.name,
                    'scholarship_name': award.scholarship.name,
                    'scholarship_type': award.scholarship.get_scholarship_type_display(),
                    'awarded_amount': float(award.awarded_amount),
                    'start_date': award.start_date.isoformat(),
                    'end_date': award.end_date.isoformat(),
                    'status': award.get_status_display()
                }
                for award in recent_awards
            ],
            'status_breakdown': [
                {
                    'status': item['status'].title(),
                    'count': item['count'],
                    'total_amount': float(item['total_amount'] or 0),
                    'percentage': (item['count'] / overall_stats['total_recipients'] * 100) if overall_stats['total_recipients'] > 0 else 0
                }
                for item in status_breakdown
            ]
        }
        
        return report_data
    
    @staticmethod
    def generate_payroll_report(month=None, year=None, department=None):
        """
        Generate payroll report with salary breakdowns and deduction summaries
        
        Requirements: 9.4 - Payroll reports with salary breakdowns and deduction summaries
        """
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
            
        # Create date range for the month
        report_date = date(year, month, 1)
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        
        # Build base queryset
        queryset = StaffPayroll.objects.filter(
            month__gte=report_date,
            month__lt=next_month
        ).select_related('teacher__user', 'payroll_structure')
        
        # Apply department filter if provided
        if department:
            # Assuming teachers have a department field - adjust as needed
            queryset = queryset.filter(teacher__department=department)
        
        # Overall statistics
        overall_stats = queryset.aggregate(
            total_staff=Count('id'),
            paid_staff=Count('id', filter=Q(is_paid=True)),
            total_gross=Sum('gross_salary'),
            total_net=Sum('net_salary'),
            total_tax=Sum('tax_deduction'),
            total_pension=Sum('pension_deduction'),
            total_other_deductions=Sum('other_deductions'),
            avg_gross=Avg('gross_salary'),
            avg_net=Avg('net_salary')
        )
        
        # Payment status breakdown
        status_breakdown = queryset.values('is_paid').annotate(
            count=Count('id'),
            total_gross=Sum('gross_salary'),
            total_net=Sum('net_salary')
        )
        
        # Payroll structure breakdown
        structure_breakdown = queryset.values(
            'payroll_structure__name'
        ).annotate(
            staff_count=Count('id'),
            total_gross=Sum('gross_salary'),
            total_net=Sum('net_salary'),
            avg_gross=Avg('gross_salary'),
            avg_net=Avg('net_salary')
        ).order_by('-total_gross')
        
        # Individual payroll details
        individual_payrolls = queryset.order_by('teacher__user__last_name', 'teacher__user__first_name')
        
        # Deduction analysis
        total_deductions = (overall_stats['total_tax'] or 0) + (overall_stats['total_pension'] or 0) + (overall_stats['total_other_deductions'] or 0)
        
        # Calculate percentages
        total_gross = overall_stats['total_gross'] or 0
        tax_percentage = (float(overall_stats['total_tax'] or 0) / float(total_gross) * 100) if total_gross > 0 else 0
        pension_percentage = (float(overall_stats['total_pension'] or 0) / float(total_gross) * 100) if total_gross > 0 else 0
        
        report_data = {
            'report_info': {
                'title': f'Payroll Report - {report_date.strftime("%B %Y")}',
                'generated_at': timezone.now().isoformat(),
                'period': {
                    'month': month,
                    'year': year,
                    'month_name': report_date.strftime('%B %Y')
                },
                'filters_applied': {
                    'department': department
                }
            },
            'summary': {
                'total_staff': overall_stats['total_staff'] or 0,
                'paid_staff': overall_stats['paid_staff'] or 0,
                'pending_payments': (overall_stats['total_staff'] or 0) - (overall_stats['paid_staff'] or 0),
                'total_gross_salary': float(total_gross),
                'total_net_salary': float(overall_stats['total_net'] or 0),
                'total_deductions': float(total_deductions),
                'average_gross_salary': float(overall_stats['avg_gross'] or 0),
                'average_net_salary': float(overall_stats['avg_net'] or 0)
            },
            'deduction_analysis': {
                'total_tax_deduction': float(overall_stats['total_tax'] or 0),
                'total_pension_deduction': float(overall_stats['total_pension'] or 0),
                'total_other_deductions': float(overall_stats['total_other_deductions'] or 0),
                'tax_percentage': float(tax_percentage),
                'pension_percentage': float(pension_percentage),
                'total_deduction_percentage': float((float(total_deductions) / float(total_gross) * 100) if total_gross > 0 else 0)
            },
            'payment_status': [
                {
                    'status': 'Paid' if item['is_paid'] else 'Pending',
                    'count': item['count'],
                    'total_gross': float(item['total_gross'] or 0),
                    'total_net': float(item['total_net'] or 0),
                    'percentage': (item['count'] / overall_stats['total_staff'] * 100) if overall_stats['total_staff'] > 0 else 0
                }
                for item in status_breakdown
            ],
            'structure_breakdown': [
                {
                    'structure_name': item['payroll_structure__name'],
                    'staff_count': item['staff_count'],
                    'total_gross': float(item['total_gross'] or 0),
                    'total_net': float(item['total_net'] or 0),
                    'average_gross': float(item['avg_gross'] or 0),
                    'average_net': float(item['avg_net'] or 0)
                }
                for item in structure_breakdown
            ],
            'individual_payrolls': [
                {
                    'staff_name': payroll.teacher.user.get_full_name(),
                    'employee_id': payroll.teacher.employee_id,
                    'payroll_structure': payroll.payroll_structure.name,
                    'gross_salary': float(payroll.gross_salary),
                    'tax_deduction': float(payroll.tax_deduction),
                    'pension_deduction': float(payroll.pension_deduction),
                    'other_deductions': float(payroll.other_deductions),
                    'net_salary': float(payroll.net_salary),
                    'is_paid': payroll.is_paid,
                    'payment_date': payroll.payment_date.isoformat() if payroll.payment_date else None
                }
                for payroll in individual_payrolls
            ]
        }
        
        return report_data
    
    @staticmethod
    def generate_comparative_year_over_year_report(current_year=None, comparison_years=1):
        """
        Generate comparative reports showing year-over-year financial performance
        
        Requirements: 9.5 - Comparative reports showing year-over-year financial performance
        """
        if not current_year:
            current_year = timezone.now().year
        
        years_to_compare = [current_year - i for i in range(comparison_years + 1)]
        
        comparative_data = {}
        
        for year in years_to_compare:
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            
            # Fee income for the year
            fee_income = FeePayment.objects.filter(
                payment_date__date__gte=year_start,
                payment_date__date__lte=year_end
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            # Other income
            other_income = FinancialTransaction.objects.filter(
                transaction_type='income',
                transaction_date__gte=year_start,
                transaction_date__lte=year_end
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            # Expenses
            expenses = FinancialTransaction.objects.filter(
                transaction_type='expense',
                transaction_date__gte=year_start,
                transaction_date__lte=year_end
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            # Payroll expenses
            payroll = StaffPayroll.objects.filter(
                month__gte=year_start,
                month__lte=year_end,
                is_paid=True
            ).aggregate(
                total_gross=Sum('gross_salary'),
                total_net=Sum('net_salary'),
                count=Count('id')
            )
            
            # Student enrollment
            student_count = StudentFee.objects.filter(
                created_at__date__gte=year_start,
                created_at__date__lte=year_end
            ).values('student').distinct().count()
            
            # Scholarship data
            scholarships = ScholarshipRecipient.objects.filter(
                start_date__gte=year_start,
                start_date__lte=year_end
            ).aggregate(
                total_awarded=Sum('awarded_amount'),
                recipient_count=Count('id')
            )
            
            total_income = (fee_income['total'] or 0) + (other_income['total'] or 0)
            total_expenses = (expenses['total'] or 0) + (payroll['total_net'] or 0)
            net_profit = total_income - total_expenses
            
            comparative_data[year] = {
                'year': year,
                'income': {
                    'fee_income': float(fee_income['total'] or 0),
                    'other_income': float(other_income['total'] or 0),
                    'total_income': float(total_income),
                    'payment_count': fee_income['count'] or 0
                },
                'expenses': {
                    'operational_expenses': float(expenses['total'] or 0),
                    'payroll_expenses': float(payroll['total_net'] or 0),
                    'total_expenses': float(total_expenses),
                    'expense_count': expenses['count'] or 0
                },
                'profitability': {
                    'net_profit': float(net_profit),
                    'profit_margin': (float(net_profit) / float(total_income) * 100) if total_income > 0 else 0
                },
                'operational_metrics': {
                    'student_count': student_count,
                    'staff_payroll_count': payroll['count'] or 0,
                    'scholarship_recipients': scholarships['recipient_count'] or 0,
                    'total_scholarships_awarded': float(scholarships['total_awarded'] or 0)
                }
            }
        
        # Calculate year-over-year changes
        changes = {}
        if len(years_to_compare) > 1:
            current_data = comparative_data[current_year]
            previous_data = comparative_data[current_year - 1]
            
            changes = {
                'income_change': {
                    'amount': current_data['income']['total_income'] - previous_data['income']['total_income'],
                    'percentage': ((current_data['income']['total_income'] - previous_data['income']['total_income']) / previous_data['income']['total_income'] * 100) if previous_data['income']['total_income'] > 0 else 0
                },
                'expense_change': {
                    'amount': current_data['expenses']['total_expenses'] - previous_data['expenses']['total_expenses'],
                    'percentage': ((current_data['expenses']['total_expenses'] - previous_data['expenses']['total_expenses']) / previous_data['expenses']['total_expenses'] * 100) if previous_data['expenses']['total_expenses'] > 0 else 0
                },
                'profit_change': {
                    'amount': current_data['profitability']['net_profit'] - previous_data['profitability']['net_profit'],
                    'percentage': ((current_data['profitability']['net_profit'] - previous_data['profitability']['net_profit']) / abs(previous_data['profitability']['net_profit']) * 100) if previous_data['profitability']['net_profit'] != 0 else 0
                },
                'student_change': {
                    'count': current_data['operational_metrics']['student_count'] - previous_data['operational_metrics']['student_count'],
                    'percentage': ((current_data['operational_metrics']['student_count'] - previous_data['operational_metrics']['student_count']) / previous_data['operational_metrics']['student_count'] * 100) if previous_data['operational_metrics']['student_count'] > 0 else 0
                }
            }
        
        report_data = {
            'report_info': {
                'title': f'Year-over-Year Comparative Report ({current_year - comparison_years}-{current_year})',
                'generated_at': timezone.now().isoformat(),
                'comparison_period': {
                    'current_year': current_year,
                    'years_compared': years_to_compare,
                    'comparison_years': comparison_years
                }
            },
            'yearly_data': comparative_data,
            'year_over_year_changes': changes,
            'trends': {
                'income_trend': [comparative_data[year]['income']['total_income'] for year in sorted(years_to_compare)],
                'expense_trend': [comparative_data[year]['expenses']['total_expenses'] for year in sorted(years_to_compare)],
                'profit_trend': [comparative_data[year]['profitability']['net_profit'] for year in sorted(years_to_compare)],
                'student_trend': [comparative_data[year]['operational_metrics']['student_count'] for year in sorted(years_to_compare)]
            }
        }
        
        return report_data
    
    @staticmethod
    def get_available_report_types():
        """
        Get list of available report types with their descriptions
        
        Requirements: 9.6, 9.7 - Report customization functionality
        """
        return {
            'monthly_summary': {
                'name': 'Monthly Financial Summary',
                'description': 'Comprehensive monthly financial report with income, expenses, and profit analysis',
                'parameters': ['year', 'month', 'include_charts']
            },
            'fee_collection': {
                'name': 'Fee Collection Report',
                'description': 'Detailed fee collection report with payment status and collection rates',
                'parameters': ['term_id', 'class_id', 'status_filter', 'date_range']
            },
            'scholarship_distribution': {
                'name': 'Scholarship Distribution Report',
                'description': 'Scholarship distribution analysis with recipient demographics',
                'parameters': ['academic_year', 'scholarship_type']
            },
            'payroll': {
                'name': 'Payroll Report',
                'description': 'Staff payroll report with salary breakdowns and deductions',
                'parameters': ['month', 'year', 'department']
            },
            'year_over_year': {
                'name': 'Year-over-Year Comparative Report',
                'description': 'Comparative financial performance analysis across multiple years',
                'parameters': ['current_year', 'comparison_years']
            }
        }
    
    @staticmethod
    def generate_custom_report(report_type, **parameters):
        """
        Generate custom report based on type and parameters
        
        Requirements: 9.6, 9.7 - Report customization functionality
        """
        report_methods = {
            'monthly_summary': ReportService.generate_monthly_financial_summary,
            'fee_collection': ReportService.generate_fee_collection_report,
            'scholarship_distribution': ReportService.generate_scholarship_distribution_report,
            'payroll': ReportService.generate_payroll_report,
            'year_over_year': ReportService.generate_comparative_year_over_year_report
        }
        
        if report_type not in report_methods:
            raise ValueError(f"Unknown report type: {report_type}")
        
        method = report_methods[report_type]
        return method(**parameters)