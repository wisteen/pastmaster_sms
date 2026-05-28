from django.db import models
from django.contrib.auth import get_user_model
from .tenanting import TenantOwnedMixin

User = get_user_model()

class GeneratedReport(TenantOwnedMixin):
    report_type = models.CharField(max_length=50)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)
    parameters = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['-generated_at']
        
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.generated_at}"
    
    def get_report_type_display(self):
        types = {
            'monthly_summary': 'Monthly Financial Summary',
            'fee_collection': 'Fee Collection Report',
            'scholarship_distribution': 'Scholarship Distribution',
            'payroll': 'Payroll Report',
            'year_over_year': 'Year-over-Year Comparison'
        }
        return types.get(self.report_type, self.report_type)
