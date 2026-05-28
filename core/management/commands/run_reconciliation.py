"""
Django Management Command for Running Financial Reconciliation

This command allows administrators to run financial reconciliation checks
from the command line or as part of automated scheduling.

Usage:
    python manage.py run_reconciliation [options]
    
Options:
    --type: Type of reconciliation (payment, payroll, scholarship, balance, all)
    --email: Send email notification if discrepancies found
    --month: Month for payroll reconciliation (YYYY-MM-DD)
    --year: Academic year for scholarship reconciliation (YYYY-YYYY)
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime
import json

from core.services_reconciliation import (
    ReconciliationService,
    ReconciliationReporter,
    ReconciliationScheduler
)
from core.models import Term


class Command(BaseCommand):
    help = 'Run financial reconciliation checks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            choices=['payment', 'payroll', 'scholarship', 'balance', 'all'],
            help='Type of reconciliation to run'
        )
        
        parser.add_argument(
            '--email',
            action='store_true',
            help='Send email notification if discrepancies found'
        )
        
        parser.add_argument(
            '--month',
            type=str,
            help='Month for payroll reconciliation (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--year',
            type=str,
            help='Academic year for scholarship reconciliation (e.g., 2024-2025)'
        )
        
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for payment reconciliation (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for payment reconciliation (YYYY-MM-DD format)'
        )
        
    def handle(self, *args, **options):
        recon_type = options['type']
        send_email = options['email']
        
        self.stdout.write(self.style.SUCCESS(
            f'\nStarting {recon_type} reconciliation...\n'
        ))
        
        try:
            if recon_type == 'all':
                self._run_comprehensive_reconciliation(options, send_email)
            elif recon_type == 'payment':
                self._run_payment_reconciliation(options)
            elif recon_type == 'payroll':
                self._run_payroll_reconciliation(options)
            elif recon_type == 'scholarship':
                self._run_scholarship_reconciliation(options)
            elif recon_type == 'balance':
                self._run_balance_reconciliation(options)
                
        except Exception as e:
            raise CommandError(f'Reconciliation failed: {str(e)}')
            
    def _run_comprehensive_reconciliation(self, options, send_email):
        """Run comprehensive reconciliation"""
        start_date = self._parse_date(options.get('start_date'))
        end_date = self._parse_date(options.get('end_date'))
        
        results = ReconciliationService.run_comprehensive_reconciliation(
            start_date, end_date
        )
        
        # Generate report
        report_text = ReconciliationReporter.generate_comprehensive_report(results)
        
        self.stdout.write(report_text)
        
        # Check if email notification needed
        overall_status = results.get('overall_status', {})
        if send_email and overall_status.get('requires_attention'):
            ReconciliationScheduler.send_discrepancy_notification(results, report_text)
            self.stdout.write(self.style.SUCCESS(
                '\nEmail notification sent to administrators.'
            ))
            
        # Summary
        if overall_status.get('all_balanced'):
            self.stdout.write(self.style.SUCCESS(
                '\n✓ All reconciliations balanced - no discrepancies found!'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'\n⚠ Found {overall_status.get("total_discrepancies", 0)} discrepancies - review required!'
            ))
            
    def _run_payment_reconciliation(self, options):
        """Run payment collection reconciliation"""
        start_date = self._parse_date(options.get('start_date'))
        end_date = self._parse_date(options.get('end_date'))
        
        result = ReconciliationService.reconcile_payment_collections(
            start_date, end_date
        )
        
        self._display_result(result)
        
    def _run_payroll_reconciliation(self, options):
        """Run payroll calculation reconciliation"""
        month = self._parse_date(options.get('month'))
        
        result = ReconciliationService.reconcile_payroll_calculations(month)
        
        self._display_result(result)
        
    def _run_scholarship_reconciliation(self, options):
        """Run scholarship application reconciliation"""
        academic_year = options.get('year')
        
        result = ReconciliationService.reconcile_scholarship_applications(
            academic_year
        )
        
        self._display_result(result)
        
    def _run_balance_reconciliation(self, options):
        """Run balance verification"""
        # Get active term
        term = Term.objects.filter(is_active=True).first()
        
        result = ReconciliationService.reconcile_balance_verification(term)
        
        self._display_result(result)
        
    def _display_result(self, result):
        """Display reconciliation result"""
        summary = result.get_summary()
        
        self.stdout.write(f'\nReconciliation Type: {summary["reconciliation_type"]}')
        self.stdout.write(f'Items Checked: {summary["total_checked"]}')
        self.stdout.write(f'Discrepancies Found: {summary["total_discrepancies"]}')
        
        if summary['is_balanced']:
            self.stdout.write(self.style.SUCCESS('\n✓ Balanced - no discrepancies found!'))
        else:
            self.stdout.write(self.style.WARNING('\n⚠ Discrepancies detected:'))
            for i, disc in enumerate(summary['discrepancies'][:10], 1):
                self.stdout.write(f'  {i}. {disc["description"]}')
                self.stdout.write(f'     Expected: {disc["expected"]}, Actual: {disc["actual"]}')
                
            if len(summary['discrepancies']) > 10:
                self.stdout.write(f'  ... and {len(summary["discrepancies"]) - 10} more')
                
        if summary.get('warnings'):
            self.stdout.write(self.style.WARNING('\nWarnings:'))
            for warning in summary['warnings'][:5]:
                self.stdout.write(f'  - {warning["message"]}')
                
        # Display summary details if available
        if 'details' in summary and 'summary' in summary['details']:
            self.stdout.write('\nSummary:')
            details = summary['details']['summary']
            for key, value in details.items():
                if isinstance(value, dict):
                    self.stdout.write(f'  {key}:')
                    for sub_key, sub_value in value.items():
                        self.stdout.write(f'    {sub_key}: {sub_value}')
                else:
                    self.stdout.write(f'  {key}: {value}')
                    
    def _parse_date(self, date_str):
        """Parse date string to datetime object"""
        if not date_str:
            return None
            
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise CommandError(f'Invalid date format: {date_str}. Use YYYY-MM-DD format.')
