from django.db import models
from .models import Student, User


class ParentDevice(models.Model):
    """Store parent device tokens for push notifications"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parent_devices')
    parent_name = models.CharField(max_length=200, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    device_token = models.CharField(max_length=500, unique=True)
    device_type = models.CharField(max_length=20, choices=[
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web')
    ])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'parent_devices'
        verbose_name = 'Parent Device'
        verbose_name_plural = 'Parent Devices'
    
    def __str__(self):
        return f"{self.parent_name or 'Parent'} - {self.student.user.get_full_name()}"
