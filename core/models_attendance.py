from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from .models import Student, Teacher, User
from .tenanting import TenantOwnedMixin
import uuid

class IDCard(models.Model):
    """ID Card model for students and staff"""
    CARD_TYPE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('staff', 'Staff'),
    ]
    
    card_number = models.CharField(max_length=50, unique=True)
    barcode_data = models.CharField(max_length=100, unique=True)
    card_type = models.CharField(max_length=10, choices=CARD_TYPE_CHOICES)
    student = models.OneToOneField(Student, on_delete=models.CASCADE, null=True, blank=True, related_name='id_card')
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE, null=True, blank=True, related_name='id_card')
    issue_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.student:
            return f"ID Card - {self.student.user.get_full_name()}"
        return f"ID Card - {self.teacher.user.get_full_name()}"
    
    def get_holder(self):
        return self.student if self.student else self.teacher
    
    def get_holder_name(self):
        holder = self.get_holder()
        return holder.user.get_full_name() if holder else "Unknown"
    
    def get_holder_id(self):
        if self.student:
            return self.student.student_id
        return self.teacher.employee_id if self.teacher else "N/A"
    
    def get_photo(self):
        if self.student and self.student.passport_photo:
            return self.student.passport_photo.url
        if self.teacher:
            try:
                if self.teacher.bio_data.passport_photo:
                    return self.teacher.bio_data.passport_photo.url
            except (AttributeError, ObjectDoesNotExist):
                pass
        return None

    def get_holder_role(self):
        if self.student:
            return 'Student'
        return self.teacher.get_staff_title() if self.teacher else 'Staff'

class AttendanceSession(TenantOwnedMixin):
    """Daily attendance session"""
    date = models.DateField(default=timezone.now)
    session_type = models.CharField(max_length=20, choices=[
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
    ], default='morning')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['school', 'date', 'session_type']
        ordering = ['-date', '-session_type']
    
    def __str__(self):
        return f"{self.date} - {self.session_type}"

class AttendanceRecord(models.Model):
    """Individual attendance record"""
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]
    
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    id_card = models.ForeignKey(IDCard, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendance')
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['session', 'id_card']
        ordering = ['-check_in_time']
    
    def __str__(self):
        holder = self.student if self.student else self.teacher
        return f"{holder.user.get_full_name()} - {self.session.date} - {self.status}"
    
    def has_outstanding_fees(self):
        """Check if student has outstanding fees"""
        if not self.student:
            return False
        
        from .models import StudentFee
        outstanding = StudentFee.objects.filter(
            student=self.student,
            status__in=['pending', 'partial', 'overdue']
        ).exists()
        return outstanding
    
    def get_fee_balance(self):
        """Get total outstanding balance"""
        if not self.student:
            return 0
        
        from .models import StudentFee
        from django.db.models import Sum
        
        fees = StudentFee.objects.filter(
            student=self.student,
            status__in=['pending', 'partial', 'overdue']
        )
        
        total_balance = sum(fee.balance_amount for fee in fees)
        return total_balance


class AttendanceMovement(models.Model):
    """Every entrance/exit scan belonging to a gate attendance record."""

    ACTION_CHOICES = [
        ('in', 'Clock In'),
        ('out', 'Clock Out'),
    ]

    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name='movements',
    )
    action = models.CharField(max_length=3, choices=ACTION_CHOICES)
    event_time = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_movements_recorded',
    )
    source = models.CharField(max_length=20, default='scanner')

    class Meta:
        ordering = ['event_time', 'id']
        indexes = [models.Index(fields=['record', 'event_time'])]

    def __str__(self):
        return f"{self.record} - {self.get_action_display()} at {self.event_time}"


class Visitor(TenantOwnedMixin):
    """Visitor log for school security"""
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    purpose = models.TextField()
    person_to_see = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True)
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    logged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-check_in_time']
    
    def __str__(self):
        return f"{self.name} - {self.check_in_time.date()}"
    
    def duration(self):
        if self.check_out_time:
            delta = self.check_out_time - self.check_in_time
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "Still on premises"
