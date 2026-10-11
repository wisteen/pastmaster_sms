from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .pastmaster_crypto import decrypt_secret, encrypt_secret


class PastMasterConnection(models.Model):
    class Status(models.TextChoices):
        DISCONNECTED = "disconnected", "Disconnected"
        ACTIVE = "active", "Active"
        ERROR = "error", "Needs attention"

    school = models.OneToOneField(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="pastmaster_connection",
    )
    base_url = models.URLField(default="https://pastmaster.top")
    client_id = models.CharField(max_length=64, blank=True)
    client_secret_encrypted = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DISCONNECTED)
    last_roster_sync_at = models.DateTimeField(null=True, blank=True)
    last_report_sync_at = models.DateTimeField(null=True, blank=True)
    last_event_id = models.PositiveBigIntegerField(default=0)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        parsed = urlparse(self.base_url)
        local = parsed.hostname in {"localhost", "127.0.0.1", "10.0.2.2"}
        if parsed.scheme != "https" and not (settings.DEBUG and parsed.scheme == "http" and local):
            raise ValidationError({"base_url": "Use an HTTPS PastMaster address. HTTP is allowed only for local development."})

    def set_client_secret(self, value):
        self.client_secret_encrypted = encrypt_secret(value)

    def get_client_secret(self):
        return decrypt_secret(self.client_secret_encrypted)

    @property
    def is_configured(self):
        return bool(self.client_id and self.client_secret_encrypted)

    def __str__(self):
        return f"PastMaster - {self.school}"


class PastMasterLearnerSnapshot(models.Model):
    school = models.ForeignKey(
        "core.SchoolTenant",
        on_delete=models.CASCADE,
        related_name="pastmaster_snapshots",
    )
    student = models.OneToOneField(
        "core.Student",
        on_delete=models.CASCADE,
        related_name="pastmaster_snapshot",
    )
    external_student_id = models.CharField(max_length=120)
    report = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-synced_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("school", "external_student_id"),
                name="unique_school_pastmaster_external_student",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.synced_at:%Y-%m-%d}"
