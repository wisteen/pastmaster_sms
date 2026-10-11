from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_parent_role_guardian_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolTenant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=80, unique=True)),
                ('plan', models.CharField(choices=[('essential', 'Essential'), ('standard', 'Standard'), ('premium', 'Premium')], default='essential', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('contact_name', models.CharField(blank=True, max_length=150)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('contact_phone', models.CharField(blank=True, max_length=30)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='SchoolDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(help_text='Example: brightfuture.sms.pastmaster.top', max_length=255, unique=True)),
                ('is_primary', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='domains', to='core.schooltenant')),
            ],
            options={
                'ordering': ['school__name', '-is_primary', 'domain'],
            },
        ),
        migrations.CreateModel(
            name='TenantFeatureOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_enabled', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('feature', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tenant_overrides', to='core.featureflag')),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feature_overrides', to='core.schooltenant')),
            ],
            options={
                'ordering': ['school__name', 'feature__category', 'feature__display_name'],
                'unique_together': {('school', 'feature')},
            },
        ),
        migrations.CreateModel(
            name='SchoolMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('primary_role', models.CharField(choices=[('student', 'Student'), ('parent', 'Parent'), ('subject_teacher', 'Subject Teacher'), ('class_teacher', 'Class Teacher'), ('librarian', 'Librarian'), ('accountant', 'Accountant'), ('bursar', 'Bursar'), ('security', 'Security'), ('super_admin', 'Super Admin')], max_length=20)),
                ('extra_roles', models.JSONField(blank=True, default=list)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='core.schooltenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='school_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['school__name', 'user__username'],
                'unique_together': {('school', 'user')},
            },
        ),
        migrations.AddField(
            model_name='systemlicense',
            name='school',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='license', to='core.schooltenant'),
        ),
        migrations.AddField(
            model_name='schoolsettings',
            name='school',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='settings', to='core.schooltenant'),
        ),
    ]
