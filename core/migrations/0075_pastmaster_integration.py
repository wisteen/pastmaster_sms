from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("core", "0074_attendance_movements")]

    operations = [
        migrations.CreateModel(
            name="PastMasterConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_url", models.URLField(default="https://pastmaster.top")),
                ("client_id", models.CharField(blank=True, max_length=64)),
                ("client_secret_encrypted", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("disconnected", "Disconnected"), ("active", "Active"), ("error", "Needs attention")], default="disconnected", max_length=20)),
                ("last_roster_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_report_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_event_id", models.PositiveBigIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="pastmaster_connection", to="core.schooltenant")),
            ],
        ),
        migrations.CreateModel(
            name="PastMasterLearnerSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_student_id", models.CharField(max_length=120)),
                ("report", models.JSONField(blank=True, default=dict)),
                ("synced_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pastmaster_snapshots", to="core.schooltenant")),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="pastmaster_snapshot", to="core.student")),
            ],
            options={
                "ordering": ("-synced_at",),
                "constraints": [models.UniqueConstraint(fields=("school", "external_student_id"), name="unique_school_pastmaster_external_student")],
            },
        ),
    ]
