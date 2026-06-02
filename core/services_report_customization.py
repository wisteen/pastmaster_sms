"""
Report Customization and Scheduling Services for Financial Management Enhancement

This module provides advanced report customization capabilities including parameter validation,
chart configuration, and report scheduling functionality.

Requirements: 9.6, 9.7 - Report customization and scheduling functionality
"""

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from .tenanting import TenantOwnedMixin
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
import json
from dataclasses import dataclass, asdict
from enum import Enum


class ReportFrequency(models.TextChoices):
    """Report scheduling frequency options"""
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    YEARLY = 'yearly', 'Yearly'


class ReportFormat(models.TextChoices):
    """Available report export formats"""
    PDF = 'pdf', 'PDF'
    EXCEL = 'excel', 'Excel'
    CSV = 'csv', 'CSV'
    JSON = 'json', 'JSON'


@dataclass
class ChartConfiguration:
    """Configuration for chart visualization in reports"""
    chart_type: str  # 'line', 'bar', 'pie', 'doughnut', 'area'
    title: str
    colors: List[str]
    show_legend: bool = True
    show_labels: bool = True
    responsive: bool = True
    height: int = 400
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ReportParameters:
    """Standardized report parameters with validation"""
    report_type: str
    date_range: Optional[tuple] = None
    filters: Optional[Dict[str, Any]] = None
    include_charts: bool = True
    chart_configs: Optional[List[ChartConfiguration]] = None
    export_formats: Optional[List[str]] = None
    
    def validate(self) -> List[str]:
        """Validate report parameters and return list of errors"""
        errors = []
        
        valid_types = ['monthly_summary', 'fee_collection', 'scholarship_distribution', 'payroll', 'year_over_year']
        if self.report_type not in valid_types:
            errors.append(f"Invalid report type: {self.report_type}")
        
        if self.date_range:
            if len(self.date_range) != 2:
                errors.append("Date range must contain start and end dates")
            elif self.date_range[0] > self.date_range[1]:
                errors.append("Start date must be before end date")
        
        if self.export_formats:
            valid_formats = [choice[0] for choice in ReportFormat.choices]
            invalid_formats = [f for f in self.export_formats if f not in valid_formats]
            if invalid_formats:
                errors.append(f"Invalid export formats: {', '.join(invalid_formats)}")
        
        return errors


class ScheduledReport(TenantOwnedMixin):
    """Model for scheduled report generation"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    report_type = models.CharField(max_length=50)
    parameters = models.JSONField(default=dict)
    frequency = models.CharField(max_length=20, choices=ReportFrequency.choices)
    recipients = models.JSONField(default=list)  # List of email addresses
    is_active = models.BooleanField(default=True)
    next_run = models.DateTimeField()
    last_run = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency"""
        now = timezone.now()
        
        if self.frequency == ReportFrequency.DAILY:
            return now + timedelta(days=1)
        elif self.frequency == ReportFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif self.frequency == ReportFrequency.MONTHLY:
            # Add one month
            if now.month == 12:
                return now.replace(year=now.year + 1, month=1)
            else:
                return now.replace(month=now.month + 1)
        elif self.frequency == ReportFrequency.QUARTERLY:
            # Add 3 months
            month = now.month + 3
            year = now.year
            if month > 12:
                month -= 12
                year += 1
            return now.replace(year=year, month=month)
        elif self.frequency == ReportFrequency.YEARLY:
            return now.replace(year=now.year + 1)
        
        return now + timedelta(days=1)  # Default fallback


class ReportExecution(models.Model):
    """Track report execution history"""
    scheduled_report = models.ForeignKey(ScheduledReport, on_delete=models.CASCADE, related_name='executions')
    executed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('running', 'Running')
    ])
    error_message = models.TextField(blank=True)
    execution_time = models.DurationField(null=True, blank=True)
    report_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-executed_at']


