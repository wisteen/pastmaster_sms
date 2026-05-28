from django.db import models
from django.db import connection
from django.db.utils import ProgrammingError, OperationalError
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from ckeditor.fields import RichTextField
import json
import secrets
from decimal import Decimal
from .tenanting import TenantOwnedMixin, install_tenant_manager

class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('parent', 'Parent'),
        ('subject_teacher', 'Subject Teacher'),
        ('class_teacher', 'Class Teacher'),
        ('librarian', 'Librarian'),
        ('accountant', 'Accountant'),
        ('bursar', 'Bursar'),
        ('security', 'Security'),
        ('super_admin', 'Super Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    extra_roles = models.JSONField(default=list, blank=True, help_text='Additional roles this user can access.')
    phone = models.CharField(max_length=15, blank=True)

    ROLE_ALIASES = {
        'accountant': {'accountant', 'bursar'},
        'bursar': {'accountant', 'bursar'},
    }

    def get_all_roles(self):
        try:
            from .tenant_context import get_current_school
            school = get_current_school()
            if school:
                if self.is_superuser:
                    roles = ['super_admin']
                    roles.extend(self.extra_roles or [])
                    return list(dict.fromkeys(roles))
                membership = self.school_memberships.filter(school=school, is_active=True).first()
                if membership:
                    return membership.get_all_roles()
                return []
        except Exception:
            pass

        roles = [getattr(self, 'primary_role', self.role)]
        roles.extend(self.extra_roles or [])
        return list(dict.fromkeys(roles))

    def has_role(self, role):
        if role == 'super_admin' and self.is_superuser:
            return True
        allowed = self.ROLE_ALIASES.get(role, {role})
        user_roles = set(self.get_all_roles())
        return bool(user_roles.intersection(allowed))

    def has_any_role(self, roles):
        return any(self.has_role(role) for role in roles)

class SchoolClass(TenantOwnedMixin):
    name = models.CharField(max_length=50)
    stream = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['school', 'name', 'stream']

    def __str__(self):
        return f"{self.name} {self.stream}".strip()

class Subject(TenantOwnedMixin):
    SUBJECT_TYPES = [
        ('academic', 'Academic Subject'),
        ('break', 'Break Period'),
        ('assembly', 'Assembly'),
        ('closing', 'Closing Period'),
        ('special', 'Special Activity'),
    ]
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPES, default='academic')
    pass_mark = models.IntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('school', 'name'), ('school', 'code')]

    def __str__(self):
        return self.name

class GradingSystem(TenantOwnedMixin):
    min_score = models.IntegerField()
    max_score = models.IntegerField()
    grade = models.CharField(max_length=2)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2)
    remark = models.CharField(max_length=50)

    class Meta:
        ordering = ['-min_score']

    def __str__(self):
        return f"{self.grade} ({self.min_score}-{self.max_score})"

class QuestionGroup(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    instruction = RichTextField(help_text="Common passage/instruction for grouped questions")
    created_by = models.ForeignKey('Teacher', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.subject.code} - {self.instruction[:50]}"

class QuestionBank(models.Model):
    QUESTION_TYPES = [
        ('objective', 'Objective (SCQ)'),
        ('multichoice', 'Multi-Choice (MCQ)'),
        ('theory', 'Theory'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, null=True, blank=True)
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='objective')
    topic = models.CharField(max_length=200, blank=True)
    group = models.ForeignKey(QuestionGroup, on_delete=models.CASCADE, null=True, blank=True, related_name='questions')
    question_text = RichTextField()
    option_a = RichTextField(blank=True)
    option_b = RichTextField(blank=True)
    option_c = RichTextField(blank=True)
    option_d = RichTextField(blank=True)
    correct_answer = models.CharField(max_length=10, blank=True)
    difficulty = models.CharField(max_length=10, choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium')
    created_by = models.ForeignKey('Teacher', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject.code} - {self.question_text[:50]}"

class ResultComponent(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    component_name = models.CharField(max_length=50)
    weight = models.IntegerField()
    max_score = models.IntegerField(default=100)
    linked_quiz = models.ForeignKey('Quiz', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ['school_class', 'subject', 'component_name']

    def __str__(self):
        return f"{self.school_class} - {self.subject} - {self.component_name} ({self.weight}%)"

class Student(TenantOwnedMixin):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, blank=True)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    address = models.TextField(blank=True)
    passport_photo = models.ImageField(upload_to='students/', blank=True)
    is_promoted = models.BooleanField(default=False)
    promoted_to = models.ForeignKey(SchoolClass, on_delete=models.SET_NULL, null=True, blank=True, related_name='promoted_students')

    class Meta:
        unique_together = ['school', 'student_id']

    def save(self, *args, **kwargs):
        if not self.school_id:
            school = self.get_tenant_school()
            if school:
                self.school = school
        if not self.student_id:
            settings = SchoolSettings.get_for_school(self.school)
            if settings:
                self.student_id = settings.generate_student_id()
            else:
                # Fallback if no settings
                last = Student.objects.order_by('-id').first()
                self.student_id = f"STU{str((last.id if last else 0) + 1).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_id}"

class Teacher(TenantOwnedMixin):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, blank=True)
    subjects = models.ManyToManyField(Subject, blank=True)
    classes = models.ManyToManyField(SchoolClass, blank=True)
    signature = models.ImageField(upload_to='signatures/teachers/', blank=True)
    ai_access_expires = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['school', 'employee_id']

    def save(self, *args, **kwargs):
        if not self.school_id:
            school = self.get_tenant_school()
            if school:
                self.school = school
        if not self.employee_id:
            settings = SchoolSettings.get_for_school(self.school)
            if settings:
                self.employee_id = settings.generate_teacher_id()
            else:
                # Fallback if no settings
                last = Teacher.objects.order_by('-id').first()
                self.employee_id = f"TCH{str((last.id if last else 0) + 1).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"
    
    def has_ai_access(self):
        if not self.ai_access_expires:
            return False
        return timezone.now() < self.ai_access_expires

class AISubscription(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=30000.00)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, default='pending')
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.reference}"

