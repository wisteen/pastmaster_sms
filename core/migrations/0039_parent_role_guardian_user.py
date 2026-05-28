from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_user_extra_roles_bursar'),
    ]

    operations = [
        migrations.AddField(
            model_name='guardian',
            name='user',
            field=models.ForeignKey(blank=True, help_text='Parent portal account for this guardian.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='guardian_profiles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('student', 'Student'), ('parent', 'Parent'), ('subject_teacher', 'Subject Teacher'), ('class_teacher', 'Class Teacher'), ('librarian', 'Librarian'), ('accountant', 'Accountant'), ('bursar', 'Bursar'), ('security', 'Security'), ('super_admin', 'Super Admin')], default='student', max_length=20),
        ),
    ]
