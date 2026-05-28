# Financial Reconciliation System

## Overview

The Financial Reconciliation System provides comprehensive financial validation and verification capabilities for the school management system. It automatically detects discrepancies, generates detailed reports, and can be scheduled to run daily with email notifications.

## Features

### 1. Payment Collection Reconciliation
- Verifies that total payments match recorded fee collections
- Checks balance calculations for accuracy
- Validates payment status consistency
- Detects overpayments and payment anomalies

### 2. Payroll Calculation Reconciliation
- Validates payroll calculations are mathematically correct
- Verifies gross salary, tax deductions, pension deductions
- Checks net salary calculations
- Detects excessive deductions and negative salaries

### 3. Scholarship Application Reconciliation
- Checks that scholarship deductions are properly applied to student fees
- Validates scholarship recipient limits
- Detects expired scholarships still marked active
- Identifies overlapping scholarships

### 4. Balance Verification
- Provides comprehensive balance verification reports
- Calculates overall financial position
- Breaks down payments by method
- Tracks income vs expenses

### 5. Discrepancy Detection
- Advanced algorithms to detect payment anomalies
- Identifies duplicate payments
- Detects unusual payment patterns
- Flags long overdue fees

### 6. Automated Scheduling
- Daily automated reconciliation checks
- Email notifications for discrepancies
- Audit trail logging
- Error notifications for system issues

## Usage

### Command Line Interface

Run reconciliation checks from the command line:

```bash
# Run comprehensive reconciliation (all checks)
python manage.py run_reconciliation --type all

# Run specific reconciliation type
python manage.py run_reconciliation --type payment
python manage.py run_reconciliation --type payroll
python manage.py run_reconciliation --type scholarship
python manage.py run_reconciliation --type balance

# Run with email notifications
python manage.py run_reconciliation --type all --email

# Run with date range for payment reconciliation
python manage.py run_reconciliation --type payment --start-date 2024-01-01 --end-date 2024-01-31

# Run payroll reconciliation for specific month
python manage.py run_reconciliation --type payroll --month 2024-01-01

# Run scholarship reconciliation for academic year
python manage.py run_reconciliation --type scholarship --year 2024-2025
```

### Python API

Use the reconciliation service in your Python code:

```python
from core.services_reconciliation import ReconciliationService
from django.utils import timezone

# Run payment collection reconciliation
result = ReconciliationService.reconcile_payment_collections()
if not result.is_balanced:
    print(f"Found {result.total_discrepancies} discrepancies")
    for disc in result.discrepancies:
        print(f"- {disc['description']}")

# Run comprehensive reconciliation
results = ReconciliationService.run_comprehensive_reconciliation()
overall_status = results['overall_status']
print(f"All balanced: {overall_status['all_balanced']}")
print(f"Total discrepancies: {overall_status['total_discrepancies']}")

# Generate detailed report
from core.services_reconciliation import ReconciliationReporter
report = ReconciliationReporter.generate_discrepancy_report(result)
print(report)
```

### Automated Scheduling

#### Using Celery (Recommended)

If Celery is configured, the reconciliation task is automatically available:

```python
# In your Celery configuration (celery.py)
from celery.schedules import crontab

app.conf.beat_schedule = {
    'daily-reconciliation': {
        'task': 'core.services_reconciliation.run_daily_reconciliation',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
    },
}
```

#### Using Django-Q

```python
# In your Django shell or management command
from django_q.tasks import schedule
from django_q.models import Schedule

schedule(
    'core.services_reconciliation.ReconciliationScheduler.schedule_daily_reconciliation',
    schedule_type=Schedule.DAILY,
    repeats=-1  # Repeat indefinitely
)
```

#### Using Cron

