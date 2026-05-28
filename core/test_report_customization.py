"""
Tests for Report Customization and Scheduling Services

Requirements: 9.6, 9.7 - Report customization and scheduling functionality
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .services_report_customization import (
    ReportCustomizationService, ScheduledReport, ReportExecution,
    ReportParameters, ChartConfiguration
)

User = get_user_model()


class ReportCustomizationServiceTest(TestCase):
    """Test the ReportCustomizationService functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123',
            role='super_admin'
        )
    
    def test_get_default_chart_configs(self):
        """Test getting default chart configurations for different report types"""
        # Test monthly summary charts
        configs = ReportCustomizationService.get_default_chart_configs('monthly_summary')
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0].chart_type, 'doughnut')
        self.assertEqual(configs[0].title, 'Income Breakdown')
        
        # Test fee collection charts
        configs = ReportCustomizationService.get_default_chart_configs('fee_collection')
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0].chart_type, 'pie')
        
        # Test unknown report type
        configs = ReportCustomizationService.get_default_chart_configs('unknown')
        self.assertEqual(len(configs), 0)
    
    def test_validate_report_parameters(self):
        """Test parameter validation for different report types"""
        # Test valid monthly summary parameters
        params = {'year': 2024, 'month': 6}
        errors = ReportCustomizationService.validate_report_parameters('monthly_summary', params)
        self.assertEqual(len(errors), 0)
        
        # Test invalid year
        params = {'year': 1999, 'month': 6}
        errors = ReportCustomizationService.validate_report_parameters('monthly_summary', params)
        self.assertGreater(len(errors), 0)
        self.assertIn('Year must be between 2000 and 2100', errors)
        
        # Test invalid month
        params = {'year': 2024, 'month': 13}
        errors = ReportCustomizationService.validate_report_parameters('monthly_summary', params)
        self.assertGreater(len(errors), 0)
        self.assertIn('Month must be between 1 and 12', errors)
    
    def test_create_scheduled_report(self):
        """Test creating a scheduled report"""
        scheduled_report = ReportCustomizationService.create_scheduled_report(
            name='Test Monthly Report',
            report_type='monthly_summary',
            parameters={'year': 2024, 'month': 6, 'include_charts': True},
            frequency='monthly',
            recipients=['test@example.com'],
            user=self.user,
            description='Test report description'
        )
        
        self.assertIsInstance(scheduled_report, ScheduledReport)
        self.assertEqual(scheduled_report.name, 'Test Monthly Report')
        self.assertEqual(scheduled_report.report_type, 'monthly_summary')
        self.assertEqual(scheduled_report.frequency, 'monthly')
        self.assertEqual(scheduled_report.recipients, ['test@example.com'])
        self.assertEqual(scheduled_report.created_by, self.user)
        self.assertTrue(scheduled_report.is_active)
    
    def test_create_scheduled_report_validation_errors(self):
        """Test scheduled report creation with validation errors"""
        # Test with invalid parameters
        with self.assertRaises(ValueError):
            ReportCustomizationService.create_scheduled_report(
                name='Test Report',
                report_type='monthly_summary',
                parameters={'year': 1999},  # Invalid year
                frequency='monthly',
                recipients=['test@example.com'],
                user=self.user
            )
        
        # Test with no recipients
        with self.assertRaises(ValueError):
            ReportCustomizationService.create_scheduled_report(
                name='Test Report',
                report_type='monthly_summary',
                parameters={'year': 2024, 'month': 6},
                frequency='monthly',
                recipients=[],  # No recipients
                user=self.user
            )
    
    def test_get_report_templates(self):
        """Test getting predefined report templates"""
        templates = ReportCustomizationService.get_report_templates()
        
        self.assertIsInstance(templates, dict)
        self.assertIn('monthly_financial_overview', templates)
        self.assertIn('weekly_fee_collection', templates)
        self.assertIn('quarterly_scholarship_review', templates)
        
        # Check template structure
        template = templates['monthly_financial_overview']
        self.assertIn('name', template)
        self.assertIn('report_type', template)
        self.assertIn('parameters', template)
        self.assertIn('frequency', template)
    
    def test_get_available_customization_options(self):
        """Test getting customization options for report types"""
        options = ReportCustomizationService.get_available_customization_options('monthly_summary')
        
        self.assertIsInstance(options, dict)
        self.assertIn('include_charts', options)
        self.assertIn('export_formats', options)
        self.assertIn('year', options)
        self.assertIn('month', options)
        
        # Check option structure
        year_option = options['year']
        self.assertEqual(year_option['type'], 'select')
        self.assertEqual(year_option['label'], 'Year')
        self.assertIn('options', year_option)


