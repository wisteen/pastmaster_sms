# cPanel Deployment Guide for Jewels of Calvary Schools

## ⚠️ CRITICAL ISSUES TO FIX BEFORE DEPLOYMENT

### 🔴 HIGH PRIORITY - SECURITY ISSUES

1. **SECRET_KEY is Exposed**
   - Current: `SECRET_KEY = 'django-insecure-your-secret-key-here'`
   - **ACTION REQUIRED**: Generate a new secret key and store it in `.env`
   - Run this in Python to generate a new key:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```

2. **DEBUG = True in Production**
   - Current: `DEBUG = True`
   - **ACTION REQUIRED**: Set `DEBUG = False` in production
   - This is a MAJOR security risk - exposes sensitive information

3. **ALLOWED_HOSTS = ["*"]**
   - Current: Allows any host
   - **ACTION REQUIRED**: Restrict to your actual domain
   - Example: `ALLOWED_HOSTS = ['jewelscalvary.com', 'www.jewelscalvary.com']`

4. **Using SQLite in Production**
   - Current: `sqlite3` database
   - **ACTION REQUIRED**: Switch to MySQL (cPanel standard)
   - SQLite is NOT recommended for production

### 🟡 MEDIUM PRIORITY

5. **No Environment Variables**
   - Sensitive data is hardcoded
   - **ACTION REQUIRED**: Use `.env` file (already created for you)

6. **Static Files Configuration**
   - Need to collect static files for production
   - **ACTION REQUIRED**: Run `python manage.py collectstatic`

7. **Missing Production Dependencies**
   - Need MySQL client: `mysqlclient` or `PyMySQL`
   - **ACTION REQUIRED**: Add to requirements.txt

---

## 📋 Pre-Deployment Checklist

### Step 1: Update settings.py for Production

Replace the current settings.py with environment variable support:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-your-secret-key-here')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

# Database - Use MySQL in production
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.mysql'),
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '3306'),
        }
    }

# Security Settings for Production
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
```

### Step 2: Update requirements.txt

Add these dependencies:

```txt
Django==4.2.7
django-ckeditor==6.7.0
Pillow
google-generativeai==0.3.2
django-jazzmin
whitenoise
hypothesis
reportlab>=3.6.0
openpyxl>=3.1.0
python-dotenv
mysqlclient  # For MySQL database
gunicorn     # Optional: for better performance
```

### Step 3: cPanel Setup Instructions

#### A. Create MySQL Database
1. Log into cPanel
2. Go to **MySQL Databases**
3. Create a new database (e.g., `jewelscalvary_db`)
4. Create a database user with a strong password
5. Add user to database with ALL PRIVILEGES
6. Note down: database name, username, password

#### B. Setup Python Application
1. Go to **Setup Python App** in cPanel
2. Click **Create Application**
3. Select Python version: **3.11** (or latest available)
4. Application root: `/home/yourusername/truecalms`
5. Application URL: Your domain or subdomain
6. Click **Create**

#### C. Upload Files
1. Use **File Manager** or **FTP** to upload your project
2. Upload to: `/home/yourusername/truecalms/`
3. Exclude: `venv/`, `__pycache__/`, `*.pyc`, `db.sqlite3`

#### D. Install Dependencies
1. In cPanel Python App, click **Enter to virtual environment**
2. Or use SSH terminal:
```bash
cd /home/yourusername/truecalms
source /home/yourusername/virtualenv/truecalms/3.11/bin/activate
pip install -r requirements.txt
```

#### E. Configure Environment Variables
1. Edit `.env` file with your actual values:
   - Generate new SECRET_KEY
   - Set DEBUG=False
   - Add your domain to ALLOWED_HOSTS
   - Add MySQL database credentials
   - Add email settings

#### F. Run Django Commands
```bash
# Activate virtual environment first
source /home/yourusername/virtualenv/truecalms/3.11/bin/activate

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

#### G. Configure .htaccess
1. Update `/home/yourusername/truecalms/.htaccess`
2. Replace `yourusername` with your actual cPanel username
3. Update Python version path if different

#### H. Restart Application
1. Go back to **Setup Python App** in cPanel
2. Click **Restart** button
3. Or click **Stop App** then **Start App**

---

## 🧪 Testing After Deployment

1. **Visit your website**: https://yourdomain.com
2. **Check admin panel**: https://yourdomain.com/admin
3. **Test static files**: Images, CSS, JS should load
4. **Test media uploads**: Try uploading a file
5. **Check SSL**: Ensure HTTPS is working
6. **Test forms**: Contact forms, login, etc.

---

## 🔧 Troubleshooting

### Issue: 500 Internal Server Error
- Check error logs in cPanel: **Errors** section
- Verify `.env` file has correct values
- Check database connection
- Ensure all migrations are run

### Issue: Static files not loading
- Run: `python manage.py collectstatic`
- Check `.htaccess` static file paths
- Verify STATIC_ROOT in settings.py

### Issue: Database connection error
- Verify MySQL credentials in `.env`
- Check database user has correct privileges
- Ensure database exists

### Issue: Permission denied errors
- Check file permissions: 644 for files, 755 for directories
- Ensure media folder is writable: `chmod 755 media/`

---

## 📊 Performance Optimization

1. **Enable caching**:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}
```

2. **Optimize database queries**:
   - Use `select_related()` and `prefetch_related()`
   - Add database indexes

3. **Enable compression**:
   - Already configured with WhiteNoise

4. **Use CDN for static files** (optional):
   - Consider Cloudflare for better performance

---

## 🔐 Security Checklist

- [ ] SECRET_KEY is unique and not exposed
- [ ] DEBUG = False in production
- [ ] ALLOWED_HOSTS is restricted to your domain
- [ ] Using MySQL instead of SQLite
- [ ] SSL/HTTPS is enabled
- [ ] Security headers are configured
- [ ] Admin URL is changed (optional but recommended)
- [ ] Strong database passwords
- [ ] Regular backups configured
- [ ] .env file is not in version control

---

## 📞 Support

If you encounter issues:
1. Check cPanel error logs
2. Check Django logs (if configured)
3. Contact your hosting provider
4. Review Django deployment documentation

---

## 🎉 Post-Deployment

Once deployed successfully:
1. Set up automated backups (database + media files)
2. Configure monitoring (uptime, errors)
3. Set up email notifications
4. Test all features thoroughly
5. Train staff on the system

---

**Last Updated**: May 12, 2026
**Django Version**: 4.2.7
**Python Version**: 3.11+
