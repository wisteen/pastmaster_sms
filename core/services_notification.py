"""
Notification Service for Financial Management System

This module provides comprehensive notification services for the financial management
system, including payment reminders, payment confirmations, scholarship awards,
and payroll processing notifications.
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db import models, transaction
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import logging
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationType(Enum):
    """Enumeration of notification types"""
    PAYMENT_REMINDER = "payment_reminder"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    SCHOLARSHIP_AWARD = "scholarship_award"
    PAYROLL_PROCESSING = "payroll_processing"
    OVERDUE_PAYMENT = "overdue_payment"
    BULK_OPERATION_COMPLETE = "bulk_operation_complete"


class NotificationStatus(Enum):
    """Enumeration of notification delivery statuses"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class NotificationContext:
    """Data class for notification context"""
    recipient_email: str
    recipient_name: str
    subject: str
    template_name: str
    context_data: Dict[str, Any]
    notification_type: NotificationType
    priority: int = 1  # 1=high, 2=medium, 3=low


class NotificationService:
    """Main service class for handling notifications"""
    
    def __init__(self):
        self.default_from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@school.edu')
        self.email_backend = getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
    
    def send_payment_reminder(self, student_fee, days_until_due: int = 7) -> bool:
        """Send payment reminder notification"""
        try:
            from .models import StudentFee
            
            if not isinstance(student_fee, StudentFee):
                logger.error("Invalid student_fee object provided")
                return False
            
            # Get recipient email (student's parent or student)
            recipient_email = student_fee.student.user.email
            if not recipient_email:
                logger.warning(f"No email found for student {student_fee.student}")
                return False
            
            context = NotificationContext(
                recipient_email=recipient_email,
                recipient_name=student_fee.student.user.get_full_name(),
                subject=f"Payment Reminder - {student_fee.fee_structure.name}",
                template_name="payment_reminder",
                context_data={
                    'student_name': student_fee.student.user.get_full_name(),
                    'student_id': student_fee.student.student_id,
                    'fee_name': student_fee.fee_structure.name,
                    'total_amount': student_fee.total_amount,
                    'paid_amount': student_fee.paid_amount,
                    'balance_amount': student_fee.balance_amount,
                    'due_date': student_fee.due_date,
                    'days_until_due': days_until_due,
                    'school_name': self._get_school_name(),
                },
                notification_type=NotificationType.PAYMENT_REMINDER
            )
            
            return self._send_notification(context)
            
        except Exception as e:
            logger.error(f"Error sending payment reminder: {str(e)}")
            return False
    
    def send_payment_confirmation(self, fee_payment) -> bool:
        """Send payment confirmation notification"""
        try:
            from .models import FeePayment
            
            if not isinstance(fee_payment, FeePayment):
                logger.error("Invalid fee_payment object provided")
                return False
            
            recipient_email = fee_payment.student_fee.student.user.email
            if not recipient_email:
                logger.warning(f"No email found for student {fee_payment.student_fee.student}")
                return False
            
            context = NotificationContext(
                recipient_email=recipient_email,
                recipient_name=fee_payment.student_fee.student.user.get_full_name(),
                subject=f"Payment Confirmation - Receipt #{fee_payment.id}",
                template_name="payment_confirmation",
                context_data={
                    'student_name': fee_payment.student_fee.student.user.get_full_name(),
                    'student_id': fee_payment.student_fee.student.student_id,
                    'fee_name': fee_payment.student_fee.fee_structure.name,
                    'payment_amount': fee_payment.amount,
                    'payment_method': fee_payment.get_payment_method_display(),
                    'payment_date': fee_payment.payment_date,
                    'reference_number': fee_payment.reference_number,
                    'remaining_balance': fee_payment.student_fee.balance_amount,
                    'receipt_id': fee_payment.id,
                    'school_name': self._get_school_name(),
                },
                notification_type=NotificationType.PAYMENT_CONFIRMATION
            )
            
            return self._send_notification(context)
            
        except Exception as e:
            logger.error(f"Error sending payment confirmation: {str(e)}")
            return False
    
    def send_scholarship_award_notification(self, scholarship_recipient) -> bool:
        """Send scholarship award notification"""
        try:
            from .models import ScholarshipRecipient
            
            if not isinstance(scholarship_recipient, ScholarshipRecipient):
                logger.error("Invalid scholarship_recipient object provided")
                return False
            
            recipient_email = scholarship_recipient.student.user.email
            if not recipient_email:
                logger.warning(f"No email found for student {scholarship_recipient.student}")
                return False
            
            context = NotificationContext(
                recipient_email=recipient_email,
                recipient_name=scholarship_recipient.student.user.get_full_name(),
                subject=f"Scholarship Award - {scholarship_recipient.scholarship.name}",
                template_name="scholarship_award",
                context_data={
                    'student_name': scholarship_recipient.student.user.get_full_name(),
                    'student_id': scholarship_recipient.student.student_id,
                    'scholarship_name': scholarship_recipient.scholarship.name,
                    'scholarship_type': scholarship_recipient.scholarship.get_scholarship_type_display(),
                    'awarded_amount': scholarship_recipient.awarded_amount,
                    'start_date': scholarship_recipient.start_date,
                    'end_date': scholarship_recipient.end_date,
                    'academic_year': scholarship_recipient.scholarship.academic_year,
                    'school_name': self._get_school_name(),
                },
                notification_type=NotificationType.SCHOLARSHIP_AWARD
            )
            
            return self._send_notification(context)
            
        except Exception as e:
            logger.error(f"Error sending scholarship award notification: {str(e)}")
            return False
    
    def send_payroll_processing_notification(self, staff_payroll) -> bool:
        """Send payroll processing notification"""
        try:
            from .models import StaffPayroll
            
            if not isinstance(staff_payroll, StaffPayroll):
                logger.error("Invalid staff_payroll object provided")
                return False
            
            recipient_email = staff_payroll.teacher.user.email
            if not recipient_email:
                logger.warning(f"No email found for teacher {staff_payroll.teacher}")
                return False
            
            context = NotificationContext(
                recipient_email=recipient_email,
                recipient_name=staff_payroll.teacher.user.get_full_name(),
                subject=f"Payroll Processed - {staff_payroll.month.strftime('%B %Y')}",
                template_name="payroll_processing",
                context_data={
                    'teacher_name': staff_payroll.teacher.user.get_full_name(),
                    'employee_id': staff_payroll.teacher.employee_id,
                    'month': staff_payroll.month.strftime('%B %Y'),
                    'gross_salary': staff_payroll.gross_salary,
                    'tax_deduction': staff_payroll.tax_deduction,
                    'pension_deduction': staff_payroll.pension_deduction,
                    'other_deductions': staff_payroll.other_deductions,
                    'net_salary': staff_payroll.net_salary,
                    'payment_date': staff_payroll.payment_date,
                    'is_paid': staff_payroll.is_paid,
                    'school_name': self._get_school_name(),
                },
                notification_type=NotificationType.PAYROLL_PROCESSING
            )
            
            return self._send_notification(context)
            
        except Exception as e:
            logger.error(f"Error sending payroll processing notification: {str(e)}")
            return False
    
    def send_bulk_overdue_reminders(self, days_overdue: int = 1) -> Dict[str, int]:
        """Send reminders for all overdue payments"""
        try:
            from .models import StudentFee
            
            overdue_fees = StudentFee.objects.filter(
                status='overdue',
                due_date__lt=timezone.now().date() - timedelta(days=days_overdue)
            ).select_related('student__user', 'fee_structure')
            
            results = {'sent': 0, 'failed': 0, 'skipped': 0}
            
            for fee in overdue_fees:
                if self.send_payment_reminder(fee, days_until_due=-days_overdue):
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            
            logger.info(f"Bulk overdue reminders: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error sending bulk overdue reminders: {str(e)}")
            return {'sent': 0, 'failed': 0, 'skipped': 0}
    
    def send_bulk_upcoming_due_reminders(self, days_ahead: int = 7) -> Dict[str, int]:
        """Send reminders for payments due soon"""
        try:
            from .models import StudentFee
            
            upcoming_due = StudentFee.objects.filter(
                status__in=['pending', 'partial'],
                due_date__lte=timezone.now().date() + timedelta(days=days_ahead),
                due_date__gt=timezone.now().date()
            ).select_related('student__user', 'fee_structure')
            
            results = {'sent': 0, 'failed': 0, 'skipped': 0}
            
            for fee in upcoming_due:
                days_until_due = (fee.due_date - timezone.now().date()).days
                if self.send_payment_reminder(fee, days_until_due=days_until_due):
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            
            logger.info(f"Bulk upcoming due reminders: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error sending bulk upcoming due reminders: {str(e)}")
            return {'sent': 0, 'failed': 0, 'skipped': 0}
    
    def retry_failed_notifications(self) -> Dict[str, int]:
        """Retry failed notifications that haven't exceeded max retries"""
        try:
            from .models import NotificationLog
            failed_notifications = NotificationLog.objects.filter(
                status__in=['failed', 'retry']
            ).filter(
                retry_count__lt=models.F('max_retries')
            )
            
            results = {'retried': 0, 'succeeded': 0, 'failed': 0}
            
            for notification in failed_notifications:
                if self._retry_notification(notification):
                    results['succeeded'] += 1
                else:
                    results['failed'] += 1
                results['retried'] += 1
            
            logger.info(f"Notification retry results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error retrying failed notifications: {str(e)}")
            return {'retried': 0, 'succeeded': 0, 'failed': 0}
    
    def _send_notification(self, context: NotificationContext) -> bool:
        """Internal method to send notification and log the attempt"""
        from .models import NotificationLog
        notification_log = None
        
        try:
            # Create notification log entry
            notification_log = NotificationLog.objects.create(
                notification_type=context.notification_type.value,
                recipient_email=context.recipient_email,
                recipient_name=context.recipient_name,
                subject=context.subject,
                context_data=context.context_data,
                status='pending'
            )
            
            # Get or create template
            template = self._get_template(context.template_name, context.notification_type)
            
            # Render email content
            html_content = self._render_template(template.html_template, context.context_data)
            text_content = self._render_template(template.text_template, context.context_data) if template.text_template else None
            subject = self._render_template(template.subject_template, context.context_data)
            
            # Send email
            if self._send_email(context.recipient_email, subject, html_content, text_content):
                notification_log.status = 'sent'
                notification_log.sent_at = timezone.now()
                notification_log.save()
                return True
            else:
                notification_log.status = 'failed'
                notification_log.error_message = "Email sending failed"
                notification_log.save()
                return False
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error sending notification: {error_msg}")
            
            if notification_log:
                notification_log.status = 'failed'
                notification_log.error_message = error_msg
                notification_log.save()
            
            return False
    
    def _retry_notification(self, notification_log: 'NotificationLog') -> bool:
        """Retry a failed notification"""
        try:
            notification_log.retry_count += 1
            notification_log.status = 'retry'
            notification_log.save()
            
            # Recreate context from log data
            context = NotificationContext(
                recipient_email=notification_log.recipient_email,
                recipient_name=notification_log.recipient_name,
                subject=notification_log.subject,
                template_name=notification_log.notification_type,
                context_data=notification_log.context_data,
                notification_type=NotificationType(notification_log.notification_type)
            )
            
            # Get template and render content
            template = self._get_template(context.template_name, context.notification_type)
            html_content = self._render_template(template.html_template, context.context_data)
            text_content = self._render_template(template.text_template, context.context_data) if template.text_template else None
            subject = self._render_template(template.subject_template, context.context_data)
            
            # Attempt to send
            if self._send_email(context.recipient_email, subject, html_content, text_content):
                notification_log.status = 'sent'
                notification_log.sent_at = timezone.now()
                notification_log.save()
                return True
            else:
                notification_log.status = 'failed'
                notification_log.error_message = "Retry failed"
                notification_log.save()
                return False
                
        except Exception as e:
            notification_log.status = 'failed'
            notification_log.error_message = f"Retry error: {str(e)}"
            notification_log.save()
            return False
    
    def _send_email(self, recipient_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Send email using Django's email backend"""
        try:
            if text_content:
                # Send multipart email
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=self.default_from_email,
                    to=[recipient_email]
                )
                email.attach_alternative(html_content, "text/html")
                email.send()
            else:
                # Send HTML email only
                send_mail(
                    subject=subject,
                    message="",  # Empty plain text
                    html_message=html_content,
                    from_email=self.default_from_email,
                    recipient_list=[recipient_email],
                    fail_silently=False
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            return False
    
    def _get_template(self, template_name: str, notification_type: NotificationType) -> 'NotificationTemplate':
        """Get or create notification template"""
        try:
            from .models import NotificationTemplate
            template = NotificationTemplate.objects.get(
                template_type=notification_type.value,
                is_active=True
            )
            return template
        except NotificationTemplate.DoesNotExist:
            # Create default template
            return self._create_default_template(notification_type)
    
    def _create_default_template(self, notification_type: NotificationType) -> 'NotificationTemplate':
        """Create default template for notification type"""
        from .models import NotificationTemplate
        templates = {
            NotificationType.PAYMENT_REMINDER: {
                'name': 'Default Payment Reminder',
                'subject_template': 'Payment Reminder - {{ fee_name }}',
                'html_template': self._get_default_payment_reminder_html(),
                'text_template': self._get_default_payment_reminder_text(),
            },
            NotificationType.PAYMENT_CONFIRMATION: {
                'name': 'Default Payment Confirmation',
                'subject_template': 'Payment Confirmation - Receipt #{{ receipt_id }}',
                'html_template': self._get_default_payment_confirmation_html(),
                'text_template': self._get_default_payment_confirmation_text(),
            },
            NotificationType.SCHOLARSHIP_AWARD: {
                'name': 'Default Scholarship Award',
                'subject_template': 'Scholarship Award - {{ scholarship_name }}',
                'html_template': self._get_default_scholarship_award_html(),
                'text_template': self._get_default_scholarship_award_text(),
            },
            NotificationType.PAYROLL_PROCESSING: {
                'name': 'Default Payroll Processing',
                'subject_template': 'Payroll Processed - {{ month }}',
                'html_template': self._get_default_payroll_processing_html(),
                'text_template': self._get_default_payroll_processing_text(),
            },
        }
        
        template_data = templates.get(notification_type, {
            'name': f'Default {notification_type.value}',
            'subject_template': f'{notification_type.value} Notification',
            'html_template': '<p>Default notification template</p>',
            'text_template': 'Default notification template',
        })
        
        return NotificationTemplate.objects.create(
            template_type=notification_type.value,
            **template_data
        )
    
    def _render_template(self, template_string: str, context_data: Dict[str, Any]) -> str:
        """Render template string with context data"""
        try:
            from django.template import Template, Context
            template = Template(template_string)
            context = Context(context_data)
            return template.render(context)
        except Exception as e:
            logger.error(f"Template rendering error: {str(e)}")
            return template_string
    
    def _get_school_name(self) -> str:
        """Get school name from settings"""
        try:
            from .models import SchoolSettings
            settings = SchoolSettings.objects.first()
            return settings.school_name if settings else "School"
        except:
            return "School"
    
    # Default template methods
    def _get_default_payment_reminder_html(self) -> str:
        try:
            return render_to_string('notifications/email/payment_reminder.html', {})
        except:
            return """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Payment Reminder</h2>
                <p>Dear {{ student_name }},</p>
                <p>This is a reminder that your payment for <strong>{{ fee_name }}</strong> is due.</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Payment Details:</h3>
                    <ul>
                        <li><strong>Student ID:</strong> {{ student_id }}</li>
                        <li><strong>Fee:</strong> {{ fee_name }}</li>
                        <li><strong>Total Amount:</strong> ${{ total_amount }}</li>
                        <li><strong>Paid Amount:</strong> ${{ paid_amount }}</li>
                        <li><strong>Balance:</strong> ${{ balance_amount }}</li>
                        <li><strong>Due Date:</strong> {{ due_date }}</li>
                    </ul>
                </div>
                <p>Please make your payment as soon as possible to avoid any late fees.</p>
                <p>Thank you,<br>{{ school_name }}</p>
            </div>
            """
    
    def _get_default_payment_reminder_text(self) -> str:
        return """
        Payment Reminder
        
        Dear {{ student_name }},
        
        This is a reminder that your payment for {{ fee_name }} is due.
        
        Payment Details:
        - Student ID: {{ student_id }}
        - Fee: {{ fee_name }}
        - Total Amount: ${{ total_amount }}
        - Paid Amount: ${{ paid_amount }}
        - Balance: ${{ balance_amount }}
        - Due Date: {{ due_date }}
        
        Please make your payment as soon as possible to avoid any late fees.
        
        Thank you,
        {{ school_name }}
        """
    
    def _get_default_payment_confirmation_html(self) -> str:
        try:
            return render_to_string('notifications/email/payment_confirmation.html', {})
        except:
            return """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #28a745;">Payment Confirmation</h2>
                <p>Dear {{ student_name }},</p>
                <p>We have successfully received your payment. Thank you!</p>
                <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Payment Details:</h3>
                    <ul>
                        <li><strong>Receipt ID:</strong> {{ receipt_id }}</li>
                        <li><strong>Student ID:</strong> {{ student_id }}</li>
                        <li><strong>Fee:</strong> {{ fee_name }}</li>
                        <li><strong>Payment Amount:</strong> ${{ payment_amount }}</li>
                        <li><strong>Payment Method:</strong> {{ payment_method }}</li>
                        <li><strong>Payment Date:</strong> {{ payment_date }}</li>
                        <li><strong>Reference Number:</strong> {{ reference_number }}</li>
                        <li><strong>Remaining Balance:</strong> ${{ remaining_balance }}</li>
                    </ul>
                </div>
                <p>Please keep this confirmation for your records.</p>
                <p>Thank you,<br>{{ school_name }}</p>
            </div>
            """
    
    def _get_default_payment_confirmation_text(self) -> str:
        return """
        Payment Confirmation
        
        Dear {{ student_name }},
        
        We have successfully received your payment. Thank you!
        
        Payment Details:
        - Receipt ID: {{ receipt_id }}
        - Student ID: {{ student_id }}
        - Fee: {{ fee_name }}
        - Payment Amount: ${{ payment_amount }}
        - Payment Method: {{ payment_method }}
        - Payment Date: {{ payment_date }}
        - Reference Number: {{ reference_number }}
        - Remaining Balance: ${{ remaining_balance }}
        
        Please keep this confirmation for your records.
        
        Thank you,
        {{ school_name }}
        """
    
    def _get_default_scholarship_award_html(self) -> str:
        try:
            return render_to_string('notifications/email/scholarship_award.html', {})
        except:
            return """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #007bff;">Scholarship Award Notification</h2>
                <p>Dear {{ student_name }},</p>
                <p>Congratulations! You have been awarded a scholarship.</p>
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Scholarship Details:</h3>
                    <ul>
                        <li><strong>Student ID:</strong> {{ student_id }}</li>
                        <li><strong>Scholarship:</strong> {{ scholarship_name }}</li>
                        <li><strong>Type:</strong> {{ scholarship_type }}</li>
                        <li><strong>Award Amount:</strong> ${{ awarded_amount }}</li>
                        <li><strong>Academic Year:</strong> {{ academic_year }}</li>
                        <li><strong>Start Date:</strong> {{ start_date }}</li>
                        <li><strong>End Date:</strong> {{ end_date }}</li>
                    </ul>
                </div>
                <p>This scholarship will be automatically applied to your fee payments.</p>
                <p>Congratulations once again!<br>{{ school_name }}</p>
            </div>
            """
    
    def _get_default_scholarship_award_text(self) -> str:
        return """
        Scholarship Award Notification
        
        Dear {{ student_name }},
        
        Congratulations! You have been awarded a scholarship.
        
        Scholarship Details:
        - Student ID: {{ student_id }}
        - Scholarship: {{ scholarship_name }}
        - Type: {{ scholarship_type }}
        - Award Amount: ${{ awarded_amount }}
        - Academic Year: {{ academic_year }}
        - Start Date: {{ start_date }}
        - End Date: {{ end_date }}
        
        This scholarship will be automatically applied to your fee payments.
        
        Congratulations once again!
        {{ school_name }}
        """
    
    def _get_default_payroll_processing_html(self) -> str:
        try:
            return render_to_string('notifications/email/payroll_processing.html', {})
        except:
            return """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #6c757d;">Payroll Processing Notification</h2>
                <p>Dear {{ teacher_name }},</p>
                <p>Your payroll for {{ month }} has been processed.</p>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Payroll Details:</h3>
                    <ul>
                        <li><strong>Employee ID:</strong> {{ employee_id }}</li>
                        <li><strong>Month:</strong> {{ month }}</li>
                        <li><strong>Gross Salary:</strong> ${{ gross_salary }}</li>
                        <li><strong>Tax Deduction:</strong> ${{ tax_deduction }}</li>
                        <li><strong>Pension Deduction:</strong> ${{ pension_deduction }}</li>
                        <li><strong>Other Deductions:</strong> ${{ other_deductions }}</li>
                        <li><strong>Net Salary:</strong> ${{ net_salary }}</li>
                        {% if is_paid %}<li><strong>Payment Date:</strong> {{ payment_date }}</li>{% endif %}
                    </ul>
                </div>
                {% if is_paid %}
                <p>Your salary has been paid and should reflect in your account shortly.</p>
                {% else %}
                <p>Your salary will be paid soon. You will receive another notification once payment is completed.</p>
                {% endif %}
                <p>Thank you,<br>{{ school_name }}</p>
            </div>
            """
    
    def _get_default_payroll_processing_text(self) -> str:
        return """
        Payroll Processing Notification
        
        Dear {{ teacher_name }},
        
        Your payroll for {{ month }} has been processed.
        
        Payroll Details:
        - Employee ID: {{ employee_id }}
        - Month: {{ month }}
        - Gross Salary: ${{ gross_salary }}
        - Tax Deduction: ${{ tax_deduction }}
        - Pension Deduction: ${{ pension_deduction }}
        - Other Deductions: ${{ other_deductions }}
        - Net Salary: ${{ net_salary }}
        {% if is_paid %}- Payment Date: {{ payment_date }}{% endif %}
        
        {% if is_paid %}Your salary has been paid and should reflect in your account shortly.{% else %}Your salary will be paid soon. You will receive another notification once payment is completed.{% endif %}
        
        Thank you,
        {{ school_name }}
        """
    
    def send_custom_email(self, recipient_email: str, recipient_name: str, subject: str, html_content: str) -> bool:
        """Send custom email with provided HTML content"""
        from .models import NotificationLog
        try:
            if self._send_email(recipient_email, subject, html_content):
                NotificationLog.objects.create(
                    notification_type='custom',
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    subject=subject,
                    status='sent',
                    sent_at=timezone.now()
                )
                return True
            else:
                NotificationLog.objects.create(
                    notification_type='custom',
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    subject=subject,
                    status='failed',
                    error_message='Email sending failed'
                )
                return False
        except Exception as e:
            logger.error(f"Error sending custom email: {str(e)}")
            NotificationLog.objects.create(
                notification_type='custom',
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                subject=subject,
                status='failed',
                error_message=str(e)
            )
            return False


# Utility functions for scheduled tasks
def send_daily_payment_reminders():
    """Function to be called by scheduled tasks for daily payment reminders"""
    service = NotificationService()
    return service.send_bulk_upcoming_due_reminders(days_ahead=7)


def send_overdue_payment_reminders():
    """Function to be called by scheduled tasks for overdue payment reminders"""
    service = NotificationService()
    return service.send_bulk_overdue_reminders(days_overdue=1)


def retry_failed_notifications():
    """Function to be called by scheduled tasks to retry failed notifications"""
    service = NotificationService()
    return service.retry_failed_notifications()
