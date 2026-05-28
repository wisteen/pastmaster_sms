from django.db import models
from django.core.validators import RegexValidator
from .models import Student, Teacher, User

class StudentBioData(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    GENOTYPE_CHOICES = [
        ('AA', 'AA'), ('AS', 'AS'), ('AC', 'AC'),
        ('SS', 'SS'), ('SC', 'SC'), ('CC', 'CC'),
    ]
    
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='bio_data')
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=200)
    nationality = models.CharField(max_length=100, default='Nigerian')
    state_of_origin = models.CharField(max_length=100)
    lga = models.CharField(max_length=100, verbose_name='LGA')
    religion = models.CharField(max_length=50)
    home_address = models.TextField()
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(r'^\+?1?\d{9,15}$')])
    email = models.EmailField(blank=True)
    passport_photo = models.ImageField(upload_to='students/passports/', blank=True)
    
    # Previous School Information
    previous_school_name = models.CharField(max_length=200, blank=True)
    previous_school_address = models.TextField(blank=True)
    previous_class = models.CharField(max_length=50, blank=True)
    reason_for_leaving = models.TextField(blank=True)
    transfer_certificate = models.FileField(upload_to='students/certificates/', blank=True)
    
    # Health Records
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    genotype = models.CharField(max_length=2, choices=GENOTYPE_CHOICES, blank=True)
    allergies = models.TextField(blank=True, help_text='List any allergies')
    medical_conditions = models.TextField(blank=True, help_text='List any medical conditions')
    medications = models.TextField(blank=True, help_text='Current medications')
    doctor_name = models.CharField(max_length=200, blank=True)
    doctor_phone = models.CharField(max_length=15, blank=True)
    hospital_name = models.CharField(max_length=200, blank=True)
    hospital_address = models.TextField(blank=True)
    
    # Government ID
    birth_certificate_number = models.CharField(max_length=50, blank=True)
    nin = models.CharField(max_length=11, blank=True, verbose_name='NIN')
    
    # Experience/Background
    hobbies = models.TextField(blank=True)
    special_talents = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Student Bio Data'
        verbose_name_plural = 'Student Bio Data'
    
    def __str__(self):
        return f"Bio Data - {self.student.user.get_full_name()}"


class Guardian(models.Model):
    RELATIONSHIP_CHOICES = [
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Guardian'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('grandparent', 'Grandparent'),
        ('sibling', 'Sibling'),
        ('other', 'Other'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='guardian_profiles', help_text='Parent portal account for this guardian.')
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    title = models.CharField(max_length=10, choices=[('Mr', 'Mr'), ('Mrs', 'Mrs'), ('Miss', 'Miss'), ('Dr', 'Dr'), ('Prof', 'Prof')])
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(r'^\+?1?\d{9,15}$')])
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=100)
    employer = models.CharField(max_length=200, blank=True)
    office_address = models.TextField(blank=True)
    home_address = models.TextField()
    is_primary_contact = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)
    passport_photo = models.ImageField(upload_to='guardians/', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_primary_contact', 'relationship']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.relationship}) - {self.student.user.get_full_name()}"
    
    def get_full_name(self):
        return f"{self.title} {self.first_name} {self.last_name}"


class StaffBioData(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    
    GENOTYPE_CHOICES = [
        ('AA', 'AA'), ('AS', 'AS'), ('AC', 'AC'),
        ('SS', 'SS'), ('SC', 'SC'), ('CC', 'CC'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]
    
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE, related_name='bio_data')
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=200)
    nationality = models.CharField(max_length=100, default='Nigerian')
    state_of_origin = models.CharField(max_length=100)
    lga = models.CharField(max_length=100, verbose_name='LGA')
    religion = models.CharField(max_length=50)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES)
    home_address = models.TextField()
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(r'^\+?1?\d{9,15}$')])
    email = models.EmailField()
    passport_photo = models.ImageField(upload_to='staff/passports/', blank=True)
    
    # Health Records
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, blank=True)
    genotype = models.CharField(max_length=2, choices=GENOTYPE_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)
    
    # Government IDs
    nin = models.CharField(max_length=11, blank=True, verbose_name='NIN')
    bvn = models.CharField(max_length=11, blank=True, verbose_name='BVN')
    passport_number = models.CharField(max_length=20, blank=True)
    drivers_license = models.CharField(max_length=20, blank=True)
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200)
    emergency_contact_relationship = models.CharField(max_length=50)
    emergency_contact_phone = models.CharField(max_length=15)
    emergency_contact_address = models.TextField()
    
    # Employment Details
    date_of_employment = models.DateField()
    employment_type = models.CharField(max_length=20, choices=[('full_time', 'Full Time'), ('part_time', 'Part Time'), ('contract', 'Contract')])
    department = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    
    # Previous Experience
    previous_employer = models.CharField(max_length=200, blank=True)
    previous_position = models.CharField(max_length=100, blank=True)
    years_of_experience = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Staff Bio Data'
        verbose_name_plural = 'Staff Bio Data'
    
    def __str__(self):
        return f"Bio Data - {self.teacher.user.get_full_name()}"


