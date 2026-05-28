from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_add_subject_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='IDCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('card_number', models.CharField(max_length=50, unique=True)),
                ('barcode_data', models.CharField(max_length=100, unique=True)),
                ('card_type', models.CharField(choices=[('student', 'Student'), ('teacher', 'Teacher')], max_length=10)),
                ('issue_date', models.DateField(default=django.utils.timezone.now)),
                ('expiry_date', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='id_card', to='core.student')),
                ('teacher', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='id_card', to='core.teacher')),
            ],
        ),
        migrations.CreateModel(
            name='AttendanceSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.now)),
                ('session_type', models.CharField(choices=[('morning', 'Morning'), ('afternoon', 'Afternoon')], default='morning', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_closed', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.user')),
            ],
            options={
                'ordering': ['-date', '-session_type'],
                'unique_together': {('date', 'session_type')},
            },
        ),
        migrations.CreateModel(
            name='AttendanceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('present', 'Present'), ('absent', 'Absent'), ('late', 'Late'), ('excused', 'Excused')], default='present', max_length=10)),
                ('check_in_time', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True)),
                ('id_card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.idcard')),
                ('marked_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marked_attendance', to='core.user')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='core.attendancesession')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.student')),
                ('teacher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.teacher')),
            ],
            options={
                'ordering': ['-check_in_time'],
                'unique_together': {('session', 'id_card')},
            },
        ),
    ]
