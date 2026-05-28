import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_list(name, default=None):
    value = os.environ.get(name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(',') if item.strip()]


SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-your-secret-key-here')

DATABASE_PROFILE = os.environ.get('DATABASE_PROFILE', 'local').strip().lower()

DEBUG = _env_bool('DEBUG', DATABASE_PROFILE == 'local')

ALLOWED_HOSTS = _env_list(
    'ALLOWED_HOSTS',
    ['*'] if DATABASE_PROFILE == 'local' else [
        'sms.finpalix.com',
        '.finpalix.com',
        'jewelsofcalvaryschools.com.ng',
        'www.jewelsofcalvaryschools.com.ng',
        'localhost',
        '127.0.0.1',
    ],
)

CSRF_TRUSTED_ORIGINS = _env_list(
    'CSRF_TRUSTED_ORIGINS',
    [
        'https://sms.finpalix.com',
        'http://sms.finpalix.com',
        'https://jewelsofcalvaryschools.com.ng',
        'http://jewelsofcalvaryschools.com.ng',
        'https://www.jewelsofcalvaryschools.com.ng',
        'http://www.jewelsofcalvaryschools.com.ng',
        'https://*.finpalix.com',
        'http://*.finpalix.com',
        'https://*.sms.finpalix.com',
        'http://*.sms.finpalix.com',
    ],
)

CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = _env_bool('CSRF_COOKIE_SECURE', False)
SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', False)
CSRF_FAILURE_VIEW = 'school_management.views.csrf_failure'
CSRF_COOKIE_DOMAIN = os.environ.get('CSRF_COOKIE_DOMAIN') or None
SESSION_COOKIE_DOMAIN = os.environ.get('SESSION_COOKIE_DOMAIN') or None
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',  # For SEO sitemaps
    'django.contrib.sites',     # For SEO
    'ckeditor',
    'ckeditor_uploader',
    'core.apps.CoreConfig',
    'website.apps.WebsiteConfig',
]

# Site ID for django.contrib.sites
SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'core.middleware_tenants.SchoolTenantMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware_csrf.TenantAwareCsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware_roles.ActiveRoleMiddleware',
    'core.middleware_tenant_access.TenantAccessMiddleware',
    'core.services_audit.AuditLogMiddleware',
    'core.middleware_license.SystemLicenseMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'school_management.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.school_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'school_management.wsgi.application'

DATABASE_CONFIGS = {
    'local': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('LOCAL_DB_NAME', 'finpalix_db'),
        'USER': os.environ.get('LOCAL_DB_USER', 'wisteen_finpalix_user'),
        'PASSWORD': os.environ.get('LOCAL_DB_PASSWORD', ''),
        'HOST': os.environ.get('LOCAL_DB_HOST', 'localhost'),
        'PORT': os.environ.get('LOCAL_DB_PORT', '5432'),
    },
    'live': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('LIVE_DB_NAME', 'cvtzapuk_sms'),
        'USER': os.environ.get('LIVE_DB_USER', 'cvtzapuk_smsuser'),
        'PASSWORD': os.environ.get('LIVE_DB_PASSWORD', ''),
        'HOST': os.environ.get('LIVE_DB_HOST', 'localhost'),
        'PORT': os.environ.get('LIVE_DB_PORT', '5432'),
    },
}

DATABASES = {
    'default': DATABASE_CONFIGS.get(DATABASE_PROFILE, DATABASE_CONFIGS['local'])
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

CKEDITOR_UPLOAD_PATH = 'uploads/'
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'extraPlugins': 'mathjax',
        'mathJaxLib': 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-AMS_HTML',
        'height': 150,
    },
}