Add to your crontab:

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/project && python manage.py run_reconciliation --type all --email
```

## Reconciliation Results

### ReconciliationResult Object

Each reconciliation returns a `ReconciliationResult` object with:

- `reconciliation_type`: Type of reconciliation performed
- `is_balanced`: Boolean indicating if everything is balanced
- `discrepancies`: List of detected discrepancies
- `warnings`: List of warning messages
- `total_checked`: Number of items checked
- `total_discrepancies`: Number of discrepancies found
- `details`: Additional details and summary statistics

### Discrepancy Object

Each discrepancy contains:

- `description`: Human-readable description
- `expected`: Expected value
- `actual`: Actual value
- `difference`: Difference between expected and actual
- `item_id`: ID of the affected item
- `severity`: Severity level (critical, error, warning)
- `timestamp`: When the discrepancy was detected

## Email Notifications

When discrepancies are detected, email notifications are sent to:
- All users with `super_admin` role
- All superusers

Email includes:
- Number of discrepancies found
- Detailed reconciliation report
- Recommendations for addressing issues

## Best Practices

1. **Run Daily**: Schedule reconciliation to run daily during off-peak hours
2. **Review Promptly**: Address discrepancies as soon as they're detected
3. **Monitor Trends**: Track discrepancy patterns over time
4. **Test Changes**: Run reconciliation after making bulk financial changes
5. **Backup First**: Always backup data before correcting discrepancies

## Troubleshooting

### No Email Notifications Received

1. Check email configuration in `settings.py`
2. Verify admin users have valid email addresses
3. Check email logs for delivery errors

### Reconciliation Taking Too Long

1. Run reconciliation for specific date ranges
2. Consider running different reconciliation types separately
3. Optimize database queries with proper indexing

### False Positives

Some warnings may be expected:
- Overpayments may be intentional (credit for next term)
- Scholarship overlaps may be valid (multiple scholarships allowed)
- Review warnings carefully before taking action

## API Reference

### ReconciliationService

Main service class for financial reconciliation.

#### Methods

- `reconcile_payment_collections(start_date, end_date)`: Verify payment vs collection
- `reconcile_payroll_calculations(month)`: Validate payroll calculations
- `reconcile_scholarship_applications(academic_year)`: Check scholarship applications
- `reconcile_balance_verification(term)`: Verify financial balances
- `run_comprehensive_reconciliation(start_date, end_date)`: Run all reconciliations

### DiscrepancyDetector

Advanced discrepancy detection algorithms.

#### Methods

- `detect_payment_anomalies(student_fee)`: Detect payment anomalies
- `detect_payroll_anomalies(payroll)`: Detect payroll anomalies
- `detect_scholarship_anomalies(recipient)`: Detect scholarship anomalies

### ReconciliationReporter

Generate detailed reports with suggestions.

#### Methods

- `generate_discrepancy_report(reconciliation_result)`: Generate detailed report
- `generate_comprehensive_report(comprehensive_results)`: Generate comprehensive report

### ReconciliationScheduler

Automated scheduling and notifications.

#### Methods

- `schedule_daily_reconciliation()`: Run daily reconciliation
- `send_discrepancy_notification(results, report_text)`: Send email notification
- `send_error_notification(error_message)`: Send error notification

## Requirements Validation

This implementation validates the following requirements:

- **Requirement 11.1**: Payment vs collection verification
- **Requirement 11.2**: Payroll calculation validation
- **Requirement 11.3**: Scholarship application verification
- **Requirement 11.4**: Discrepancy detection and reporting
- **Requirement 11.5**: Balance verification functionality
- **Requirement 11.6**: Detailed error reporting with suggestions
- **Requirement 11.7**: Automated daily reconciliation scheduling

## Testing

Run the test suite:

```bash
# Run all reconciliation tests
python manage.py test core.test_reconciliation_services

# Run specific test case
python manage.py test core.test_reconciliation_services.ReconciliationServiceTestCase

# Run with verbose output
python manage.py test core.test_reconciliation_services --verbosity=2
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the test cases for usage examples
3. Consult the main documentation
4. Contact the development team