class StaffQualification(models.Model):
    QUALIFICATION_TYPES = [
        ('ssce', 'SSCE/WAEC/NECO'),
        ('ond', 'OND'),
        ('hnd', 'HND'),
        ('bsc', 'B.Sc/B.A/B.Ed'),
        ('msc', 'M.Sc/M.A/M.Ed'),
        ('phd', 'Ph.D'),
        ('certificate', 'Certificate'),
        ('diploma', 'Diploma'),
        ('other', 'Other'),
    ]
    
    staff_bio_data = models.ForeignKey(StaffBioData, on_delete=models.CASCADE, related_name='qualifications')
    qualification_type = models.CharField(max_length=20, choices=QUALIFICATION_TYPES)
    institution = models.CharField(max_length=200)
    course_of_study = models.CharField(max_length=200)
    grade = models.CharField(max_length=50)
    year_obtained = models.IntegerField()
    certificate_file = models.FileField(upload_to='staff/certificates/', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-year_obtained']
    
    def __str__(self):
        return f"{self.get_qualification_type_display()} - {self.staff_bio_data.teacher.user.get_full_name()}"


class StaffGuarantor(models.Model):
    staff_bio_data = models.ForeignKey(StaffBioData, on_delete=models.CASCADE, related_name='guarantors')
    title = models.CharField(max_length=10, choices=[('Mr', 'Mr'), ('Mrs', 'Mrs'), ('Miss', 'Miss'), ('Dr', 'Dr'), ('Prof', 'Prof')])
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, validators=[RegexValidator(r'^\+?1?\d{9,15}$')])
    email = models.EmailField()
    occupation = models.CharField(max_length=100)
    employer = models.CharField(max_length=200)
    office_address = models.TextField()
    home_address = models.TextField()
    relationship = models.CharField(max_length=100)
    passport_photo = models.ImageField(upload_to='guarantors/', blank=True)
    id_card = models.FileField(upload_to='guarantors/ids/', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_full_name()} - Guarantor for {self.staff_bio_data.teacher.user.get_full_name()}"
    
    def get_full_name(self):
        return f"{self.title} {self.first_name} {self.last_name}"


class StaffBankAccount(models.Model):
    staff_bio_data = models.OneToOneField(StaffBioData, on_delete=models.CASCADE, related_name='bank_account')
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=10, validators=[RegexValidator(r'^\d{10}$')])
    account_name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=[('savings', 'Savings'), ('current', 'Current')])
    branch = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Staff Bank Account'
        verbose_name_plural = 'Staff Bank Accounts'
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number} ({self.staff_bio_data.teacher.user.get_full_name()})"


class PaymentSchedule(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='payment_schedules')
    month = models.DateField()
    staff_name = models.CharField(max_length=200)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-month', 'staff_name']
        unique_together = ['teacher', 'month']
    
    def __str__(self):
        return f"{self.staff_name} - {self.month.strftime('%B %Y')} - {self.amount}"
