from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0059_tenant_delivery_and_access_controls')]

    operations = [
        migrations.AddField(
            model_name='student', name='status',
            field=models.CharField(
                choices=[('active', 'Active'), ('graduated', 'Graduated'), ('relocated', 'Relocated'), ('withdrawn', 'Withdrawn')],
                default='active', max_length=20,
            ),
        ),
        migrations.AddField(model_name='student', name='archived_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='student', name='archive_note', field=models.TextField(blank=True)),
        migrations.AddField(
            model_name='reportcardsettings', name='third_term_mode',
            field=models.CharField(
                choices=[('cumulative', 'Cumulative (all terms)'), ('term_only', 'Third term only')],
                default='cumulative', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='schoolsettings', name='promotion_min_average',
            field=models.DecimalField(decimal_places=2, default=50, max_digits=5),
        ),
        migrations.AddField(
            model_name='schoolsettings', name='promotion_max_failed_subjects',
            field=models.PositiveIntegerField(default=2),
        ),
        migrations.AddField(
            model_name='schoolsettings', name='promotion_min_attendance',
            field=models.DecimalField(decimal_places=2, default=75, max_digits=5),
        ),
        migrations.AlterField(
            model_name='schoolmessage', name='audience',
            field=models.CharField(
                choices=[('selected', 'Selected Users'), ('class', 'A Class'), ('everyone', 'Everyone'), ('admins', 'School Admins'), ('teachers', 'Teachers'), ('parents', 'Parents'), ('students', 'Students')],
                default='selected', max_length=20,
            ),
        ),
    ]
