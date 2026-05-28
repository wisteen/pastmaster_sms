from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0042_schoolsettings_theme_colors'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenantDataExportRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('ready', 'Ready'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('requester_name', models.CharField(blank=True, max_length=150)),
                ('requester_email', models.EmailField(blank=True, max_length=254)),
                ('reason', models.TextField(blank=True)),
                ('include_media', models.BooleanField(default=True)),
                ('export_file', models.FileField(blank=True, upload_to='private/tenant_exports/')),
                ('file_size', models.PositiveBigIntegerField(default=0)),
                ('record_counts', models.JSONField(blank=True, default=dict)),
                ('notes', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('generated_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_tenant_exports', to=settings.AUTH_USER_MODEL)),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tenant_export_requests', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_export_requests', to='core.schooltenant')),
            ],
            options={
                'ordering': ['-requested_at'],
            },
        ),
    ]
