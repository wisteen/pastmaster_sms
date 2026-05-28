# cPanel PostgreSQL Deployment Troubleshooting

This note covers the errors seen while deploying the SMS platform to `sms.finpalix.com` with PostgreSQL on cPanel.

## cPanel Database

Use the same PostgreSQL user for importing the SQL file and for running Django.

The project now has a database switch:

```text
DATABASE_PROFILE=local
DATABASE_PROFILE=live
```

Local testing uses `local` by default. cPanel must use:

```text
DATABASE_PROFILE=live
```

Production database values:

```text
DB_NAME=cvtzapuk_sms
DB_USER=cvtzapuk_smsuser
DB_PASSWORD=<set in .env or cPanel environment>
DB_HOST=localhost
DB_PORT=5432
```

The Django settings are configured to use only these database credentials.

## Recommended SQL Import File

For cPanel/phpPgAdmin import, use:

```text
database baccups/finpalix_db_backup_cpanel_insert_import_nobom.sql
```

This file is preferred because it avoids common cPanel import problems:

- no UTF-8 BOM at the start of the file
- no database owner commands from the local machine
- insert-based data import that phpPgAdmin handles more reliably

## BOM Syntax Error

Error:

```text
ERROR: syntax error at or near "<BOM>"
LINE 1: <BOM>
```

Cause:

The SQL file starts with an invisible UTF-8 BOM character.

Fix:

Use the `finpalix_db_backup_cpanel_insert_import_nobom.sql` file, or resave the SQL file as UTF-8 without BOM before importing.

## Permission Denied For Tables

Errors:

```text
permission denied for table core_schooldomain
permission denied for table django_migrations
```

Cause:

The tables were imported or created by a different PostgreSQL role, so `cvtzapuk_smsuser` cannot read/write them.

Best fix:

Drop the imported tables and re-import the SQL file while logged in as `cvtzapuk_smsuser`, if cPanel allows it.

Alternative fix in phpPgAdmin:

1. Select database `cvtzapuk_sms`.
2. Open schema `public`.
3. Use the Privileges/Grant screen.
4. Select only user `cvtzapuk_smsuser`.
5. Do not select `PUBLIC`.
6. Do not select group `cvtzapuk_sms`.
7. Uncheck `GRANT OPTION`.
8. Grant normal privileges only.

If SQL commands are available, run each statement directly, not inside a `SELECT COUNT(*) FROM (...)` wrapper:

```sql
GRANT USAGE ON SCHEMA public TO cvtzapuk_smsuser;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public
TO cvtzapuk_smsuser;

GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA public
TO cvtzapuk_smsuser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
TO cvtzapuk_smsuser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES
TO cvtzapuk_smsuser;
```

Do not use `WITH GRANT OPTION` in cPanel unless you are granting to a role that is allowed to receive grant options.

## Tenant Domain

The hosted domain is:

```text
sms.finpalix.com
```

Make sure the `core_schooldomain` table contains a row for this domain and points to the correct school tenant. Without this, tenant lookup can fail or load the wrong school context.

## Tenant Subdomains

These are different hostnames:

```text
jewelsofcalvaryschool.finpalix.com
jewelsofcalvaryschool.sms.finpalix.com
```

If the school domain saved in the database is `jewelsofcalvaryschool.finpalix.com`, then visit exactly:

```text
http://jewelsofcalvaryschool.finpalix.com
```

If you visit `jewelsofcalvaryschool.sms.finpalix.com`, then that exact hostname must also exist in DNS and in the `core_schooldomain` table.

Error:

```text
DNS_PROBE_FINISHED_NXDOMAIN
```

Cause:

The hostname does not exist in DNS yet, or the DNS record has not propagated. Django will not receive the request until DNS resolves.

cPanel DNS fix:

1. Open cPanel Zone Editor for `finpalix.com`.
2. Add an `A` record for the exact tenant hostname.
3. Point it to the same server IP used by `sms.finpalix.com`.
4. If using tenant domains under `sms.finpalix.com`, add the exact record `jewelsofcalvaryschool.sms.finpalix.com`.
5. If using tenant domains directly under `finpalix.com`, add `jewelsofcalvaryschool.finpalix.com`.
6. Wait for DNS propagation, then test again.

For many tenants, use wildcard DNS if cPanel allows it:

```text
*.finpalix.com
```

or:

```text
*.sms.finpalix.com
```

The wildcard should point to the same server/app as `sms.finpalix.com`.

The Django settings trust tenant subdomains for CSRF with:

```python
CSRF_TRUSTED_ORIGINS = [
    'https://sms.finpalix.com',
    'http://sms.finpalix.com',
    'https://*.finpalix.com',
    'http://*.finpalix.com',
    'https://*.sms.finpalix.com',
    'http://*.sms.finpalix.com',
]
```

## Subdomain Shows "Index of /"

If the browser shows:

```text
Index of /
Proudly Served by LiteSpeed Web Server
```

then DNS is working, but cPanel is serving the subdomain as a normal folder instead of sending the request to the Django Python app.

Fix:

1. Open cPanel Domains or Subdomains.
2. Edit `jewelsofcalvaryschool.finpalix.com`.
3. Set its document root to the Django app folder:

```text
/home/cvtzapuk/sms
```

4. Make sure this folder contains:

```text
passenger_wsgi.py
.htaccess
manage.py
school_management/
core/
templates/
```

5. Upload the updated `.htaccess` file.
6. Restart the Python app in cPanel.

The `.htaccess` file should use the cPanel Passenger paths:

```apache
PassengerEnabled On
PassengerAppRoot /home/cvtzapuk/sms
PassengerPython /home/cvtzapuk/virtualenv/sms/3.13/bin/python
PassengerAppEnv production
Options -Indexes
```