class ClassTeacher(models.Model):
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE)
    school_class = models.OneToOneField(SchoolClass, on_delete=models.CASCADE)
    can_assign_parent_wards = models.BooleanField(
        default=False,
        help_text='Allow this class teacher to link learners in this class to parent portal accounts.',
    )

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.school_class.name}"

class HeadTeacher(models.Model):
    teacher = models.OneToOneField(Teacher, on_delete=models.CASCADE)
    title = models.CharField(max_length=100, default='Head Teacher')
    classes = models.ManyToManyField(SchoolClass, related_name='head_teacher_classes')
    signature = models.ImageField(upload_to='signatures/head_teachers/', blank=True)
    
    def __str__(self):
        return f"{self.teacher.user.get_full_name()} - {self.title}"

class Term(TenantOwnedMixin):
    name = models.CharField(max_length=50)
    session = models.CharField(max_length=9, default='2024-2025')  # e.g., "2024-2025"
    start_date = models.DateField()
    end_date = models.DateField()
    vacation_date = models.DateField(null=True, blank=True)
    resumption_date = models.DateField(null=True, blank=True)
    school_opened_days = models.IntegerField(default=0)
    is_active = models.BooleanField(default=False)
    result_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ['school', 'name', 'session']

    def __str__(self):
        return self.name
    
    def get_next_term_resumption(self):
        """Get the resumption date for the next term"""
        next_terms = Term.objects.filter(
            session=self.session,
            start_date__gt=self.end_date
        ).order_by('start_date')
        
        if next_terms.exists():
            return next_terms.first().resumption_date
        
        # If no next term in same session, look for first term of next session
        # Handle both formats: "2023/2024" and "2024-2025"
        if '/' in self.session:
            current_year = int(self.session.split('/')[0])
            next_session = f"{current_year + 1}/{current_year + 2}"
        else:
            current_year = int(self.session.split('-')[0])
            next_session = f"{current_year + 1}-{current_year + 2}"
        
        next_session_terms = Term.objects.filter(
            session=next_session
        ).order_by('start_date')
        
        if next_session_terms.exists():
            return next_session_terms.first().resumption_date
        
        return None

class ReportCardSettings(TenantOwnedMixin):
    """Settings to control what appears on report cards"""
    show_position = models.BooleanField(default=True)
    show_subject_position = models.BooleanField(default=True)
    show_class_average = models.BooleanField(default=True)
    show_highest_in_class = models.BooleanField(default=True)
    show_attendance = models.BooleanField(default=True)
    show_psychomotor = models.BooleanField(default=True)
    show_effective_domain = models.BooleanField(default=True)
    show_next_resumption = models.BooleanField(default=True)
    show_total_obtainable = models.BooleanField(default=True)
    show_school_opened_days = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Report Card Settings'
        verbose_name_plural = 'Report Card Settings'
    
    def __str__(self):
        return f"Report Card Settings - {'Active' if self.is_active else 'Inactive'}"

class ResultToken(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    token = models.CharField(max_length=20, unique=True)
    max_uses = models.IntegerField(default=3)
    uses_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'term']
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(12)[:12].upper()
        super().save(*args, **kwargs)
    
    def can_use(self):
        return self.uses_count < self.max_uses
    
    def use_token(self):
        if self.can_use():
            self.uses_count += 1
            self.save()
            return True
        return False

