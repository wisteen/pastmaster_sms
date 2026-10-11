from django.conf import settings
from django.db import migrations, models


STAFF_ROLES = {
    'subject_teacher', 'class_teacher', 'super_admin', 'administrator',
    'security', 'cleaner', 'clerk', 'driver', 'nurse', 'maintenance', 'staff',
    'librarian', 'accountant', 'bursar',
}

ROLE_CHOICES = [
    ('student', 'Student'), ('parent', 'Parent'),
    ('subject_teacher', 'Subject Teacher'), ('class_teacher', 'Class Teacher'),
    ('librarian', 'Librarian'), ('accountant', 'Accountant'), ('bursar', 'Bursar'),
    ('security', 'Security'), ('cleaner', 'Cleaner'), ('clerk', 'Clerk'),
    ('driver', 'Driver'), ('nurse', 'Nurse'), ('maintenance', 'Maintenance Staff'),
    ('administrator', 'Administrator'), ('staff', 'Other / Non-teaching Staff'),
    ('super_admin', 'Super Admin'),
]


def backfill_staff_profiles(apps, schema_editor):
    Membership = apps.get_model('core', 'SchoolMembership')
    Teacher = apps.get_model('core', 'Teacher')
    for membership in Membership.objects.filter(
        is_active=True,
        user__is_active=True,
        school__is_active=True,
    ).select_related('user', 'school').iterator():
        roles = {membership.primary_role, *(membership.extra_roles or [])}
        if not roles.intersection(STAFF_ROLES):
            continue
        if Teacher.objects.filter(user_id=membership.user_id).exists():
            continue
        base = f'STF{membership.user_id:04d}'
        employee_id = base[:20]
        suffix = 1
        while Teacher.objects.filter(school_id=membership.school_id, employee_id=employee_id).exists():
            suffix += 1
            employee_id = f'{base[:16]}{suffix:04d}'[:20]
        Teacher.objects.create(
            school_id=membership.school_id,
            user_id=membership.user_id,
            employee_id=employee_id,
            status='active',
        )


def staff_card_type_forward(apps, schema_editor):
    apps.get_model('core', 'IDCard').objects.filter(card_type='teacher').update(card_type='staff')


def staff_card_type_reverse(apps, schema_editor):
    apps.get_model('core', 'IDCard').objects.filter(card_type='staff').update(card_type='teacher')


class Migration(migrations.Migration):
    dependencies = [('core', '0071_teacher_archival')]

    operations = [
        migrations.AlterField(
            model_name='user', name='role',
            field=models.CharField(choices=ROLE_CHOICES, default='student', max_length=20),
        ),
        migrations.AlterField(
            model_name='schoolmembership', name='primary_role',
            field=models.CharField(choices=ROLE_CHOICES, max_length=20),
        ),
        migrations.AddField(
            model_name='teacher', name='custom_job_title',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='teacher', name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'), ('former', 'Former Staff'), ('retired', 'Retired'),
                    ('resigned', 'Resigned'), ('fired', 'Fired / Terminated'),
                    ('terminated', 'Terminated'), ('suspended', 'Suspended'), ('inactive', 'Inactive'),
                ],
                default='active', max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='student', name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'), ('graduated', 'Graduated'),
                    ('relocated', 'Relocated'), ('transferred', 'Transferred'),
                    ('withdrawn', 'Withdrawn'), ('suspended', 'Suspended'),
                    ('inactive', 'Inactive'),
                ],
                default='active', max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='idcard', name='card_type',
            field=models.CharField(
                choices=[('student', 'Student'), ('teacher', 'Teacher'), ('staff', 'Staff')],
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_staff_profiles, migrations.RunPython.noop),
        migrations.RunPython(staff_card_type_forward, staff_card_type_reverse),
    ]