class ScheduledReportModelTest(TestCase):
    """Test the ScheduledReport model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123',
            role='super_admin'
        )
    
    def test_calculate_next_run_daily(self):
        """Test calculating next run time for daily frequency"""
        report = ScheduledReport.objects.create(
            name='Daily Test Report',
            report_type='monthly_summary',
            parameters={'year': 2024, 'month': 6},
            frequency='daily',
            recipients=['test@example.com'],
            created_by=self.user,
            next_run=timezone.now()
        )
        
        original_next_run = report.next_run
        new_next_run = report.calculate_next_run()
        
        # Should be approximately 1 day later
        time_diff = new_next_run - original_next_run
        self.assertAlmostEqual(time_diff.total_seconds(), 86400, delta=60)  # Within 1 minute
    
    def test_calculate_next_run_monthly(self):
        """Test calculating next run time for monthly frequency"""
        report = ScheduledReport.objects.create(
            name='Monthly Test Report',
            report_type='monthly_summary',
            parameters={'year': 2024, 'month': 6},
            frequency='monthly',
            recipients=['test@example.com'],
            created_by=self.user,
            next_run=timezone.now()
        )
        
        original_next_run = report.next_run
        new_next_run = report.calculate_next_run()
        
        # Should be approximately 1 month later
        self.assertGreater(new_next_run, original_next_run)
        self.assertLess((new_next_run - original_next_run).days, 32)  # Less than 32 days
        self.assertGreaterEqual((new_next_run - original_next_run).days, 28)  # 28 days or more


class ReportCustomizationViewsTest(TestCase):
    """Test the report customization views"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123',
            role='super_admin'
        )
        self.client.login(username='testadmin', password='testpass123')
    
    def test_report_customization_options_view(self):
        """Test the report customization options API endpoint"""
        url = reverse('financial:report_customization_options', args=['monthly_summary'])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertIn('options', data)
        self.assertIn('chart_configs', data)
        
        # Check that options contain expected fields
        options = data['options']
        self.assertIn('include_charts', options)
        self.assertIn('year', options)
        self.assertIn('month', options)
    
    def test_create_scheduled_report_view(self):
        """Test creating a scheduled report via POST"""
        url = reverse('financial:create_scheduled_report')
        data = {
            'name': 'Test Scheduled Report',
            'description': 'Test description',
            'report_type': 'monthly_summary',
            'frequency': 'monthly',
            'recipients': 'test@example.com, admin@example.com',
            'year': '2024',
            'month': '6',
            'include_charts': 'on'
        }
        
        response = self.client.post(url, data)
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # Check that report was created
        reports = ScheduledReport.objects.filter(name='Test Scheduled Report')
        self.assertEqual(reports.count(), 1)
        
        report = reports.first()
        self.assertEqual(report.report_type, 'monthly_summary')
        self.assertEqual(report.frequency, 'monthly')
        self.assertEqual(len(report.recipients), 2)
        self.assertIn('test@example.com', report.recipients)
    
    def test_validate_report_parameters_view(self):
        """Test the parameter validation API endpoint"""
        url = reverse('financial:validate_report_parameters')
        data = {
            'report_type': 'monthly_summary',
            'year': '2024',
            'month': '6'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['success'])
        self.assertEqual(len(data['errors']), 0)
        self.assertIn('parameters', data)
    
    def test_validate_report_parameters_with_errors(self):
        """Test parameter validation with invalid parameters"""
        url = reverse('financial:validate_report_parameters')
        data = {
            'report_type': 'monthly_summary',
            'year': '1999',  # Invalid year
            'month': '13'    # Invalid month
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertFalse(data['success'])
        self.assertGreater(len(data['errors']), 0)
    
    def test_unauthorized_access(self):
        """Test that non-admin users cannot access customization features"""
        # Create non-admin user
        non_admin = User.objects.create_user(
            username='student',
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        
        # Login as non-admin
        self.client.logout()
        self.client.login(username='student', password='testpass123')
        
        # Try to access customization options
        url = reverse('financial:report_customization_options', args=['monthly_summary'])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Unauthorized')


class ChartConfigurationTest(TestCase):
    """Test the ChartConfiguration dataclass"""
    
    def test_chart_configuration_creation(self):
        """Test creating a chart configuration"""
        config = ChartConfiguration(
            chart_type='bar',
            title='Test Chart',
            colors=['#ff0000', '#00ff00', '#0000ff'],
            show_legend=True,
            height=300
        )
        
        self.assertEqual(config.chart_type, 'bar')
        self.assertEqual(config.title, 'Test Chart')
        self.assertEqual(len(config.colors), 3)
        self.assertTrue(config.show_legend)
        self.assertEqual(config.height, 300)
    
    def test_chart_configuration_to_dict(self):
        """Test converting chart configuration to dictionary"""
        config = ChartConfiguration(
            chart_type='pie',
            title='Pie Chart',
            colors=['#red', '#blue']
        )
        
        config_dict = config.to_dict()
        
        self.assertIsInstance(config_dict, dict)
        self.assertEqual(config_dict['chart_type'], 'pie')
        self.assertEqual(config_dict['title'], 'Pie Chart')
        self.assertIn('colors', config_dict)
        self.assertIn('show_legend', config_dict)
        self.assertIn('responsive', config_dict)


class ReportParametersTest(TestCase):
    """Test the ReportParameters dataclass"""
    
    def test_report_parameters_validation_success(self):
        """Test successful parameter validation"""
        params = ReportParameters(
            report_type='monthly_summary',
            date_range=(datetime(2024, 1, 1).date(), datetime(2024, 1, 31).date()),
            filters={'status': 'active'},
            include_charts=True
        )
        
        errors = params.validate()
        self.assertEqual(len(errors), 0)
    
    def test_report_parameters_validation_errors(self):
        """Test parameter validation with errors"""
        # Invalid report type
        params = ReportParameters(
            report_type='invalid_type',
            date_range=(datetime(2024, 1, 31).date(), datetime(2024, 1, 1).date()),  # End before start
            export_formats=['invalid_format']
        )
        
        errors = params.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('Invalid report type' in error for error in errors))
        self.assertTrue(any('Start date must be before end date' in error for error in errors))
        self.assertTrue(any('Invalid export formats' in error for error in errors))