If cPanel does not allow changing the document root, create a Python app for the tenant subdomain with:

```text
Application root: /home/cvtzapuk/sms
Application URL: jewelsofcalvaryschool.finpalix.com
Startup file: passenger_wsgi.py
```

## Subdomain Shows 503 Service Unavailable

If the subdomain changes from `Index of /` to:

```text
503 Service Unavailable
```

then LiteSpeed/Passenger is now reaching the Django app, but the app is failing during startup.

First upload the corrected `.htaccess` and restart the Python app. The Python path should be:

```apache
PassengerPython /home/cvtzapuk/virtualenv/sms/3.13/bin/python
```

Then test the app from cPanel Terminal:

```bash
cd /home/cvtzapuk/sms
source /home/cvtzapuk/virtualenv/sms/3.13/bin/activate
python manage.py check
```

If `manage.py check` fails, fix that error first. If it passes but the browser still shows 503, check the Passenger/LiteSpeed error log in cPanel. Common log locations are:

```bash
tail -n 100 ~/logs/error_log
tail -n 100 ~/sms/stderr.log
tail -n 100 ~/sms/passenger.log
```

Also confirm the cPanel Python app values:

```text
Application root: /home/cvtzapuk/sms
Application URL: jewelsofcalvaryschool.finpalix.com
Startup file: passenger_wsgi.py
Entry point: application
```

After any change, restart the Python app.

## Custom Tenant Domain

For Jewels of Calvary, the custom domain is:

```text
jewelsofcalvaryschools.com.ng
```

This domain should serve the same tenant as:

```text
jewelsofcalvaryschool.finpalix.com
```

DNS setup:

```text
jewelsofcalvaryschools.com.ng     A      102.212.247.156
www.jewelsofcalvaryschools.com.ng CNAME  jewelsofcalvaryschools.com.ng
```

If the DNS provider does not allow `CNAME` for `www`, use an `A` record for `www` too:

```text
www.jewelsofcalvaryschools.com.ng A      102.212.247.156
```

cPanel setup:

Add `jewelsofcalvaryschools.com.ng` as an Alias/Parked Domain or Addon Domain on the same hosting account as `finpalix.com`. It must point to the Django app folder:

```text
/home/cvtzapuk/sms
```

If cPanel requires a separate Python app entry, use:

```text
Application root: /home/cvtzapuk/sms
Application URL: jewelsofcalvaryschools.com.ng
Startup file: passenger_wsgi.py
Entry point: application
```

Django tenant setup:

Add these domains to `core_schooldomain` and point both to the Jewels of Calvary school tenant:

```text
jewelsofcalvaryschools.com.ng
www.jewelsofcalvaryschools.com.ng
```

The project settings already include these hosts in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

## WSGIRequest Has No User

Error:

```text
AttributeError: 'WSGIRequest' object has no attribute 'user'
```

Cause:

An earlier middleware/database error happened before Django's authentication middleware attached `request.user`. The error page then tried to access `request.user` inside the school settings context processor.

Fix applied:

`core/context_processors.py` now checks for `request.user` safely with `getattr()` before using it.

Also upload these patched files to cPanel:

```text
core/context_processors.py
school_management/views.py
```

Restart the Python app after upload.

## CSRF Cookie Not Set On Login

Error:

```text
Forbidden (403)
CSRF verification failed. Request aborted.
Reason given for failure: CSRF cookie not set.
```

Checks:

1. Open the login page with the same domain used for the POST request:

```text
https://sms.finpalix.com
```

2. Do not switch between `http://`, `https://`, `www`, and non-`www` when logging in.
3. Make sure browser cookies are enabled.
4. Reload the login page before submitting the form.
5. Confirm the login form contains `{% csrf_token %}`.
6. Restart the cPanel Python app after uploading code changes.

Fix applied:

`core/views.py` now uses `@ensure_csrf_cookie` on `login_view`, so Django explicitly sends the CSRF cookie when the login page is loaded.

Upload these files for the CSRF fix:

```text
core/views.py
school_management/settings.py
school_management/views.py
templates/403_csrf.html
```

Production settings added:

```python
CSRF_TRUSTED_ORIGINS = ['https://sms.finpalix.com', 'http://sms.finpalix.com']
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
```

If the site is accessed over plain `http://` while secure cookies are enabled, the browser will not send the CSRF/session cookies. Use HTTPS for production.

Current cPanel setup is using:

```text
http://sms.finpalix.com/admin/login/
```

Because this is HTTP, the project currently sets:

```python
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
```

When SSL/HTTPS is active and the site is loaded through `https://sms.finpalix.com`, these can be changed to `True`.

If the page still shows CSRF failure on:

```text
https://sms.finpalix.com/login/?role=super_admin
```

upload the files above, restart the Python app, then clear cookies for `finpalix.com` in the browser and reload the login page before submitting. The custom CSRF page will show the exact production reason.

For shared tenant cookies across subdomains, cPanel can optionally set:

```text
CSRF_COOKIE_DOMAIN=.finpalix.com
SESSION_COOKIE_DOMAIN=.finpalix.com
```

## cPanel Environment Variables

Set these in the cPanel Python app environment:

```text
DATABASE_PROFILE=live
DEBUG=False
ALLOWED_HOSTS=sms.finpalix.com,.finpalix.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://sms.finpalix.com,http://sms.finpalix.com
```

After changing environment variables:

1. Save the cPanel Python app settings.
2. Restart the Python app.
3. Run migrations again:

```bash
python manage.py migrate
```

4. Create the superuser:

```bash
python manage.py createsuperuser
```
