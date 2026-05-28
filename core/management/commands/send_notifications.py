"""
Management command for sending scheduled notifications.

This command can be used with cron jobs or task schedulers to send
automated notifications like payment reminders and retry failed notifications.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.services_notification import (
    NotificationService,
    send_daily_payment_reminders,
    send_overdue_payment_reminders,
    retry_failed_notifications
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send scheduled notifications for financial management system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['payment_reminders', 'overdue_reminders', 'retry_failed', 'all'],
            default='all',
            help='Type of notifications to send'
        )
        
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=7,
            help='Days ahead to send payment reminders (default: 7)'
        )
        
        parser.add_argument(
            '--days-overdue',
            type=int,
            default=1,
            help='Days overdue to send overdue reminders (default: 1)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending notifications'
        )
    
    def handle(self, *args, **options):
        notification_type = options['type']
        days_ahead = options['days_ahead']
        days_overdue = options['days_overdue']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No notifications will be sent')
            )
        
        service = NotificationService()
        total_results = {'sent': 0, 'failed': 0, 'retried': 0, 'succeeded': 0}
        
        try:
            if notification_type in ['payment_reminders', 'all']:
                self.stdout.write('Sending payment reminders...')
                if not dry_run:
                    results = service.send_bulk_upcoming_due_reminders(days_ahead=days_ahead)
                    total_results['sent'] += results['sent']
                    total_results['failed'] += results['failed']
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Payment reminders: {results["sent"]} sent, {results["failed"]} failed'
                        )
                    )
                else:
                    # Dry run - count what would be sent
                    from core.models import StudentFee
                    from datetime import timedelta
                    
                    upcoming_due = StudentFee.objects.filter(
                        status__in=['pending', 'partial'],
                        due_date__lte=timezone.now().date() + timedelta(days=days_ahead),
                        due_date__gt=timezone.now().date()
                    ).count()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Would send {upcoming_due} payment reminders')
                    )
            
            if notification_type in ['overdue_reminders', 'all']:
                self.stdout.write('Sending overdue payment reminders...')
                if not dry_run:
                    results = service.send_bulk_overdue_reminders(days_overdue=days_overdue)
                    total_results['sent'] += results['sent']
                    total_results['failed'] += results['failed']
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Overdue reminders: {results["sent"]} sent, {results["failed"]} failed'
                        )
                    )
                else:
                    # Dry run - count what would be sent
                    from core.models import StudentFee
                    from datetime import timedelta
                    
                    overdue_fees = StudentFee.objects.filter(
                        status='overdue',
                        due_date__lt=timezone.now().date() - timedelta(days=days_overdue)
                    ).count()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Would send {overdue_fees} overdue reminders')
                    )
            
            if notification_type in ['retry_failed', 'all']:
                self.stdout.write('Retrying failed notifications...')
                if not dry_run:
                    results = service.retry_failed_notifications()
                    total_results['retried'] += results['retried']
                    total_results['succeeded'] += results['succeeded']
                    total_results['failed'] += results['failed']
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Retry results: {results["retried"]} retried, '
                            f'{results["succeeded"]} succeeded, {results["failed"]} failed'
                        )
                    )
                else:
                    # Dry run - count what would be retried
                    from core.models import NotificationLog
                    from django.db import models
                    
                    failed_notifications = NotificationLog.objects.filter(
                        status__in=['failed', 'retry']
                    ).filter(
                        retry_count__lt=models.F('max_retries')
                    ).count()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Would retry {failed_notifications} failed notifications')
                    )
            
            # Summary
            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSUMMARY: {total_results["sent"]} sent, '
                        f'{total_results["failed"]} failed, '
                        f'{total_results["retried"]} retried, '
                        f'{total_results["succeeded"]} retry succeeded'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\nDry run completed - no notifications were sent')
                )
                
        except Exception as e:
            logger.error(f"Error in send_notifications command: {str(e)}")
            raise CommandError(f'Failed to send notifications: {str(e)}')