class ReportCustomizationService:
    """Service for advanced report customization and configuration"""
    
    @staticmethod
    def get_default_chart_configs(report_type: str) -> List[ChartConfiguration]:
        """Get default chart configurations for each report type"""
        configs = {
            'monthly_summary': [
                ChartConfiguration(
                    chart_type='doughnut',
                    title='Income Breakdown',
                    colors=['#28a745', '#17a2b8', '#ffc107', '#dc3545']
                ),
                ChartConfiguration(
                    chart_type='bar',
                    title='Monthly Comparison',
                    colors=['#007bff', '#6c757d']
                )
            ],
            'fee_collection': [
                ChartConfiguration(
                    chart_type='pie',
                    title='Payment Status Distribution',
                    colors=['#28a745', '#ffc107', '#dc3545', '#6c757d']
                ),
                ChartConfiguration(
                    chart_type='bar',
                    title='Collection by Class',
                    colors=['#007bff']
                )
            ],
            'scholarship_distribution': [
                ChartConfiguration(
                    chart_type='bar',
                    title='Scholarships by Type',
                    colors=['#17a2b8', '#28a745', '#ffc107']
                ),
                ChartConfiguration(
                    chart_type='line',
                    title='Awards Over Time',
                    colors=['#007bff']
                )
            ],
            'payroll': [
                ChartConfiguration(
                    chart_type='bar',
                    title='Salary Distribution',
                    colors=['#28a745', '#dc3545']
                ),
                ChartConfiguration(
                    chart_type='doughnut',
                    title='Deduction Breakdown',
                    colors=['#ffc107', '#17a2b8', '#6c757d']
                )
            ],
            'year_over_year': [
                ChartConfiguration(
                    chart_type='line',
                    title='Revenue Trend',
                    colors=['#007bff', '#28a745', '#dc3545']
                ),
                ChartConfiguration(
                    chart_type='bar',
                    title='Year Comparison',
                    colors=['#007bff', '#6c757d']
                )
            ]
        }
        
        return configs.get(report_type, [])
    
    @staticmethod
    def validate_report_parameters(report_type: str, parameters: Dict[str, Any]) -> List[str]:
        """Validate report parameters based on report type"""
        errors = []
        
        if report_type == 'monthly_summary':
            year = parameters.get('year')
            month = parameters.get('month')
            
            if year and (not isinstance(year, int) or year < 2000 or year > 2100):
                errors.append("Year must be between 2000 and 2100")
            
            if month and (not isinstance(month, int) or month < 1 or month > 12):
                errors.append("Month must be between 1 and 12")
        
        elif report_type == 'fee_collection':
            date_range = parameters.get('date_range')
            if date_range and len(date_range) == 2:
                try:
                    start_date = datetime.strptime(str(date_range[0]), '%Y-%m-%d').date()
                    end_date = datetime.strptime(str(date_range[1]), '%Y-%m-%d').date()
                    if start_date > end_date:
                        errors.append("Start date must be before end date")
                except (ValueError, TypeError):
                    errors.append("Invalid date format in date range")
        
        elif report_type == 'payroll':
            year = parameters.get('year')
            month = parameters.get('month')
            
            if year and (not isinstance(year, int) or year < 2000 or year > 2100):
                errors.append("Year must be between 2000 and 2100")
            
            if month and (not isinstance(month, int) or month < 1 or month > 12):
                errors.append("Month must be between 1 and 12")
        
        elif report_type == 'year_over_year':
            current_year = parameters.get('current_year')
            comparison_years = parameters.get('comparison_years')
            
            if current_year and (not isinstance(current_year, int) or current_year < 2000):
                errors.append("Current year must be 2000 or later")
            
            if comparison_years and (not isinstance(comparison_years, int) or comparison_years < 1 or comparison_years > 10):
                errors.append("Comparison years must be between 1 and 10")
        
        return errors
    
    @staticmethod
    def create_scheduled_report(name: str, report_type: str, parameters: Dict[str, Any], 
                              frequency: str, recipients: List[str], user,
                              description: str = '') -> ScheduledReport:
        """Create a new scheduled report"""
        # Validate parameters
        errors = ReportCustomizationService.validate_report_parameters(report_type, parameters)
        if errors:
            raise ValueError(f"Parameter validation failed: {'; '.join(errors)}")
        
        # Validate recipients
        if not recipients:
            raise ValueError("At least one recipient email is required")
        
        # Create scheduled report
        scheduled_report = ScheduledReport.objects.create(
            name=name,
            description=description,
            report_type=report_type,
            parameters=parameters,
            frequency=frequency,
            recipients=recipients,
            created_by=user,
            next_run=timezone.now() + timedelta(hours=1)  # Start in 1 hour
        )
        
        # Calculate proper next run time
        scheduled_report.next_run = scheduled_report.calculate_next_run()
        scheduled_report.save()
        
        return scheduled_report
    
    @staticmethod
    def update_scheduled_report(report_id: int, **updates) -> ScheduledReport:
        """Update an existing scheduled report"""
        scheduled_report = ScheduledReport.objects.get(id=report_id)
        
        for field, value in updates.items():
            if hasattr(scheduled_report, field):
                setattr(scheduled_report, field, value)
        
        # Recalculate next run if frequency changed
        if 'frequency' in updates:
            scheduled_report.next_run = scheduled_report.calculate_next_run()
        
        scheduled_report.save()
        return scheduled_report
    
    @staticmethod
    def get_report_templates() -> Dict[str, Dict[str, Any]]:
        """Get predefined report templates with common configurations"""
        return {
            'monthly_financial_overview': {
                'name': 'Monthly Financial Overview',
                'report_type': 'monthly_summary',
                'description': 'Comprehensive monthly financial summary with charts',
                'parameters': {
                    'include_charts': True,
                    'year': timezone.now().year,
                    'month': timezone.now().month
                },
                'frequency': 'monthly',
                'chart_configs': ReportCustomizationService.get_default_chart_configs('monthly_summary')
            },
            'weekly_fee_collection': {
                'name': 'Weekly Fee Collection Report',
                'report_type': 'fee_collection',
                'description': 'Weekly fee collection status and trends',
                'parameters': {
                    'include_charts': True,
                    'date_range': [
                        (timezone.now() - timedelta(days=7)).date(),
                        timezone.now().date()
                    ]
                },
                'frequency': 'weekly',
                'chart_configs': ReportCustomizationService.get_default_chart_configs('fee_collection')
            },
            'quarterly_scholarship_review': {
                'name': 'Quarterly Scholarship Review',
                'report_type': 'scholarship_distribution',
                'description': 'Quarterly review of scholarship distribution and impact',
                'parameters': {
                    'include_charts': True,
                    'academic_year': f"{timezone.now().year}-{timezone.now().year + 1}"
                },
                'frequency': 'quarterly',
                'chart_configs': ReportCustomizationService.get_default_chart_configs('scholarship_distribution')
            },
            'monthly_payroll_summary': {
                'name': 'Monthly Payroll Summary',
                'report_type': 'payroll',
                'description': 'Monthly payroll processing summary and analysis',
                'parameters': {
                    'include_charts': True,
                    'year': timezone.now().year,
                    'month': timezone.now().month
                },
                'frequency': 'monthly',
                'chart_configs': ReportCustomizationService.get_default_chart_configs('payroll')
            },
            'annual_performance_review': {
                'name': 'Annual Performance Review',
                'report_type': 'year_over_year',
                'description': 'Annual financial performance comparison',
                'parameters': {
                    'include_charts': True,
                    'current_year': timezone.now().year,
                    'comparison_years': 3
                },
                'frequency': 'yearly',
                'chart_configs': ReportCustomizationService.get_default_chart_configs('year_over_year')
            }
        }
    
    @staticmethod
    def get_available_customization_options(report_type: str) -> Dict[str, Any]:
        """Get available customization options for a specific report type"""
        from .academic_choices import existing_session_choices

        sessions = existing_session_choices()
        base_options = {
            'include_charts': {
                'type': 'boolean',
                'label': 'Include Charts and Visualizations',
                'default': True
            },
            'export_formats': {
                'type': 'multi_select',
                'label': 'Export Formats',
                'options': [
                    {'value': 'pdf', 'label': 'PDF'},
                    {'value': 'excel', 'label': 'Excel'},
                    {'value': 'csv', 'label': 'CSV'},
                    {'value': 'json', 'label': 'JSON'}
                ],
                'default': ['pdf', 'csv']
            }
        }
        
        type_specific_options = {
            'monthly_summary': {
                'year': {
                    'type': 'select',
                    'label': 'Year',
                    'options': [{'value': y, 'label': str(y)} for y in range(2020, 2030)],
                    'default': timezone.now().year
                },
                'month': {
                    'type': 'select',
                    'label': 'Month',
                    'options': [
                        {'value': i, 'label': month} for i, month in enumerate([
                            'January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December'
                        ], 1)
                    ],
                    'default': timezone.now().month
                }
            },
            'fee_collection': {
                'date_range': {
                    'type': 'date_range',
                    'label': 'Date Range',
                    'default': [
                        (timezone.now() - timedelta(days=30)).date(),
                        timezone.now().date()
                    ]
                },
                'status_filter': {
                    'type': 'select',
                    'label': 'Payment Status',
                    'options': [
                        {'value': '', 'label': 'All Statuses'},
                        {'value': 'pending', 'label': 'Pending'},
                        {'value': 'paid', 'label': 'Paid'},
                        {'value': 'overdue', 'label': 'Overdue'},
                        {'value': 'partial', 'label': 'Partial'}
                    ],
                    'default': ''
                }
            },
            'scholarship_distribution': {
                'academic_year': {
                    'type': 'select',
                    'label': 'Academic Year',
                    'options': [{'value': value, 'label': label} for value, label in sessions],
                    'default': sessions[0][0] if sessions else ''
                },
                'scholarship_type': {
                    'type': 'select',
                    'label': 'Scholarship Type',
                    'options': [
                        {'value': '', 'label': 'All Types'},
                        {'value': 'merit', 'label': 'Merit'},
                        {'value': 'need', 'label': 'Need Based'},
                        {'value': 'sports', 'label': 'Sports'},
                        {'value': 'academic', 'label': 'Academic'}
                    ],
                    'default': ''
                }
            },
            'payroll': {
                'year': {
                    'type': 'select',
                    'label': 'Year',
                    'options': [{'value': y, 'label': str(y)} for y in range(2020, 2030)],
                    'default': timezone.now().year
                },
                'month': {
                    'type': 'select',
                    'label': 'Month',
                    'options': [
                        {'value': i, 'label': month} for i, month in enumerate([
                            'January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December'
                        ], 1)
                    ],
                    'default': timezone.now().month
                },
                'department': {
                    'type': 'text',
                    'label': 'Department (Optional)',
                    'placeholder': 'e.g., Mathematics',
                    'default': ''
                }
            },
            'year_over_year': {
                'current_year': {
                    'type': 'select',
                    'label': 'Current Year',
                    'options': [{'value': y, 'label': str(y)} for y in range(2020, 2030)],
                    'default': timezone.now().year
                },
                'comparison_years': {
                    'type': 'select',
                    'label': 'Years to Compare',
                    'options': [
                        {'value': 1, 'label': '1 Year'},
                        {'value': 2, 'label': '2 Years'},
                        {'value': 3, 'label': '3 Years'},
                        {'value': 5, 'label': '5 Years'}
                    ],
                    'default': 2
                }
            }
        }
        
        # Merge base options with type-specific options
        options = {**base_options}
        if report_type in type_specific_options:
            options.update(type_specific_options[report_type])
        
        return options