class Attendance(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    days_present = models.IntegerField(default=0)
    days_absent = models.IntegerField(default=0)
    total_days = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['student', 'term']
    
    def percentage(self):
        if self.total_days > 0:
            return (self.days_present / self.total_days) * 100
        return 0

class Comment(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    teacher_comment = models.TextField(blank=True)
    proprietor_comment = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['student', 'term']


class Psychomotor(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    sports_games = models.CharField(max_length=5, blank=True)
    handwriting = models.CharField(max_length=5, blank=True)
    drawing_painting = models.CharField(max_length=5, blank=True)
    crafts = models.CharField(max_length=5, blank=True)
    music_drama = models.CharField(max_length=5, blank=True)

    class Meta:
        unique_together = ['student', 'term']
        verbose_name = 'Psychomotor'
        verbose_name_plural = 'Psychomotor'

    def __str__(self):
        return f"Psychomotor - {self.student} - {self.term}"


class EffectiveDomain(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    punctuality = models.CharField(max_length=5, blank=True)
    neatness = models.CharField(max_length=5, blank=True)
    attentiveness = models.CharField(max_length=5, blank=True)
    politeness = models.CharField(max_length=5, blank=True)
    relationship_with_others = models.CharField(max_length=5, blank=True)

    class Meta:
        unique_together = ['student', 'term']
        verbose_name = 'Effective Domain'
        verbose_name_plural = 'Effective Domains'

    def __str__(self):
        return f"Effective Domain - {self.student} - {self.term}"


class SchoolSettings(models.Model):
    class SchoolSettingsManager(models.Manager):
        def get_queryset(self):
            queryset = super().get_queryset()
            try:
                table_name = queryset.model._meta.db_table
                with connection.cursor() as cursor:
                    existing_columns = connection.introspection.get_table_description(cursor, table_name)
                column_names = {column.name for column in existing_columns}
            except (ProgrammingError, OperationalError, Exception):
                return queryset

            safe_fields = []
            for field in queryset.model._meta.concrete_fields:
                if field.column in column_names:
                    safe_fields.append(field.name)

            return queryset.only(*safe_fields) if safe_fields else queryset

    objects = SchoolSettingsManager()
    school = models.OneToOneField('SchoolTenant', on_delete=models.CASCADE, null=True, blank=True, related_name='settings')
    school_name = models.CharField(max_length=200)
    school_address = models.TextField()
    school_logo = models.ImageField(upload_to='school/', blank=True)
    school_seal = models.ImageField(upload_to='school/', blank=True)
    principal_signature = models.ImageField(upload_to='school/', blank=True)
    primary_color = models.CharField(max_length=7, default='#2563eb', help_text='Primary brand color in hex format.')
    secondary_color = models.CharField(max_length=7, default='#1d4ed8', help_text='Secondary brand color in hex format.')
    accent_color = models.CharField(max_length=7, default='#f97316', help_text='Accent brand color in hex format.')
    principal_name = models.CharField(max_length=100)
    proprietor_name = models.CharField(max_length=100, blank=True)
    school_motto = models.CharField(max_length=200, blank=True)
    student_id_prefix = models.CharField(max_length=10, default='STU', help_text='Prefix for student IDs')
    student_id_digits = models.IntegerField(default=4, help_text='Number of digits in student ID')
    teacher_id_prefix = models.CharField(max_length=10, default='TCH', help_text='Prefix for teacher IDs')
    teacher_id_digits = models.IntegerField(default=4, help_text='Number of digits in teacher ID')
    
    class Meta:
        verbose_name_plural = 'School Settings'
    
    def __str__(self):
        return self.school_name

    @classmethod
    def get_for_school(cls, school=None):
        queryset = cls.all_objects.all() if hasattr(cls, 'all_objects') else cls.objects.all()
        if school:
            tenant_settings = queryset.filter(school=school).first()
            if tenant_settings:
                cls._attach_theme_defaults(tenant_settings)
                return tenant_settings
        settings = queryset.filter(school__isnull=True).first() or queryset.first()
        if settings:
            cls._attach_theme_defaults(settings)
        return settings

    @classmethod
    def _attach_theme_defaults(cls, settings):
        if not settings:
            return settings
        if 'primary_color' not in settings.__dict__:
            settings.primary_color = '#2563eb'
        if 'secondary_color' not in settings.__dict__:
            settings.secondary_color = '#1d4ed8'
        if 'accent_color' not in settings.__dict__:
            settings.accent_color = '#f97316'
        return settings
    
    def generate_student_id(self):
        """Generate next student ID based on settings"""
        students = Student.all_objects.filter(student_id__startswith=self.student_id_prefix)
        if self.school_id:
            students = students.filter(school=self.school)
        last_student = students.order_by('-student_id').first()
        if last_student:
            try:
                last_num = int(last_student.student_id.replace(self.student_id_prefix, ''))
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1
        return f"{self.student_id_prefix}{str(next_num).zfill(self.student_id_digits)}"
    
    def generate_teacher_id(self):
        """Generate next teacher ID based on settings"""
        teachers = Teacher.all_objects.filter(employee_id__startswith=self.teacher_id_prefix)
        if self.school_id:
            teachers = teachers.filter(school=self.school)
        last_teacher = teachers.order_by('-employee_id').first()
        if last_teacher:
            try:
                last_num = int(last_teacher.employee_id.replace(self.teacher_id_prefix, ''))
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1
        return f"{self.teacher_id_prefix}{str(next_num).zfill(self.teacher_id_digits)}"

class ComponentResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    component = models.ForeignKey(ResultComponent, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'component', 'term']

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    total_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grade = models.CharField(max_length=2, blank=True)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    remark = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'subject', 'term']

    def calculate_total(self):
        components = ComponentResult.objects.filter(
            student=self.student,
            component__subject=self.subject,
            component__school_class=self.student.school_class,
            term=self.term
        )
        
        total = 0
        for comp_result in components:
            weighted_score = (comp_result.score / comp_result.component.max_score) * comp_result.component.weight
            total += weighted_score
        
        self.total_score = total
        
        grading = GradingSystem.objects.filter(
            min_score__lte=total,
            max_score__gte=total
        ).first()
        
        if grading:
            self.grade = grading.grade
            self.grade_point = grading.grade_point
            self.remark = grading.remark
        
        self.save()

class Quiz(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('ended', 'Ended'),
    ]
    
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    instructions = models.TextField(blank=True)
    shuffle_questions = models.BooleanField(default=True)
    shuffle_options = models.BooleanField(default=True)
    full_screen_mode = models.BooleanField(default=True)
    detect_tab_switching = models.BooleanField(default=True)
    max_tab_switches = models.IntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.school_class.name}"

    def is_live(self):
        now = timezone.now()
        return self.status == 'live' or (self.status == 'scheduled' and self.start_time <= now <= self.end_time)

class QuestionGroupInstance(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='question_groups')
    instruction = RichTextField()
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']

class Question(models.Model):
    QUESTION_TYPES = [
        ('objective', 'Objective'),
        ('multichoice', 'Multi-Choice'),
        ('theory', 'Theory'),
    ]
    
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    group_instance = models.ForeignKey(QuestionGroupInstance, on_delete=models.CASCADE, null=True, blank=True, related_name='questions')
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES, default='objective')
    question_text = RichTextField()
    option_a = RichTextField(blank=True)
    option_b = RichTextField(blank=True)
    option_c = RichTextField(blank=True)
    option_d = RichTextField(blank=True)
    correct_answer = models.CharField(max_length=10, blank=True)  # Can store 'A,B,C' for multichoice
    max_marks = models.IntegerField(default=1)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.title} - Q{self.id}"

