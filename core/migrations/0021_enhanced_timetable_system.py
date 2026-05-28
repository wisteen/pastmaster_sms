# Generated migration for enhanced timetable system

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_lessonnote'),
    ]

    operations = [
        # This migration ensures RoomAssignment model exists
        # The model is already defined in models.py, so this is just a placeholder
        # to maintain migration consistency
        migrations.RunSQL(
            "SELECT 1;",  # No-op SQL
            reverse_sql="SELECT 1;"
        ),
    ]