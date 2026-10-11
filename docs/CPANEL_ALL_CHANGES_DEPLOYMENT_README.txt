VIRTUAKIDS SMS - CPANEL ALL CHANGES DEPLOYMENT
================================================

This archive contains the full current application source, including Django,
templates, static source files, migrations, tests, scripts, website CMS, and
Flutter source.

The archive intentionally does not include:
- .env or other local secrets
- db.sqlite3 or database backup files
- media/user uploads
- venv, Git metadata, caches, logs, or generated build folders
- generated staticfiles (regenerate these on the server)

DEPLOYMENT
1. Back up the production files and database in cPanel.
2. Extract this ZIP into the Django application root (where manage.py exists).
3. Keep the production .env and media directory already on the server.
4. Activate the cPanel Python virtual environment.
5. Install/update requirements:
      pip install -r requirements.txt
6. Review the migration plan:
      python manage.py migrate --plan
7. Apply migrations:
      python manage.py migrate
8. Rebuild static files:
      python manage.py collectstatic --noinput
9. Restart the cPanel Python application.
10. Check the assignment, quiz, login, dashboard, results, and attendance pages.

IMPORTANT
The pending migration chain contains historical student-promotion and staffing
data migrations as well as the assessment integrity migration. Review the
production migration plan and retain a database backup before applying it.

Do not replace the production .env, database, or media directory with local
files. They are intentionally absent from this archive.