class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    auto_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    manual_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_submitted = models.BooleanField(default=False)
    is_graded = models.BooleanField(default=False)
    integrity_log = models.TextField(default='[]')
    tab_switches = models.IntegerField(default=0)

    class Meta:
        unique_together = ['quiz', 'student']

    def add_integrity_event(self, event_type, details=''):
        log = json.loads(self.integrity_log)
        log.append({
            'timestamp': timezone.now().isoformat(),
            'event': event_type,
            'details': details
        })
        self.integrity_log = json.dumps(log)
        
        if event_type == 'tab_switch':
            self.tab_switches += 1
        
        self.save()

class QuizAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=10, blank=True)  # Can store 'A,B,C' for multichoice
    theory_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    manual_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    teacher_feedback = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.question.question_type in ['objective', 'multichoice'] and self.selected_answer:
            if self.question.question_type == 'multichoice':
                # For multichoice, check if selected answers match correct answers
                selected = set(self.selected_answer.split(','))
                correct = set(self.question.correct_answer.split(','))
                self.is_correct = selected == correct
            else:
                self.is_correct = self.selected_answer == self.question.correct_answer
        super().save(*args, **kwargs)


# Academic Management Models

class Curriculum(TenantOwnedMixin):
    title = models.CharField(max_length=200)
    description = models.TextField()
    academic_year = models.CharField(max_length=9)  # e.g., "2024-2025"
    subjects = models.ManyToManyField(Subject)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['school', 'title', 'academic_year']

    def __str__(self):
        return f"{self.title} ({self.academic_year})"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Original validation - only check if instance has been saved
        if self.pk and self.is_published and not self.learning_objectives.exists():
            raise ValidationError("Curriculum must have at least one learning objective before publishing.")
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_curriculum_relationships(self)
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete curriculum: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class LearningObjective(models.Model):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name='learning_objectives')
    title = models.CharField(max_length=300)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    grade_level = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']
        unique_together = ['curriculum', 'title']

    def __str__(self):
        return f"{self.curriculum.title} - {self.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_learning_objective_relationships(self)
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete learning objective: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class SyllabusContent(models.Model):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name='syllabus_contents')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    content = RichTextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['curriculum', 'subject', 'order']

    def __str__(self):
        return f"{self.curriculum.title} - {self.subject.name} Syllabus"

