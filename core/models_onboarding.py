import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .tenanting import TenantOwnedMixin


class OnboardingRecord(TenantOwnedMixin):
    PERSON_STUDENT = 'student'
    PERSON_TEACHER = 'teacher'
    PERSON_TYPE_CHOICES = [
        (PERSON_STUDENT, 'Student'),
        (PERSON_TEACHER, 'Teacher'),
    ]

    STATUS_BASIC = 'basic'
    STATUS_INVITED = 'invited'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_PENDING_REVIEW = 'pending_review'
    STATUS_CHANGES_REQUESTED = 'changes_requested'
    STATUS_READY = 'ready'
    STATUS_ACTIVE = 'active'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_BASIC, 'Basic profile created'),
        (STATUS_INVITED, 'Invitation sent'),
        (STATUS_IN_PROGRESS, 'Details in progress'),
        (STATUS_PENDING_REVIEW, 'Awaiting review'),
        (STATUS_CHANGES_REQUESTED, 'Changes requested'),
        (STATUS_READY, 'Ready for login'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    SOURCE_EXISTING = 'existing'
    SOURCE_MANUAL = 'manual'
    SOURCE_BULK = 'bulk'
    SOURCE_CHOICES = [
        (SOURCE_EXISTING, 'Existing record'),
        (SOURCE_MANUAL, 'Added individually'),
        (SOURCE_BULK, 'Spreadsheet import'),
    ]

    person_type = models.CharField(max_length=20, choices=PERSON_TYPE_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='onboarding_records',
    )
    student = models.ForeignKey(
        'core.Student',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='onboarding_records',
    )
    teacher = models.ForeignKey(
        'core.Teacher',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='onboarding_records',
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_BASIC)
    recipient_name = models.CharField(max_length=200, blank=True)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=30, blank=True)
    token_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    login_sent_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_onboarding_records',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_onboarding_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'student'],
                condition=Q(student__isnull=False),
                name='unique_school_student_onboarding',
            ),
            models.UniqueConstraint(
                fields=['school', 'teacher'],
                condition=Q(teacher__isnull=False),
                name='unique_school_teacher_onboarding',
            ),
        ]
        indexes = [
            models.Index(fields=['school', 'person_type', 'status']),
            models.Index(fields=['school', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.display_name} - {self.get_status_display()}'

    def clean(self):
        super().clean()
        if self.person_type == self.PERSON_STUDENT and not self.student_id:
            raise ValidationError({'student': 'A student record is required for student onboarding.'})
        if self.person_type == self.PERSON_TEACHER and not self.teacher_id:
            raise ValidationError({'teacher': 'A teacher record is required for teacher onboarding.'})
        if self.student_id and self.teacher_id:
            raise ValidationError('An onboarding record cannot belong to both a student and a teacher.')
        if self.student_id and self.user_id != self.student.user_id:
            raise ValidationError({'user': 'The selected user does not belong to this student.'})
        if self.teacher_id and self.user_id != self.teacher.user_id:
            raise ValidationError({'user': 'The selected user does not belong to this teacher.'})

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def profile(self):
        return self.student if self.person_type == self.PERSON_STUDENT else self.teacher

    @property
    def basic_complete(self):
        return bool(self.user_id and (self.student_id or self.teacher_id))

    @property
    def details_complete(self):
        if self.person_type == self.PERSON_STUDENT:
            return bool(
                self.student_id
                and hasattr(self.student, 'bio_data')
                and self.student.guardians.exists()
            )
        if not self.teacher_id or not hasattr(self.teacher, 'bio_data'):
            return False
        bio_data = self.teacher.bio_data
        return bool(
            self.teacher.signature
            and bio_data.qualifications.exists()
            and hasattr(bio_data, 'bank_account')
        )

    @property
    def login_complete(self):
        if self.login_sent_at:
            return True
        membership = self.user.school_memberships.filter(school=self.school).first()
        return bool(
            membership
            and membership.has_portal_access()
            and self.user.has_usable_password()
        )

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def can_open_invitation(self):
        return bool(
            self.token_digest
            and not self.is_expired
            and self.status in {
                self.STATUS_INVITED,
                self.STATUS_IN_PROGRESS,
                self.STATUS_CHANGES_REQUESTED,
            }
        )

    def issue_invitation(self, lifetime_days=7, status=None):
        raw_token = secrets.token_urlsafe(32)
        self.token_digest = self.digest_token(raw_token)
        self.expires_at = timezone.now() + timedelta(days=lifetime_days)
        self.invited_at = timezone.now()
        self.opened_at = None
        self.status = status or self.STATUS_INVITED
        self.save(update_fields=[
            'token_digest',
            'expires_at',
            'invited_at',
            'opened_at',
            'status',
            'updated_at',
        ])
        return raw_token

    def invalidate_invitation(self):
        self.token_digest = None
        self.expires_at = None
        self.save(update_fields=['token_digest', 'expires_at', 'updated_at'])

    def sync_progress(self):
        if self.status in {
            self.STATUS_INVITED,
            self.STATUS_IN_PROGRESS,
            self.STATUS_PENDING_REVIEW,
            self.STATUS_CHANGES_REQUESTED,
            self.STATUS_CANCELLED,
        }:
            return False

        if self.login_complete:
            next_status = self.STATUS_ACTIVE
        elif self.details_complete:
            next_status = self.STATUS_READY
        else:
            next_status = self.STATUS_BASIC

        if self.status == next_status:
            return False
        self.status = next_status
        self.save(update_fields=['status', 'updated_at'])
        return True

    @staticmethod
    def digest_token(raw_token):
        return hashlib.sha256((raw_token or '').encode('utf-8')).hexdigest()

    @classmethod
    def find_by_token(cls, raw_token):
        if not raw_token:
            return None
        return cls.all_objects.select_related(
            'school', 'user', 'student__school_class', 'teacher'
        ).filter(token_digest=cls.digest_token(raw_token)).first()
