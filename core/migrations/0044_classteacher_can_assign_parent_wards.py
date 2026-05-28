from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0043_tenantdataexportrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='classteacher',
            name='can_assign_parent_wards',
            field=models.BooleanField(
                default=False,
                help_text='Allow this class teacher to link learners in this class to parent portal accounts.',
            ),
        ),
    ]