JAZZMIN_SETTINGS = {
    'site_title': 'Finpalix SMS Admin',
    'site_header': 'Finpalix SMS',
    'site_brand': 'Finpalix SMS',
    'site_logo': None,
    'site_icon': None,
    'login_logo': None,
    'login_logo_dark': None,
    'site_logo_classes': '',
    'login_logo_classes': '',
    'welcome_sign': 'Welcome to Finpalix SMS Admin Portal',
    'copyright': 'Finpalix SMS',
    'search_model': ['core.User', 'core.Student', 'core.Teacher', 'core.Subject', 'core.SchoolClass'],
    'topmenu_links': [
        {'name': 'Admin Home', 'url': 'admin:index', 'permissions': ['core.view_user']},
        {'name': 'Generate Tokens', 'url': 'generate_tokens', 'permissions': ['core.view_user']},
        {'name': 'Visit Website', 'url': '/', 'new_window': True},
    ],
    'show_sidebar': True,
    'navigation_expanded': True,
    
    # Custom menu structure organized by modules
    'custom_links': {
        'core': [
            {'name': 'Dashboard', 'url': '/dashboard/', 'icon': 'fas fa-tachometer-alt'},
            {'name': 'Generate Tokens', 'url': 'generate_tokens', 'icon': 'fas fa-key'},
        ]
    },
    
    'icons': {
        # Authentication & Authorization
        'auth': 'fas fa-shield-alt',
        'auth.user': 'fas fa-user',
        'auth.group': 'fas fa-users',
        
        # User Management
        'core.User': 'fas fa-user-shield',
        'core.Student': 'fas fa-user-graduate',
        'core.Teacher': 'fas fa-chalkboard-teacher',
        'core.ClassTeacher': 'fas fa-user-tie',
        'core.HeadTeacher': 'fas fa-user-crown',
        
        # School Structure
        'core.SchoolClass': 'fas fa-school',
        'core.Subject': 'fas fa-book-open',
        'core.Term': 'fas fa-calendar-alt',
        'core.SchoolSettings': 'fas fa-cogs',
        'core.ReportCardSettings': 'fas fa-file-invoice',
        
        # Academic Management - Curriculum
        'core.Curriculum': 'fas fa-book-reader',
        'core.LearningObjective': 'fas fa-bullseye',
        'core.SyllabusContent': 'fas fa-list-alt',
        'core.LessonPlan': 'fas fa-clipboard-list',
        'core.LessonNote': 'fas fa-sticky-note',
        'core.CurriculumCoverage': 'fas fa-chart-line',
        
        # Academic Management - Calendar & Events
        'core.AcademicEvent': 'fas fa-calendar-day',
        'core.Holiday': 'fas fa-umbrella-beach',
        'core.ExamSchedule': 'fas fa-file-signature',
        
        # Academic Management - Timetable
        'core.TimeSlot': 'fas fa-clock',
        'core.RoomAssignment': 'fas fa-door-open',
        'core.Timetable': 'fas fa-table',
        
        # Academic Management - Assignments
        'core.Assignment': 'fas fa-tasks',
        'core.AssignmentSubmission': 'fas fa-file-upload',
        'core.SubmissionFile': 'fas fa-paperclip',
        
        # Assessment & Results
        'core.GradingSystem': 'fas fa-graduation-cap',
        'core.ResultComponent': 'fas fa-puzzle-piece',
        'core.ComponentResult': 'fas fa-check-square',
        'core.Result': 'fas fa-poll',
        'core.ResultToken': 'fas fa-key',
        'core.Comment': 'fas fa-comment-dots',
        'core.Psychomotor': 'fas fa-running',
        'core.EffectiveDomain': 'fas fa-star',
        
        # Quiz & Question Bank
        'core.QuestionBank': 'fas fa-database',
        'core.QuestionGroup': 'fas fa-layer-group',
        'core.QuestionGroupInstance': 'fas fa-object-group',
        'core.Quiz': 'fas fa-question-circle',
        'core.Question': 'fas fa-question',
        'core.QuizAttempt': 'fas fa-clipboard-check',
        'core.QuizAnswer': 'fas fa-check-double',
        'core.AISubscription': 'fas fa-robot',
        
        # Attendance Management
        'core.Attendance': 'fas fa-calendar-check',
        'core.AttendanceRecord': 'fas fa-user-check',
        'core.Visitor': 'fas fa-id-badge',
        
        # Financial Management - Fees
        'core.FeeStructure': 'fas fa-money-bill-wave',
        'core.StudentFee': 'fas fa-file-invoice-dollar',
        'core.FeePayment': 'fas fa-cash-register',
        'core.FinancialTransaction': 'fas fa-exchange-alt',
        
        # Financial Management - Scholarships
        'core.Scholarship': 'fas fa-award',
        'core.ScholarshipRecipient': 'fas fa-user-graduate',
        
        # Financial Management - Payroll
        'core.PayrollStructure': 'fas fa-file-contract',
        'core.StaffPayroll': 'fas fa-money-check-alt',
        'core.TeacherLoan': 'fas fa-hand-holding-usd',
        'core.PayrollDeduction': 'fas fa-minus-circle',
        
        # Financial Management - Audit
        'core.FinancialAuditLog': 'fas fa-clipboard-list',
        
        # Library Management
        'core.BookCategory': 'fas fa-bookmark',
        'core.Book': 'fas fa-book',
        'core.BookBorrowing': 'fas fa-book-reader',
        'core.DigitalResource': 'fas fa-file-pdf',
        
        # Biodata Management
        'core.StudentBioData': 'fas fa-id-card',
        'core.Guardian': 'fas fa-user-friends',
        'core.StaffBioData': 'fas fa-address-card',
        'core.StaffQualification': 'fas fa-certificate',
        'core.BankAccount': 'fas fa-university',
        
        # Notifications & Communication
        'core.NotificationTemplate': 'fas fa-envelope',
        'core.NotificationLog': 'fas fa-bell',
        
        # Reports & Analytics
        'core.GeneratedReport': 'fas fa-chart-bar',
        
        # System Features
        'core.FeatureFlag': 'fas fa-flag',
        'core.FeatureControlAdmin': 'fas fa-toggle-on',
        'core.SystemLicense': 'fas fa-certificate',
        'core.TenantDataExportRequest': 'fas fa-file-archive',
        
        # Website Management
        'website.WebsiteProfile': 'fas fa-id-card',
        'website.WebsitePage': 'fas fa-file-alt',
        'website.WebsiteSection': 'fas fa-layer-group',
        'website.WebsiteContentItem': 'fas fa-list',
        'website.WebsiteTeamMember': 'fas fa-user-tie',
        'website.NewsPost': 'fas fa-newspaper',
        'website.GalleryImage': 'fas fa-images',
        'website.NewsletterSubscriber': 'fas fa-envelope-open-text',
        'website.NewsletterIssue': 'fas fa-paper-plane',
        'website.Faq': 'fas fa-question-circle',
        'website.DownloadableForm': 'fas fa-file-download',
        'website.Inquiry': 'fas fa-inbox',
    },
    
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
    'related_modal_active': False,
    'custom_css': 'css/admin_custom.css',
    'custom_js': None,
    'use_google_fonts_cdn': True,
    'show_ui_builder': False,
    'changeform_format': 'horizontal_tabs',
    'changeform_format_overrides': {'auth.user': 'collapsible', 'auth.group': 'vertical_tabs'},
    
    # UI Customization - School Colors
    'theme': 'default',
    'dark_mode_theme': None,
    'button_classes': {
        'primary': 'btn-primary',
        'secondary': 'btn-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success'
    },
    
    # Custom menu structure - organized by modules
    'usermenu_links': [
        {'model': 'auth.user'}
    ],
    
    # App ordering in sidebar
    'order_with_respect_to': [
        'auth',
        'core',
        'website',
    ],
    
    # Hide specific models from sidebar
    'hide_models': [],
    
    # Custom app and model ordering
    'custom_menu': [
        {
            'name': 'Dashboard',
            'icon': 'fas fa-tachometer-alt',
            'url': '/dashboard/',
        },
        {
            'app': 'auth',
            'name': 'Authentication',
            'icon': 'fas fa-shield-alt',
            'models': [
                {'name': 'User', 'icon': 'fas fa-user'},
                {'name': 'Group', 'icon': 'fas fa-users'},
            ]
        },
        {
            'name': 'User Management',
            'icon': 'fas fa-users-cog',
            'models': [
                {'model': 'core.User', 'icon': 'fas fa-user-shield'},
                {'model': 'core.Student', 'icon': 'fas fa-user-graduate'},
                {'model': 'core.Teacher', 'icon': 'fas fa-chalkboard-teacher'},
                {'model': 'core.ClassTeacher', 'icon': 'fas fa-user-tie'},
                {'model': 'core.HeadTeacher', 'icon': 'fas fa-user-crown'},
            ]
        },
        {
            'name': 'School Structure',
            'icon': 'fas fa-building',
            'models': [
                {'model': 'core.SchoolClass', 'icon': 'fas fa-school'},
                {'model': 'core.Subject', 'icon': 'fas fa-book-open'},
                {'model': 'core.Term', 'icon': 'fas fa-calendar-alt'},
                {'model': 'core.SchoolSettings', 'icon': 'fas fa-cogs'},
                {'model': 'core.ReportCardSettings', 'icon': 'fas fa-file-invoice'},
            ]
        },
        {
            'name': 'Academic Management',
            'icon': 'fas fa-graduation-cap',
            'children': [
                {
                    'name': 'Curriculum',
                    'icon': 'fas fa-book-reader',
                    'models': [
                        {'model': 'core.Curriculum', 'icon': 'fas fa-book-reader'},
                        {'model': 'core.LearningObjective', 'icon': 'fas fa-bullseye'},
                        {'model': 'core.SyllabusContent', 'icon': 'fas fa-list-alt'},
                        {'model': 'core.LessonPlan', 'icon': 'fas fa-clipboard-list'},
                        {'model': 'core.LessonNote', 'icon': 'fas fa-sticky-note'},
                        {'model': 'core.CurriculumCoverage', 'icon': 'fas fa-chart-line'},
                    ]
                },
                {
                    'name': 'Calendar & Events',
                    'icon': 'fas fa-calendar',
                    'models': [
                        {'model': 'core.AcademicEvent', 'icon': 'fas fa-calendar-day'},
                        {'model': 'core.Holiday', 'icon': 'fas fa-umbrella-beach'},
                        {'model': 'core.ExamSchedule', 'icon': 'fas fa-file-signature'},
                    ]
                },
                {
                    'name': 'Timetable',
                    'icon': 'fas fa-table',
                    'models': [
                        {'model': 'core.TimeSlot', 'icon': 'fas fa-clock'},
                        {'model': 'core.RoomAssignment', 'icon': 'fas fa-door-open'},
                        {'model': 'core.Timetable', 'icon': 'fas fa-table'},
                    ]
                },
                {
                    'name': 'Assignments',
                    'icon': 'fas fa-tasks',
                    'models': [
                        {'model': 'core.Assignment', 'icon': 'fas fa-tasks'},
                        {'model': 'core.AssignmentSubmission', 'icon': 'fas fa-file-upload'},
                        {'model': 'core.SubmissionFile', 'icon': 'fas fa-paperclip'},
                    ]
                },
            ]
        },
        {
            'name': 'Assessment & Results',
            'icon': 'fas fa-poll',
            'models': [
                {'model': 'core.GradingSystem', 'icon': 'fas fa-graduation-cap'},
                {'model': 'core.ResultComponent', 'icon': 'fas fa-puzzle-piece'},
                {'model': 'core.ComponentResult', 'icon': 'fas fa-check-square'},
                {'model': 'core.Result', 'icon': 'fas fa-poll'},
                {'model': 'core.ResultToken', 'icon': 'fas fa-key'},
                {'model': 'core.Comment', 'icon': 'fas fa-comment-dots'},
                {'model': 'core.Psychomotor', 'icon': 'fas fa-running'},
                {'model': 'core.EffectiveDomain', 'icon': 'fas fa-star'},
            ]
        },
        {
            'name': 'Quiz & Question Bank',
            'icon': 'fas fa-question-circle',
            'models': [
                {'model': 'core.QuestionBank', 'icon': 'fas fa-database'},
                {'model': 'core.QuestionGroup', 'icon': 'fas fa-layer-group'},
                {'model': 'core.QuestionGroupInstance', 'icon': 'fas fa-object-group'},
                {'model': 'core.Quiz', 'icon': 'fas fa-question-circle'},
                {'model': 'core.Question', 'icon': 'fas fa-question'},
                {'model': 'core.QuizAttempt', 'icon': 'fas fa-clipboard-check'},
                {'model': 'core.QuizAnswer', 'icon': 'fas fa-check-double'},
                {'model': 'core.AISubscription', 'icon': 'fas fa-robot'},
            ]
        },
        {
            'name': 'Attendance',
            'icon': 'fas fa-calendar-check',
            'models': [
                {'model': 'core.Attendance', 'icon': 'fas fa-calendar-check'},
                {'model': 'core.AttendanceRecord', 'icon': 'fas fa-user-check'},
                {'model': 'core.Visitor', 'icon': 'fas fa-id-badge'},
            ]
        },
        {
            'name': 'Financial Management',
            'icon': 'fas fa-dollar-sign',
            'children': [
                {
                    'name': 'Student Fees',
                    'icon': 'fas fa-money-bill-wave',
                    'models': [
                        {'model': 'core.FeeStructure', 'icon': 'fas fa-money-bill-wave'},
                        {'model': 'core.StudentFee', 'icon': 'fas fa-file-invoice-dollar'},
                        {'model': 'core.FeePayment', 'icon': 'fas fa-cash-register'},
                    ]
                },
                {
                    'name': 'Scholarships',
                    'icon': 'fas fa-award',
                    'models': [
                        {'model': 'core.Scholarship', 'icon': 'fas fa-award'},
                        {'model': 'core.ScholarshipRecipient', 'icon': 'fas fa-user-graduate'},
                    ]
                },
                {
                    'name': 'Staff Payroll',
                    'icon': 'fas fa-money-check-alt',
                    'models': [
                        {'model': 'core.PayrollStructure', 'icon': 'fas fa-file-contract'},
                        {'model': 'core.StaffPayroll', 'icon': 'fas fa-money-check-alt'},
                        {'model': 'core.TeacherLoan', 'icon': 'fas fa-hand-holding-usd'},
                        {'model': 'core.PayrollDeduction', 'icon': 'fas fa-minus-circle'},
                    ]
                },
                {
                    'name': 'Transactions & Audit',
                    'icon': 'fas fa-exchange-alt',
                    'models': [
                        {'model': 'core.FinancialTransaction', 'icon': 'fas fa-exchange-alt'},
                        {'model': 'core.FinancialAuditLog', 'icon': 'fas fa-clipboard-list'},
                    ]
                },
            ]
        },
        {
            'name': 'Library Management',
            'icon': 'fas fa-book',
            'models': [
                {'model': 'core.BookCategory', 'icon': 'fas fa-bookmark'},
                {'model': 'core.Book', 'icon': 'fas fa-book'},
                {'model': 'core.BookBorrowing', 'icon': 'fas fa-book-reader'},
                {'model': 'core.DigitalResource', 'icon': 'fas fa-file-pdf'},
            ]
        },
        {
            'name': 'Biodata Management',
            'icon': 'fas fa-id-card',
            'models': [
                {'model': 'core.StudentBioData', 'icon': 'fas fa-id-card'},
                {'model': 'core.Guardian', 'icon': 'fas fa-user-friends'},
                {'model': 'core.StaffBioData', 'icon': 'fas fa-address-card'},
                {'model': 'core.StaffQualification', 'icon': 'fas fa-certificate'},
                {'model': 'core.BankAccount', 'icon': 'fas fa-university'},
            ]
        },
        {
            'name': 'Notifications',
            'icon': 'fas fa-bell',
            'models': [
                {'model': 'core.NotificationTemplate', 'icon': 'fas fa-envelope'},
                {'model': 'core.NotificationLog', 'icon': 'fas fa-bell'},
            ]
        },
        {
            'name': 'Reports & Analytics',
            'icon': 'fas fa-chart-bar',
            'models': [
                {'model': 'core.GeneratedReport', 'icon': 'fas fa-chart-bar'},
            ]
        },
        {
            'name': 'System Management',
            'icon': 'fas fa-cog',
            'models': [
                {'model': 'core.FeatureFlag', 'icon': 'fas fa-flag'},
                {'model': 'core.FeatureControlAdmin', 'icon': 'fas fa-toggle-on'},
                {'model': 'core.SystemLicense', 'icon': 'fas fa-certificate'},
                {'model': 'core.TenantDataExportRequest', 'icon': 'fas fa-file-archive'},
            ]
        },
        {
            'app': 'website',
            'name': 'Website Management',
            'icon': 'fas fa-globe',
            'models': [
                {'model': 'website.WebsiteProfile', 'icon': 'fas fa-id-card'},
                {'model': 'website.WebsitePage', 'icon': 'fas fa-file-alt'},
                {'model': 'website.WebsiteSection', 'icon': 'fas fa-layer-group'},
                {'model': 'website.WebsiteContentItem', 'icon': 'fas fa-list'},
                {'model': 'website.WebsiteTeamMember', 'icon': 'fas fa-user-tie'},
                {'model': 'website.NewsPost', 'icon': 'fas fa-newspaper'},
                {'model': 'website.GalleryImage', 'icon': 'fas fa-images'},
                {'model': 'website.NewsletterSubscriber', 'icon': 'fas fa-envelope-open-text'},
                {'model': 'website.NewsletterIssue', 'icon': 'fas fa-paper-plane'},
                {'model': 'website.Faq', 'icon': 'fas fa-question-circle'},
                {'model': 'website.DownloadableForm', 'icon': 'fas fa-file-download'},
                {'model': 'website.Inquiry', 'icon': 'fas fa-inbox'},
            ]
        },
    ],
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

AUTH_USER_MODEL = 'core.User'

# Performance & Security Settings
SECURE_CROSS_ORIGIN_OPENER_POLICY = None  # Fix COOP warning in development

# Cache Configuration (Optional - improves performance)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Session Configuration
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
