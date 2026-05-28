from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from core.models_features import FeatureFlag, FeatureControlAdmin, SchoolMembership, SchoolTenant
from core.models_license import SystemLicense
from core.tenant_permissions import grant_school_admin_permissions
from core.models import (
    AcademicEvent,
    BookCategory,
    Curriculum,
    FinancialAuditLog,
    FinancialTransaction,
    GeneratedReport,
    GradingSystem,
    Holiday,
    NotificationLog,
    NotificationTemplate,
    PayrollStructure,
    ReportCardSettings,
    RoomAssignment,
    SchoolClass,
    SchoolSettings,
    Scholarship,
    Student,
    Subject,
    Teacher,
    Term,
    TimeSlot,
)
from core.models_attendance import AttendanceSession, Visitor
from core.services_report_customization import ScheduledReport
import hashlib
import os

class Command(BaseCommand):
    help = 'Setup feature control admin and initial features'

    def handle(self, *args, **kwargs):
        # Create admin
        phone = os.environ.get('FEATURE_CONTROL_ADMIN_PHONE', '09125442676')
        password = os.environ.get('FEATURE_CONTROL_ADMIN_PASSWORD')
        if not password:
            self.stderr.write(self.style.ERROR('Set FEATURE_CONTROL_ADMIN_PASSWORD before running this command.'))
            return
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        admin, created = FeatureControlAdmin.objects.get_or_create(
            phone=phone,
            defaults={'password_hash': password_hash}
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Admin created: {phone}'))
        else:
            admin.password_hash = password_hash
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Admin password updated: {phone}'))
        
        # Create initial features
        features = [
            ('academic_timetable', 'Academic Timetable', 'Manage class timetables and schedules', 'academic'),
            ('timetable_management', 'Timetable Management', 'Manage class timetables and schedules', 'academic'),
            ('academic_assignments', 'Assignments', 'Create and manage student assignments', 'academic'),
            ('assignments', 'Assignments', 'Create and manage student assignments', 'academic'),
            ('academic_lesson_plans', 'Lesson Plans', 'Teacher lesson planning system', 'academic'),
            ('lesson_plans', 'Lesson Plans', 'Teacher lesson planning system', 'academic'),
            ('academic_curriculum', 'Curriculum Management', 'Manage school curriculum', 'academic'),
            ('curriculum_management', 'Curriculum Management', 'Manage school curriculum', 'academic'),
            
            ('financial_management', 'Financial Management', 'Financial dashboard and tools', 'financial'),
            ('financial_fees', 'Fee Management', 'Student fee collection and tracking', 'financial'),
            ('financial_expenses', 'Expense Tracking', 'School expense management', 'financial'),
            ('financial_payroll', 'Payroll System', 'Staff salary management', 'financial'),
            ('financial_reports', 'Financial Reports', 'Financial analytics and reports', 'financial'),
            ('financial_transactions', 'Financial Transactions', 'Income and expense transactions', 'financial'),
            ('financial_scholarships', 'Scholarships', 'Scholarship awards and tracking', 'financial'),
            ('financial_analytics', 'Financial Analytics', 'Financial analytics dashboard', 'financial'),
            
            ('attendance_marking', 'Attendance Marking', 'Mark student and staff attendance', 'attendance'),
            ('attendance_id_cards', 'ID Card Generation', 'Generate and manage ID cards', 'attendance'),
            ('id_card_generation', 'ID Card Generation', 'Generate and manage ID cards', 'attendance'),
            ('attendance_visitors', 'Visitor Log', 'Track school visitors', 'attendance'),
            ('attendance_reports', 'Attendance Reports', 'View attendance statistics', 'attendance'),
            
            ('library_books', 'Book Management', 'Manage library books', 'library'),
            ('library_management', 'Library Management', 'Library dashboard and management tools', 'library'),
            ('library_borrowing', 'Book Borrowing', 'Track book loans', 'library'),
            ('library_fines', 'Library Fines', 'Manage overdue fines', 'library'),
            
            ('communication_sms', 'SMS Notifications', 'Send SMS to parents/students', 'communication'),
            ('communication_email', 'Email System', 'Send emails', 'communication'),
            ('communication_announcements', 'Announcements', 'School announcements', 'communication'),
            
            ('cbt_quiz', 'Computer Based Test (CBT)', 'Online quiz and CBT system', 'reports'),
            ('reports_results', 'Result Management', 'Student results and report cards', 'reports'),
            ('reports_analytics', 'Analytics Dashboard', 'School performance analytics', 'reports'),
            ('reports_broadsheet', 'Broadsheet', 'Class broadsheet generation', 'reports'),
            
            ('system_users', 'User Management', 'Manage system users', 'system'),
            ('system_students', 'Student Management', 'Manage student records', 'system'),
            ('system_staff', 'Staff Management', 'Manage staff and teacher records', 'system'),
            ('system_backup', 'Backup System', 'Database backup and restore', 'system'),
            ('system_settings', 'School Settings', 'Configure school information', 'system'),
        ]
        
        for name, display_name, description, category in features:
            feature, created = FeatureFlag.objects.get_or_create(
                name=name,
                defaults={
                    'display_name': display_name,
                    'description': description,
                    'category': category,
                    'is_enabled': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created feature: {display_name}'))
            else:
                feature.display_name = display_name
                feature.description = description
                feature.category = category
                feature.save(update_fields=['display_name', 'description', 'category', 'updated_at'])

        default_school, school_created = SchoolTenant.objects.get_or_create(
            slug='default-school',
            defaults={
                'name': 'Default School',
                'plan': 'premium',
                'is_active': True,
            }
        )
        if school_created:
            self.stdout.write(self.style.SUCCESS('Created default tenant school'))

        SystemLicense.objects.get_or_create(
            school=default_school,
            defaults={
                'school_name': default_school.name,
                'license_key': 'DEFAULT-SCHOOL-TRIAL',
                'expiry_date': timezone.now().date() + timedelta(days=365),
            }
        )

        SchoolSettings.objects.get_or_create(
            school=default_school,
            defaults={
                'school_name': default_school.name,
                'school_address': 'Configure school address',
                'principal_name': 'Principal',
            }
        )

        User = get_user_model()
        for user in User.objects.all():
            SchoolMembership.objects.get_or_create(
                school=default_school,
                user=user,
                defaults={
                    'primary_role': user.role,
                    'extra_roles': user.extra_roles or [],
                    'is_active': user.is_active,
                }
            )
            if user.has_role('super_admin') or user.is_superuser:
                grant_school_admin_permissions(user)

        tenant_owned_models = [
            AcademicEvent,
            AttendanceSession,
            BookCategory,
            Curriculum,
            FinancialAuditLog,
            FinancialTransaction,
            GeneratedReport,
            GradingSystem,
            Holiday,
            NotificationLog,
            NotificationTemplate,
            PayrollStructure,
            ReportCardSettings,
            RoomAssignment,
            ScheduledReport,
            Scholarship,
            SchoolClass,
            Student,
            Subject,
            Teacher,
            Term,
            TimeSlot,
            Visitor,
        ]
        for model in tenant_owned_models:
            manager = getattr(model, 'all_objects', model.objects)
            updated = manager.filter(school__isnull=True).update(school=default_school)
            if updated:
                self.stdout.write(self.style.SUCCESS(f'Attached {updated} {model.__name__} record(s) to {default_school.name}'))
        
        self.stdout.write(self.style.SUCCESS('\nFeature Control Setup Complete!'))
        self.stdout.write(self.style.SUCCESS(f'Login at: /feature-control/'))
        self.stdout.write(self.style.SUCCESS(f'Phone: {phone}'))
        self.stdout.write(self.style.SUCCESS(f'Password: {password}'))