class LessonPlan(models.Model):
    title = models.CharField(max_length=200)
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    learning_objectives = models.ManyToManyField(LearningObjective)
    content = RichTextField()
    resources = models.TextField(blank=True)
    estimated_duration = models.DurationField()
    is_completed = models.BooleanField(default=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.school_class.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_lesson_plan_relationships(self)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.is_completed and not self.completion_date:
            self.completion_date = timezone.now()
        elif not self.is_completed:
            self.completion_date = None
        super().save(*args, **kwargs)
        
        # Update coverage tracking
        if self.is_completed:
            self.update_coverage_tracking()

    def update_coverage_tracking(self):
        """Update curriculum coverage when lesson is completed"""
        for objective in self.learning_objectives.all():
            coverage, created = CurriculumCoverage.objects.get_or_create(
                curriculum=self.curriculum,
                school_class=self.school_class,
                learning_objective=objective,
                defaults={'total_planned_lessons': 1}
            )
            
            # Count total lessons for this objective
            total_lessons = LessonPlan.objects.filter(
                curriculum=self.curriculum,
                school_class=self.school_class,
                learning_objectives=objective
            ).count()
            
            # Count completed lessons
            completed_lessons = LessonPlan.objects.filter(
                curriculum=self.curriculum,
                school_class=self.school_class,
                learning_objectives=objective,
                is_completed=True
            ).count()
            
            coverage.total_planned_lessons = max(total_lessons, 1)  # Avoid division by zero
            coverage.completed_lessons = completed_lessons
            coverage.completion_percentage = (completed_lessons / coverage.total_planned_lessons) * 100
            coverage.save()

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete lesson plan: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class CurriculumCoverage(models.Model):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    learning_objective = models.ForeignKey(LearningObjective, on_delete=models.CASCADE)
    completed_lessons = models.PositiveIntegerField(default=0)
    total_planned_lessons = models.PositiveIntegerField(default=1)
    completion_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['curriculum', 'school_class', 'learning_objective']

    def __str__(self):
        return f"{self.curriculum.title} - {self.school_class.name} - {self.learning_objective.title} ({self.completion_percentage}%)"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_curriculum_coverage_relationships(self)
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete coverage record: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class LessonNote(models.Model):
    lesson_plan = models.ForeignKey(LessonPlan, on_delete=models.CASCADE, related_name='lesson_notes')
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    date_taught = models.DateField()
    content_covered = RichTextField()
    teaching_methods = models.TextField(blank=True)
    student_engagement = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium')
    challenges_faced = models.TextField(blank=True)
    homework_assigned = models.TextField(blank=True)
    next_lesson_plan = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_taught']

    def __str__(self):
        return f"{self.lesson_plan.title} - {self.date_taught}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if hasattr(self, 'lesson_plan') and hasattr(self, 'curriculum') and self.lesson_plan and self.curriculum:
            if self.lesson_plan.curriculum != self.curriculum:
                raise ValidationError("Lesson note curriculum must match lesson plan curriculum.")
        if hasattr(self, 'lesson_plan') and hasattr(self, 'teacher') and self.lesson_plan and self.teacher:
            if self.lesson_plan.teacher != self.teacher:
                raise ValidationError("Lesson note teacher must match lesson plan teacher.")

class AcademicEvent(TenantOwnedMixin):
    EVENT_TYPES = [
        ('holiday', 'Holiday'),
        ('exam', 'Exam'),
        ('meeting', 'Meeting'),
        ('activity', 'Activity'),
        ('deadline', 'Deadline'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(max_length=50, blank=True)  # daily, weekly, monthly, yearly
    academic_year = models.CharField(max_length=9)
    terms = models.ManyToManyField(Term, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.title} ({self.start_date.strftime('%Y-%m-%d')})"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date.")
        
        # Validate term alignment for academic events
        if self.pk and self.terms.exists():
            for term in self.terms.all():
                if self.start_date.date() < term.start_date or self.end_date.date() > term.end_date:
                    raise ValidationError(f"Event dates must fall within the selected term: {term.name} ({term.start_date} to {term.end_date})")
        
        # Validate recurring pattern
        if self.is_recurring and not self.recurrence_pattern:
            raise ValidationError("Recurring events must have a recurrence pattern specified.")
        
        if self.recurrence_pattern and self.recurrence_pattern.lower() not in ['daily', 'weekly', 'monthly', 'yearly']:
            raise ValidationError("Recurrence pattern must be one of: daily, weekly, monthly, yearly")
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_academic_event_relationships(self)
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete academic event: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class Holiday(TenantOwnedMixin):
    name = models.CharField(max_length=100)
    date = models.DateField()
    is_recurring = models.BooleanField(default=False)
    academic_year = models.CharField(max_length=9)

    class Meta:
        ordering = ['date']
        unique_together = ['school', 'name', 'date', 'academic_year']

    def __str__(self):
        return f"{self.name} ({self.date})"

class ExamSchedule(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    exam_date = models.DateTimeField()
    duration = models.DurationField()
    room = models.CharField(max_length=50, blank=True)
    invigilator = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True)
    academic_event = models.OneToOneField(AcademicEvent, on_delete=models.CASCADE)

    class Meta:
        ordering = ['exam_date']

    def __str__(self):
        return f"{self.subject.name} - {self.school_class.name} ({self.exam_date.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .services_academic import CalendarManager
        from .validators_academic import AcademicDataValidator
        
        # Check if exam date falls on a holiday
        if CalendarManager.is_holiday(self.exam_date.date()):
            raise ValidationError("Exam cannot be scheduled on a holiday.")
        
        # Check for room conflicts if room is specified
        if self.room:
            exam_end_time = self.exam_date + self.duration
            
            # Check for overlapping exams in the same room
            overlapping_exams = ExamSchedule.objects.filter(
                room=self.room,
                exam_date__lt=exam_end_time,
                exam_date__gte=self.exam_date - self.duration
            ).exclude(pk=self.pk)
            
            if overlapping_exams.exists():
                raise ValidationError(f"Room {self.room} is already booked for another exam during this time.")
        
        # Check for invigilator conflicts
        if self.invigilator:
            exam_end_time = self.exam_date + self.duration
            
            # Check for overlapping exams with the same invigilator
            overlapping_invigilator = ExamSchedule.objects.filter(
                invigilator=self.invigilator,
                exam_date__lt=exam_end_time,
                exam_date__gte=self.exam_date - self.duration
            ).exclude(pk=self.pk)
            
            if overlapping_invigilator.exists():
                raise ValidationError(f"Invigilator {self.invigilator} is already assigned to another exam during this time.")
        
        # Check for class conflicts (same class having multiple exams at the same time)
        exam_end_time = self.exam_date + self.duration
        
        overlapping_class_exams = ExamSchedule.objects.filter(
            school_class=self.school_class,
            exam_date__lt=exam_end_time,
            exam_date__gte=self.exam_date - self.duration
        ).exclude(pk=self.pk)
        
        if overlapping_class_exams.exists():
            raise ValidationError(f"Class {self.school_class} already has an exam scheduled during this time.")
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_exam_schedule_relationships(self)
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete exam schedule: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class TimeSlot(TenantOwnedMixin):
    name = models.CharField(max_length=50)  # e.g., "Period 1"
    start_time = models.TimeField()
    end_time = models.TimeField()
    day_of_week = models.IntegerField()  # 0=Monday, 6=Sunday
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        unique_together = ['school', 'name', 'day_of_week', 'start_time']

    def __str__(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return f"{self.name} - {days[self.day_of_week]} ({self.start_time}-{self.end_time})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")

class RoomAssignment(TenantOwnedMixin):
    room_name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField()
    room_type = models.CharField(max_length=50)  # e.g., "Classroom", "Lab", "Hall"
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['room_name']
        unique_together = ['school', 'room_name']

    def __str__(self):
        return f"{self.room_name} ({self.room_type}) - Capacity: {self.capacity}"

class Timetable(models.Model):
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    room = models.ForeignKey(RoomAssignment, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['time_slot', 'term', 'academic_year']

    def __str__(self):
        return f"{self.school_class.name} - {self.subject.name} - {self.time_slot.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Check teacher conflict
        teacher_conflict = Timetable.objects.filter(
            time_slot=self.time_slot,
            teacher=self.teacher,
            term=self.term,
            academic_year=self.academic_year,
            is_active=True
        ).exclude(pk=self.pk)
        
        if teacher_conflict.exists():
            raise ValidationError(f"Teacher {self.teacher} is already assigned to another class during {self.time_slot}")
        
        # Check room conflict
        room_conflict = Timetable.objects.filter(
            time_slot=self.time_slot,
            room=self.room,
            term=self.term,
            academic_year=self.academic_year,
            is_active=True
        ).exclude(pk=self.pk)
        
        if room_conflict.exists():
            raise ValidationError(f"Room {self.room.room_name} is already booked during {self.time_slot}")
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_timetable_relationships(self)
        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete timetable entry: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = RichTextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    school_classes = models.ManyToManyField(SchoolClass)
    due_date = models.DateTimeField()
    max_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    allow_late_submission = models.BooleanField(default=False)
    late_penalty_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    attachment = models.FileField(upload_to='assignments/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.subject.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Check if due date falls on a holiday
        holiday_exists = Holiday.objects.filter(
            date=self.due_date.date(),
            academic_year=self.get_academic_year()
        ).exists()
        
        if holiday_exists:
            raise ValidationError("Assignment due date cannot be on a holiday.")
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_assignment_relationships(self)
        if errors:
            raise ValidationError(errors)

    def get_academic_year(self):
        """Get academic year based on due date"""
        year = self.due_date.year
        if self.due_date.month >= 9:  # September onwards is next academic year
            return f"{year}-{year + 1}"
        else:
            return f"{year - 1}-{year}"

    def is_overdue(self):
        return timezone.now() > self.due_date

    def time_remaining(self):
        if self.is_overdue():
            return None
        return self.due_date - timezone.now()

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete assignment: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    submission_text = RichTextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.assignment.title}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from .validators_academic import AcademicDataValidator
        
        # Enhanced relationship validation
        errors = AcademicDataValidator.validate_assignment_submission_relationships(self)
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Automatically set is_late based on submission time
        if not self.pk:  # Only on creation
            self.is_late = timezone.now() > self.assignment.due_date
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from .validators_academic import ReferentialIntegrityManager
        
        # Check cascade deletion safety
        is_safe, warnings = ReferentialIntegrityManager.safe_delete_with_cascade_check(self)
        if not is_safe and warnings:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete assignment submission: {'; '.join(warnings)}")
        
        super().delete(*args, **kwargs)

class SubmissionFile(models.Model):
    submission = models.ForeignKey(AssignmentSubmission, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='submissions/')
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.submission.student.user.get_full_name()} - {self.original_filename}"

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = self.file.name
        super().save(*args, **kwargs)


# Financial Management Models

class FeeStructure(models.Model):
    name = models.CharField(max_length=100)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    tuition_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    development_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    exam_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    library_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sports_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['school_class', 'term']

    def __str__(self):
        return f"{self.name} - {self.school_class} - {self.term}"

    @property
    def total_fee(self):
        return (self.tuition_fee + self.development_fee + self.exam_fee + 
                self.library_fee + self.sports_fee + self.other_fees)

class StudentFee(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'fee_structure']

    def __str__(self):
        return f"{self.student} - {self.fee_structure.name}"

    @property
    def balance_amount(self):
        return self.total_amount - self.paid_amount - self.discount_amount

    def update_status(self):
        if self.paid_amount >= self.total_amount - self.discount_amount:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partial'
        elif timezone.now().date() > self.due_date:
            self.status = 'overdue'
        else:
            self.status = 'pending'
        self.save()

class FeePayment(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Card'),
        ('online', 'Online'),
    ]
    
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference_number = models.CharField(max_length=100, blank=True)
    payment_date = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student_fee.student} - {self.amount}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update student fee paid amount and status
        self.student_fee.paid_amount = self.student_fee.payments.aggregate(
            total=models.Sum('amount'))['total'] or 0
        self.student_fee.update_status()

class FinancialTransaction(TenantOwnedMixin):
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    CATEGORIES = [
        ('fees', 'School Fees'),
        ('salary', 'Staff Salary'),
        ('utilities', 'Utilities'),
        ('maintenance', 'Maintenance'),
        ('supplies', 'Supplies'),
        ('equipment', 'Equipment'),
        ('other', 'Other'),
    ]
    
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200)
    reference_number = models.CharField(max_length=100, blank=True)
    transaction_date = models.DateField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.amount}"

    class Meta:
        ordering = ['-transaction_date']


