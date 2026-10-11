from django.db import models
from django.utils import timezone
from .models import Student, SchoolClass, Term, User

class DailyAttendanceSession(models.Model):
    """Daily attendance session for class teachers"""
    date = models.DateField(default=timezone.now)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['date', 'school_class', 'term']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.school_class} - {self.date}"
    
    def get_total_students(self):
        from .staffing import active_students
        return active_students(self.school_class.school).filter(school_class=self.school_class).count()
    
    def get_marked_count(self):
        return self.records.count()
    
    def is_complete(self):
        return self.get_marked_count() == self.get_total_students()

class DailyAttendanceRecord(models.Model):
    """Individual student daily attendance record"""
    MORNING_STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    ]
    
    AFTERNOON_STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('left_early', 'Left Early'),
    ]
    
    ABSENCE_REASONS = [
        ('sick', 'Sick/Medical'),
        ('family', 'Family Emergency'),
        ('permission', 'Permission Granted'),
        ('unauthorized', 'Unauthorized'),
        ('other', 'Other'),
    ]
    
    session = models.ForeignKey(DailyAttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    
    # Morning attendance
    morning_status = models.CharField(max_length=10, choices=MORNING_STATUS, default='present')
    morning_time = models.TimeField(null=True, blank=True)
    
    # Afternoon attendance
    afternoon_status = models.CharField(max_length=15, choices=AFTERNOON_STATUS, default='present')
    afternoon_time = models.TimeField(null=True, blank=True)
    
    # Absence details
    is_absent = models.BooleanField(default=False)
    absence_reason = models.CharField(max_length=20, choices=ABSENCE_REASONS, blank=True)
    absence_details = models.TextField(blank=True, help_text="Additional details about absence")
    
    # Metadata
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['session', 'student']
        ordering = ['student__user__first_name']
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.session.date}"
    
    def save(self, *args, **kwargs):
        # Auto-set is_absent based on morning/afternoon status
        self.is_absent = (self.morning_status == 'absent' and self.afternoon_status == 'absent')
        super().save(*args, **kwargs)
    
    def get_day_status(self):
        """Get overall status for the day"""
        if self.morning_status == 'absent' and self.afternoon_status == 'absent':
            return 'Absent (Full Day)'
        elif self.morning_status == 'absent':
            return 'Absent (Morning)'
        elif self.afternoon_status == 'absent':
            return 'Absent (Afternoon)'
        elif self.morning_status == 'late':
            return 'Late'
        elif self.afternoon_status == 'left_early':
            return 'Left Early'
        return 'Present'

class TermAttendanceSummary(models.Model):
    """Summary of student attendance for a term"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    
    # Counts
    total_school_days = models.IntegerField(default=0)
    days_present = models.IntegerField(default=0)
    days_absent = models.IntegerField(default=0)
    days_late = models.IntegerField(default=0)
    
    # Morning/Afternoon breakdown
    morning_present = models.IntegerField(default=0)
    morning_absent = models.IntegerField(default=0)
    afternoon_present = models.IntegerField(default=0)
    afternoon_absent = models.IntegerField(default=0)
    
    # Absence reasons breakdown
    sick_days = models.IntegerField(default=0)
    family_emergency_days = models.IntegerField(default=0)
    permission_days = models.IntegerField(default=0)
    unauthorized_days = models.IntegerField(default=0)
    other_absence_days = models.IntegerField(default=0)
    
    # Percentages
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'term']
        ordering = ['-term', 'student__user__first_name']
    
    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.term} - {self.attendance_percentage}%"
    
    def calculate_summary(self):
        """Calculate attendance summary from daily records"""
        records = DailyAttendanceRecord.objects.filter(
            student=self.student,
            session__term=self.term
        )
        
        self.total_school_days = records.count()
        self.days_present = 0
        self.days_absent = 0
        self.days_late = 0
        
        self.morning_present = 0
        self.morning_absent = 0
        self.afternoon_present = 0
        self.afternoon_absent = 0
        
        self.sick_days = 0
        self.family_emergency_days = 0
        self.permission_days = 0
        self.unauthorized_days = 0
        self.other_absence_days = 0
        
        for record in records:
            # Morning attendance
            if record.morning_status == 'present':
                self.morning_present += 1
            elif record.morning_status == 'absent':
                self.morning_absent += 1
            elif record.morning_status == 'late':
                self.days_late += 1
                self.morning_present += 1  # Count late as present
            
            # Afternoon attendance
            if record.afternoon_status == 'present':
                self.afternoon_present += 1
            elif record.afternoon_status == 'absent':
                self.afternoon_absent += 1
            elif record.afternoon_status == 'left_early':
                self.afternoon_present += 1  # Count left early as present
            
            # Full day status
            if record.morning_status == 'present' and record.afternoon_status == 'present':
                self.days_present += 1
            elif record.morning_status == 'absent' and record.afternoon_status == 'absent':
                self.days_absent += 1
            else:
                self.days_present += 0.5  # Half day present
            
            # Absence reasons
            if record.absence_reason == 'sick':
                self.sick_days += 1
            elif record.absence_reason == 'family':
                self.family_emergency_days += 1
            elif record.absence_reason == 'permission':
                self.permission_days += 1
            elif record.absence_reason == 'unauthorized':
                self.unauthorized_days += 1
            elif record.absence_reason == 'other':
                self.other_absence_days += 1
        
        # Calculate percentage
        if self.total_school_days > 0:
            self.attendance_percentage = (self.days_present / self.total_school_days) * 100
        else:
            self.attendance_percentage = 0
        
        self.save()
    
    def get_status_color(self):
        """Get color code based on attendance percentage"""
        if self.attendance_percentage >= 95:
            return 'green'
        elif self.attendance_percentage >= 85:
            return 'blue'
        elif self.attendance_percentage >= 75:
            return 'yellow'
        else:
            return 'red'
    
    def get_status_label(self):
        """Get status label based on attendance percentage"""
        if self.attendance_percentage >= 95:
            return 'Excellent'
        elif self.attendance_percentage >= 85:
            return 'Good'
        elif self.attendance_percentage >= 75:
            return 'Fair'
        else:
            return 'Poor'
