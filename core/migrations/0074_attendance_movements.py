from datetime import timedelta

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_attendance_movements(apps, schema_editor):
    AttendanceMovement = apps.get_model('core', 'AttendanceMovement')
    AttendanceRecord = apps.get_model('core', 'AttendanceRecord')

    movements = []
    for record in AttendanceRecord.objects.all().iterator():
        movements.append(AttendanceMovement(
            record_id=record.id,
            action='in',
            event_time=record.check_in_time,
            recorded_by_id=record.marked_by_id,
            source='legacy',
        ))
        if (
            record.check_out_time
            and record.check_out_time - record.check_in_time >= timedelta(minutes=10)
        ):
            movements.append(AttendanceMovement(
                record_id=record.id,
                action='out',
                event_time=record.check_out_time,
                recorded_by_id=record.marked_by_id,
                source='legacy',
            ))
        elif record.check_out_time:
            AttendanceRecord.objects.filter(pk=record.pk).update(check_out_time=None)
    AttendanceMovement.objects.bulk_create(movements, batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [('core', '0073_assessment_submission_integrity')]

    operations = [
        migrations.CreateModel(
            name='AttendanceMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('in', 'Clock In'), ('out', 'Clock Out')], max_length=3)),
                ('event_time', models.DateTimeField(default=django.utils.timezone.now)),
                ('source', models.CharField(default='scanner', max_length=20)),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movements', to='core.attendancerecord')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_movements_recorded', to='core.user')),
            ],
            options={'ordering': ['event_time', 'id']},
        ),
        migrations.AddIndex(
            model_name='attendancemovement',
            index=models.Index(fields=['record', 'event_time'], name='core_attend_record__2bf84f_idx'),
        ),
        migrations.RunPython(backfill_attendance_movements, migrations.RunPython.noop),
    ]