class Scholarship(TenantOwnedMixin):
    SCHOLARSHIP_TYPES = [
        ('merit', 'Merit Based'),
        ('need', 'Need Based'),
        ('sports', 'Sports'),
        ('academic', 'Academic Excellence'),
    ]
    
    name = models.CharField(max_length=100)
    scholarship_type = models.CharField(max_length=20, choices=SCHOLARSHIP_TYPES)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_recipients = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    academic_year = models.CharField(max_length=9)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.academic_year}"

class ScholarshipRecipient(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('completed', 'Completed'),
    ]
    
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    awarded_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['scholarship', 'student']

    def __str__(self):
        return f"{self.student} - {self.scholarship.name}"

class PayrollStructure(TenantOwnedMixin):
    name = models.CharField(max_length=100)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    house_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pension_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def gross_salary(self):
        return (self.basic_salary + self.house_allowance + self.transport_allowance + 
                self.medical_allowance + self.other_allowances)

class StaffPayroll(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    payroll_structure = models.ForeignKey(PayrollStructure, on_delete=models.CASCADE)
    month = models.DateField()
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2)
    tax_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pension_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['teacher', 'month']

    def __str__(self):
        return f"{self.teacher} - {self.month.strftime('%B %Y')}"

    def calculate_net_salary(self):
        from .models_loans import TeacherLoan
        self.gross_salary = self.payroll_structure.gross_salary
        self.tax_deduction = (self.gross_salary * self.payroll_structure.tax_rate) / 100
        self.pension_deduction = (self.gross_salary * self.payroll_structure.pension_rate) / 100
        
        # Calculate total loan deductions
        active_loans = TeacherLoan.objects.filter(teacher=self.teacher, status='active')
        total_loan_deduction = sum(loan.monthly_deduction for loan in active_loans)
        
        self.net_salary = (self.gross_salary - self.tax_deduction - 
                          self.pension_deduction - self.other_deductions - total_loan_deduction)
        self.save()


