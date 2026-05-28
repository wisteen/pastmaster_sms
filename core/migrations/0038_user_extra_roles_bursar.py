from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_parentdevice'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='extra_roles',
            field=models.JSONField(blank=True, default=list, help_text='Additional roles this user can access.'),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('student', 'Student'), ('subject_teacher', 'Subject Teacher'), ('class_teacher', 'Class Teacher'), ('librarian', 'Librarian'), ('accountant', 'Accountant'), ('bursar', 'Bursar'), ('security', 'Security'), ('super_admin', 'Super Admin')], default='student', max_length=20),
        ),
    ]
