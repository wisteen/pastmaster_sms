VIRTUAKIDS CPANEL MOBILE MODULE HOTFIX
Prepared: 27 September 2026

PROBLEM
The cumulative update included core/urls.py, which imports core.views_mobile, but the
views_mobile.py file was accidentally omitted from that ZIP. Django therefore stopped during URL
loading with: ImportError: cannot import name 'views_mobile' from 'core'.

FIX FOR THE CURRENT BROKEN DEPLOYMENT
1. Upload this hotfix ZIP to /home/ndsfdddh/sms (the directory containing manage.py).
2. Extract it there. It adds core/views_mobile.py; it does not replace configuration or data.
3. Activate the production virtual environment and run:

   python manage.py check
   python manage.py migrate

4. Restart the cPanel Python application.

The mobile school-directory module is read-only. It lists active schools with valid configured
domains for the attendance client. It does not change tenants, students, results or attendance.

Fresh deployments should use the corrected cumulative v2 ZIP instead of the earlier cumulative
archive. The v2 archive already contains this file.