# Library Management Models

class BookCategory(TenantOwnedMixin):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Book Categories'
        unique_together = ['school', 'name']

class Book(models.Model):
    BOOK_TYPES = [
        ('physical', 'Physical Book'),
        ('ebook', 'E-Book'),
        ('audiobook', 'Audio Book'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
        ('lost', 'Lost'),
    ]
    
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    isbn = models.CharField(max_length=13, unique=True, blank=True)
    category = models.ForeignKey(BookCategory, on_delete=models.CASCADE)
    book_type = models.CharField(max_length=20, choices=BOOK_TYPES, default='physical')
    publisher = models.CharField(max_length=200, blank=True)
    publication_year = models.IntegerField(null=True, blank=True)
    pages = models.IntegerField(null=True, blank=True)
    copies_total = models.IntegerField(default=1)
    copies_available = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    location = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='books/covers/', blank=True)
    digital_file = models.FileField(upload_to='books/digital/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} by {self.author}"

    def is_available(self):
        return self.copies_available > 0 and self.status == 'available'

class BookBorrowing(models.Model):
    BORROW_STATUS = [
        ('active', 'Active'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('lost', 'Lost'),
    ]
    
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    borrower = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    borrower_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    borrower_object_id = models.PositiveIntegerField(null=True, blank=True)
    borrower_generic = GenericForeignKey('borrower_content_type', 'borrower_object_id')
    borrowed_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    returned_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=BORROW_STATUS, default='active')
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        borrower_name = self.get_borrower_name()
        return f"{self.book.title} - {borrower_name}"
    
    def get_borrower_name(self):
        if self.borrower:
            return self.borrower.user.get_full_name()
        elif self.borrower_generic:
            return self.borrower_generic.user.get_full_name()
        return 'Unknown'
    
    def get_borrower_id(self):
        if self.borrower:
            return self.borrower.student_id
        elif self.borrower_generic and isinstance(self.borrower_generic, Teacher):
            return self.borrower_generic.employee_id
        return 'N/A'

    def is_overdue(self):
        if self.status == 'active' and self.due_date < timezone.now().date():
            return True
        return False

    def days_overdue(self):
        if self.is_overdue():
            return (timezone.now().date() - self.due_date).days
        return 0

    def calculate_fine(self, daily_fine=5.0):
        if self.is_overdue():
            self.fine_amount = self.days_overdue() * daily_fine
            self.status = 'overdue'
            self.save()

class DigitalResource(models.Model):
    RESOURCE_TYPES = [
        ('ebook', 'E-Book'),
        ('journal', 'Journal'),
        ('article', 'Article'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
    ]
    
    ACCESS_LEVELS = [
        ('public', 'Public'),
        ('students', 'Students Only'),
        ('teachers', 'Teachers Only'),
        ('restricted', 'Restricted'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    category = models.ForeignKey(BookCategory, on_delete=models.CASCADE)
    file = models.FileField(upload_to='digital_resources/', blank=True)
    url = models.URLField(blank=True)
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVELS, default='students')
    file_size = models.BigIntegerField(null=True, blank=True)
    download_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def increment_download(self):
        self.download_count += 1
        self.save()


# Financial Audit Logging Model

class FinancialAuditLog(TenantOwnedMixin):
    OPERATION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('payment', 'Payment'),
        ('bulk_operation', 'Bulk Operation'),
    ]
    
    MODEL_CHOICES = [
        ('fee_structure', 'Fee Structure'),
        ('student_fee', 'Student Fee'),
        ('fee_payment', 'Fee Payment'),
        ('scholarship', 'Scholarship'),
        ('scholarship_recipient', 'Scholarship Recipient'),
        ('staff_payroll', 'Staff Payroll'),
        ('financial_transaction', 'Financial Transaction'),
        ('payroll_structure', 'Payroll Structure'),
    ]
    
    operation = models.CharField(max_length=20, choices=OPERATION_CHOICES)
    model_name = models.CharField(max_length=30, choices=MODEL_CHOICES)
    object_id = models.PositiveIntegerField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(default=dict)  # Store before/after values
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['operation', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_operation_display()} {self.get_model_name_display()} by {self.user}"


# Notification System Models

class NotificationTemplate(TenantOwnedMixin):
    """Model for storing customizable notification templates"""
    
    TEMPLATE_TYPES = [
        ('payment_reminder', 'Payment Reminder'),
        ('payment_confirmation', 'Payment Confirmation'),
        ('scholarship_award', 'Scholarship Award'),
        ('payroll_processing', 'Payroll Processing'),
        ('overdue_payment', 'Overdue Payment'),
        ('bulk_operation_complete', 'Bulk Operation Complete'),
    ]
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    subject_template = models.CharField(max_length=200)
    html_template = models.TextField()
    text_template = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['school', 'template_type', 'name']
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class NotificationLog(TenantOwnedMixin):
    """Model for tracking notification delivery"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
    ]
    
    notification_type = models.CharField(max_length=30)
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    context_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['notification_type', 'recipient_email']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient_email} - {self.status}"
    
    def can_retry(self):
        return self.retry_count < self.max_retries and self.status in ['failed', 'retry']



# Import feature control models
from .models_features import FeatureFlag, FeatureControlAdmin, SchoolTenant, SchoolDomain, SchoolMembership, TenantFeatureOverride, TenantDataExportRequest
from .models_reports import GeneratedReport
from .models_loans import TeacherLoan, PayrollDeduction
from .models_daily_attendance import DailyAttendanceSession, DailyAttendanceRecord, TermAttendanceSummary
from .models_attendance import IDCard, AttendanceSession, AttendanceRecord, Visitor
from .models_biodata import (
    StudentBioData, Guardian, StaffBioData, StaffQualification,
    StaffGuarantor, StaffBankAccount, PaymentSchedule,
)
from .models_parent_device import ParentDevice
from .services_report_customization import ScheduledReport, ReportExecution


for model, lookup in (
    (SchoolSettings, 'school'),
    (QuestionGroup, 'subject__school'),
    (QuestionBank, 'subject__school'),
    (ResultComponent, 'school_class__school'),
    (AISubscription, 'teacher__school'),
    (ClassTeacher, 'teacher__school'),
    (HeadTeacher, 'teacher__school'),
    (ResultToken, 'student__school'),
    (Attendance, 'student__school'),
    (Comment, 'student__school'),
    (Psychomotor, 'student__school'),
    (EffectiveDomain, 'student__school'),
    (ComponentResult, 'student__school'),
    (Result, 'student__school'),
    (Quiz, 'school_class__school'),
    (QuestionGroupInstance, 'quiz__school_class__school'),
    (Question, 'quiz__school_class__school'),
    (QuizAttempt, 'student__school'),
    (QuizAnswer, 'attempt__student__school'),
    (LearningObjective, 'curriculum__school'),
    (SyllabusContent, 'curriculum__school'),
    (LessonPlan, 'school_class__school'),
    (CurriculumCoverage, 'school_class__school'),
    (LessonNote, 'lesson_plan__school_class__school'),
    (ExamSchedule, 'school_class__school'),
    (Timetable, 'school_class__school'),
    (Assignment, 'school_classes__school'),
    (AssignmentSubmission, 'student__school'),
    (SubmissionFile, 'submission__student__school'),
    (FeeStructure, 'school_class__school'),
    (StudentFee, 'student__school'),
    (FeePayment, 'student_fee__student__school'),
    (ScholarshipRecipient, 'student__school'),
    (StaffPayroll, 'teacher__school'),
    (Book, 'category__school'),
    (BookBorrowing, 'book__category__school'),
    (DigitalResource, 'category__school'),
    (TeacherLoan, 'teacher__school'),
    (PayrollDeduction, 'payroll__teacher__school'),
    (DailyAttendanceSession, 'school_class__school'),
    (DailyAttendanceRecord, 'student__school'),
    (TermAttendanceSummary, 'student__school'),
    (IDCard, ('student__school', 'teacher__school')),
    (AttendanceRecord, 'session__school'),
    (StudentBioData, 'student__school'),
    (Guardian, 'student__school'),
    (StaffBioData, 'teacher__school'),
    (StaffQualification, 'staff_bio_data__teacher__school'),
    (StaffGuarantor, 'staff_bio_data__teacher__school'),
    (StaffBankAccount, 'staff_bio_data__teacher__school'),
    (PaymentSchedule, 'teacher__school'),
    (ParentDevice, 'student__school'),
    (ReportExecution, 'scheduled_report__school'),
):
    install_tenant_manager(model, lookup)
