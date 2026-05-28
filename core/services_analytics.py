"""
Financial Analytics Service Classes for Financial Management Enhancement

This module provides comprehensive analytics and data processing capabilities for financial operations
including fee collection trends, expense breakdowns, income vs expenses comparisons, and scholarship
distribution analysis.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import json
from collections import defaultdict
from .models import (
    StudentFee, FeePayment, FinancialTransaction, Scholarship, 
    ScholarshipRecipient, StaffPayroll, PayrollStructure, Term, SchoolClass
)


class FinancialAnalyticsService:
    """Service for generating financial analytics data for charts and reports"""
    
    @staticmethod
    def get_fee_collection_trends(months=6):
        """
        Get fee collection trends for the last N months
        Returns data suitable for line charts showing collection patterns over time
        
        Requirements: 6.1 - Fee collection trend analysis
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        # Group payments by month
        monthly_data = []
        current_date = start_date.replace(day=1)  # Start from first day of month
        
        while current_date <= end_date:
            # Calculate next month
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1)
            
            # Get payments for this month
            payments = FeePayment.objects.filter(
                payment_date__date__gte=current_date,
                payment_date__date__lt=next_month
            ).aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            monthly_data.append({
                'month': current_date.strftime('%B %Y'),
                'month_short': current_date.strftime('%b %Y'),
                'amount': float(payments['total'] or 0),
                'payment_count': payments['count'] or 0,
                'date': current_date.isoformat()
            })
            
            current_date = next_month
        
        return {
            'labels': [item['month_short'] for item in monthly_data],
            'data': [item['amount'] for item in monthly_data],
            'payment_counts': [item['payment_count'] for item in monthly_data],
            'detailed_data': monthly_data
        }
    
    @staticmethod
    def get_expense_breakdown():
        """
        Get expense breakdown by category for pie chart visualization
        
        Requirements: 6.2 - Expense breakdown analysis
        """
        expenses = FinancialTransaction.objects.filter(
            transaction_type='expense'
        ).values('category').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Include payroll expenses
        payroll_total = StaffPayroll.objects.filter(
            is_paid=True
        ).aggregate(total=Sum('net_salary'))['total'] or 0
        
        expense_data = []
        total_expenses = 0
        
        for expense in expenses:
            amount = float(expense['total'])
            expense_data.append({
                'category': expense['category'].replace('_', ' ').title(),
                'amount': amount,
                'count': expense['count']
            })
            total_expenses += amount
        
        # Add payroll if there are any payroll expenses
        if payroll_total > 0:
            payroll_amount = float(payroll_total)
            expense_data.append({
                'category': 'Staff Payroll',
                'amount': payroll_amount,
                'count': StaffPayroll.objects.filter(is_paid=True).count()
            })
            total_expenses += payroll_amount
        
        # Calculate percentages
        for item in expense_data:
            item['percentage'] = (item['amount'] / total_expenses * 100) if total_expenses > 0 else 0
        
        return {
            'labels': [item['category'] for item in expense_data],
            'data': [item['amount'] for item in expense_data],
            'percentages': [item['percentage'] for item in expense_data],
            'detailed_data': expense_data,
            'total_expenses': total_expenses
        }
    
    @staticmethod
    def get_income_vs_expenses_comparison(months=12):
        """
        Compare monthly income vs expenses for the last N months
        Returns data suitable for bar charts showing financial performance
        
        Requirements: 6.3 - Income vs expenses comparison
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=months * 30)
        
        monthly_comparison = []
        current_date = start_date.replace(day=1)
        
        while current_date <= end_date:
            # Calculate next month
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1)
            
            # Fee income from payments
            fee_income = FeePayment.objects.filter(
                payment_date__date__gte=current_date,
                payment_date__date__lt=next_month
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Other income from financial transactions
            other_income = FinancialTransaction.objects.filter(
                transaction_type='income',
                transaction_date__gte=current_date,
                transaction_date__lt=next_month
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Expenses from financial transactions
            expenses = FinancialTransaction.objects.filter(
                transaction_type='expense',
                transaction_date__gte=current_date,
                transaction_date__lt=next_month
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Payroll expenses for the month
            payroll_expenses = StaffPayroll.objects.filter(
                month__gte=current_date,
                month__lt=next_month,
                is_paid=True
            ).aggregate(total=Sum('net_salary'))['total'] or 0
            
            total_income = fee_income + other_income
            total_expenses = expenses + payroll_expenses
            net_profit = total_income - total_expenses
            
            monthly_comparison.append({
                'month': current_date.strftime('%B %Y'),
                'month_short': current_date.strftime('%b %Y'),
                'fee_income': float(fee_income),
                'other_income': float(other_income),
                'total_income': float(total_income),
                'transaction_expenses': float(expenses),
                'payroll_expenses': float(payroll_expenses),
                'total_expenses': float(total_expenses),
                'net_profit': float(net_profit),
                'date': current_date.isoformat()
            })
            
            current_date = next_month
        
        return {
            'labels': [item['month_short'] for item in monthly_comparison],
            'income_data': [item['total_income'] for item in monthly_comparison],
            'expense_data': [item['total_expenses'] for item in monthly_comparison],
            'profit_data': [item['net_profit'] for item in monthly_comparison],
            'detailed_data': monthly_comparison
        }
    
    @staticmethod
    def get_scholarship_distribution_analysis():
        """
        Get scholarship distribution analysis by type, amount, and recipients
        
        Requirements: 6.4 - Scholarship distribution analysis
        """
        # Active scholarships by type
        scholarship_by_type = ScholarshipRecipient.objects.filter(
            status='active'
        ).values('scholarship__scholarship_type').annotate(
            total_amount=Sum('awarded_amount'),
            recipient_count=Count('id'),
            avg_amount=Avg('awarded_amount')
        ).order_by('-total_amount')
        
        # Scholarship distribution by academic year
        scholarship_by_year = Scholarship.objects.values('academic_year').annotate(
            total_scholarships=Count('id'),
            total_recipients=Count('scholarshiprecipient', filter=Q(scholarshiprecipient__status='active')),
            total_amount=Sum('scholarshiprecipient__awarded_amount', filter=Q(scholarshiprecipient__status='active'))
        ).order_by('-academic_year')
        
        # Top scholarships by amount awarded
        top_scholarships = Scholarship.objects.annotate(
            total_awarded=Sum('scholarshiprecipient__awarded_amount', filter=Q(scholarshiprecipient__status='active')),
            active_recipients=Count('scholarshiprecipient', filter=Q(scholarshiprecipient__status='active'))
        ).filter(total_awarded__gt=0).order_by('-total_awarded')[:10]
        
        # Format data for charts
        type_data = []
        for item in scholarship_by_type:
            scholarship_type = item['scholarship__scholarship_type']
            type_data.append({
                'type': scholarship_type.replace('_', ' ').title(),
                'total_amount': float(item['total_amount'] or 0),
                'recipient_count': item['recipient_count'],
                'average_amount': float(item['avg_amount'] or 0)
            })
        
        year_data = []
        for item in scholarship_by_year:
            year_data.append({
                'academic_year': item['academic_year'],
                'total_scholarships': item['total_scholarships'],
                'total_recipients': item['total_recipients'] or 0,
                'total_amount': float(item['total_amount'] or 0)
            })
        
        top_scholarship_data = []
        for scholarship in top_scholarships:
            top_scholarship_data.append({
                'name': scholarship.name,
                'type': scholarship.get_scholarship_type_display(),
                'total_awarded': float(scholarship.total_awarded or 0),
                'active_recipients': scholarship.active_recipients,
                'academic_year': scholarship.academic_year
            })
        
        return {
            'by_type': {
                'labels': [item['type'] for item in type_data],
                'amounts': [item['total_amount'] for item in type_data],
                'counts': [item['recipient_count'] for item in type_data],
                'detailed_data': type_data
            },
            'by_year': {
                'labels': [item['academic_year'] for item in year_data],
                'scholarship_counts': [item['total_scholarships'] for item in year_data],
                'recipient_counts': [item['total_recipients'] for item in year_data],
                'amounts': [item['total_amount'] for item in year_data],
                'detailed_data': year_data
            },
            'top_scholarships': top_scholarship_data
        }
    
    @staticmethod
    def get_payment_status_distribution():
        """
        Get distribution of payment statuses across all student fees
        
        Requirements: 6.5 - Financial analytics with charts and graphs
        """
        status_data = StudentFee.objects.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            balance_amount=Sum('total_amount') - Sum('paid_amount') - Sum('discount_amount')
        ).order_by('status')
        
        formatted_data = []
        total_fees = 0
        
        for item in status_data:
            count = item['count']
            total_fees += count
            formatted_data.append({
                'status': item['status'].title(),
                'count': count,
                'total_amount': float(item['total_amount'] or 0),
                'paid_amount': float(item['paid_amount'] or 0),
                'balance_amount': float(item['balance_amount'] or 0)
            })
        
        # Calculate percentages
        for item in formatted_data:
            item['percentage'] = (item['count'] / total_fees * 100) if total_fees > 0 else 0
        
        return {
            'labels': [item['status'] for item in formatted_data],
            'counts': [item['count'] for item in formatted_data],
            'percentages': [item['percentage'] for item in formatted_data],
            'amounts': [item['total_amount'] for item in formatted_data],
            'detailed_data': formatted_data,
            'total_fees': total_fees
        }
    
    @staticmethod
    def get_class_wise_fee_collection():
        """
        Get fee collection statistics by school class
        
        Requirements: 6.5 - Financial analytics with charts and graphs
        """
        class_data = StudentFee.objects.values(
            'student__school_class__name'
        ).annotate(
            total_students=Count('student', distinct=True),
            total_fees=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
            total_balance=Sum('total_amount') - Sum('paid_amount') - Sum('discount_amount'),
            paid_count=Count('id', filter=Q(status='paid')),
            pending_count=Count('id', filter=Q(status='pending')),
            overdue_count=Count('id', filter=Q(status='overdue'))
        ).order_by('student__school_class__name')
        
        formatted_data = []
        for item in class_data:
            class_name = item['student__school_class__name']
            total_fees = float(item['total_fees'] or 0)
            total_paid = float(item['total_paid'] or 0)
            collection_rate = (total_paid / total_fees * 100) if total_fees > 0 else 0
            
            formatted_data.append({
                'class_name': class_name,
                'total_students': item['total_students'],
                'total_fees': total_fees,
                'total_paid': total_paid,
                'total_balance': float(item['total_balance'] or 0),
                'collection_rate': collection_rate,
                'paid_count': item['paid_count'],
                'pending_count': item['pending_count'],
                'overdue_count': item['overdue_count']
            })
        
        return {
            'labels': [item['class_name'] for item in formatted_data],
            'collection_rates': [item['collection_rate'] for item in formatted_data],
            'total_fees': [item['total_fees'] for item in formatted_data],
            'total_paid': [item['total_paid'] for item in formatted_data],
            'detailed_data': formatted_data
        }
    
    @staticmethod
    def get_financial_summary_dashboard():
        """
        Get comprehensive financial summary for dashboard widgets
        
        Requirements: 6.5 - Financial analytics with charts and graphs
        """
        # Current month data
        current_month = timezone.now().date().replace(day=1)
        if current_month.month == 12:
            next_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            next_month = current_month.replace(month=current_month.month + 1)
        
        # Fee collection summary
        total_fees = StudentFee.objects.aggregate(
            total=Sum('total_amount'),
            paid=Sum('paid_amount'),
            balance=Sum('total_amount') - Sum('paid_amount') - Sum('discount_amount')
        )
        
        # Current month collections
        current_month_collections = FeePayment.objects.filter(
            payment_date__date__gte=current_month,
            payment_date__date__lt=next_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Outstanding fees
        overdue_fees = StudentFee.objects.filter(
            status='overdue'
        ).aggregate(
            count=Count('id'),
            amount=Sum('total_amount') - Sum('paid_amount') - Sum('discount_amount')
        )
        
        # Scholarship summary
        scholarship_summary = ScholarshipRecipient.objects.filter(
            status='active'
        ).aggregate(
            total_recipients=Count('id'),
            total_amount=Sum('awarded_amount')
        )
        
        # Payroll summary
        payroll_summary = StaffPayroll.objects.filter(
            month__gte=current_month,
            month__lt=next_month
        ).aggregate(
            total_staff=Count('id'),
            total_gross=Sum('gross_salary'),
            total_net=Sum('net_salary'),
            paid_count=Count('id', filter=Q(is_paid=True))
        )
        
        return {
            'fee_collection': {
                'total_fees': float(total_fees['total'] or 0),
                'total_paid': float(total_fees['paid'] or 0),
                'total_balance': float(total_fees['balance'] or 0),
                'collection_rate': (float(total_fees['paid'] or 0) / float(total_fees['total'] or 1)) * 100,
                'current_month_collections': float(current_month_collections)
            },
            'outstanding_fees': {
                'overdue_count': overdue_fees['count'] or 0,
                'overdue_amount': float(overdue_fees['amount'] or 0)
            },
            'scholarships': {
                'active_recipients': scholarship_summary['total_recipients'] or 0,
                'total_awarded': float(scholarship_summary['total_amount'] or 0)
            },
            'payroll': {
                'current_month_staff': payroll_summary['total_staff'] or 0,
                'current_month_gross': float(payroll_summary['total_gross'] or 0),
                'current_month_net': float(payroll_summary['total_net'] or 0),
                'paid_staff_count': payroll_summary['paid_count'] or 0
            }
        }
    
    @staticmethod
    def get_monthly_income_vs_expenses(months=6):
        """
        Alias for get_income_vs_expenses_comparison for backward compatibility
        
        Requirements: 6.3 - Income vs expenses comparison
        """
        return FinancialAnalyticsService.get_income_vs_expenses_comparison(months=months)
    
    @staticmethod
    def get_scholarship_distribution():
        """
        Alias for get_scholarship_distribution_analysis for backward compatibility
        
        Requirements: 6.4 - Scholarship distribution analysis
        """
        return FinancialAnalyticsService.get_scholarship_distribution_analysis()
    
    @staticmethod
    def get_chart_data_for_type(chart_type, **kwargs):
        """
        Generic method to get chart data based on chart type
        Useful for dynamic chart generation
        
        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
        """
        chart_methods = {
            'fee_trends': FinancialAnalyticsService.get_fee_collection_trends,
            'expense_breakdown': FinancialAnalyticsService.get_expense_breakdown,
            'income_vs_expenses': FinancialAnalyticsService.get_income_vs_expenses_comparison,
            'scholarship_distribution': FinancialAnalyticsService.get_scholarship_distribution_analysis,
            'payment_status': FinancialAnalyticsService.get_payment_status_distribution,
            'class_wise_collection': FinancialAnalyticsService.get_class_wise_fee_collection,
            'dashboard_summary': FinancialAnalyticsService.get_financial_summary_dashboard
        }
        
        if chart_type in chart_methods:
            method = chart_methods[chart_type]
            # Pass any additional parameters
            if kwargs:
                return method(**kwargs)
            else:
                return method()
        else:
            raise ValueError(f"Unknown chart type: {chart_type}")