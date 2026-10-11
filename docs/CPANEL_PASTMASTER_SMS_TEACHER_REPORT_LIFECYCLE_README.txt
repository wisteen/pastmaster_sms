PASTMASTER SMS TEACHER, REPORT CARD, AND ARCHIVE UPDATE
===================================================

This ZIP contains application code and one additive database migration. It does
not contain a database export and it does not delete existing records.

WHAT THIS UPDATE FIXES
----------------------
1. A teacher's dashboard uses subjects explicitly assigned to that teacher.
   Class assessment subjects are used only when the teacher has no explicit
   subject assignment. This prevents counts such as 19 becoming 25 or 34.
2. Report Card Settings can replace the teacher printed for one class and one
   term. Historical and archived teachers remain selectable for corrections.
3. Teachers can be Active, Former Staff, or Retired. Former/retired staff keep
   their historical records but lose school portal access and are excluded from
   active staff lists and counts.
4. Archived students and teachers have school membership, portal access, and
   result access disabled. Reactivating the profile restores those school-level
   permissions. The global user account is not disabled, so another school
   membership is not affected.

SAFE CPANEL DEPLOYMENT
----------------------
1. Back up the current PostgreSQL database before uploading files. Use the
   cPanel database backup/export tool, or the host's PostgreSQL backup command.
2. Extract the ZIP and upload its files into the Django project using the same
   relative paths. Keep the existing media directory and environment file.
3. Activate the cPanel Python virtual environment for this application.
4. From the folder containing manage.py, run:

      python manage.py migrate core
      python manage.py check

5. Audit the live school data without changing it:

      python manage.py audit_teacher_subjects --school YOUR-SCHOOL-SLUG

   The command prints explicit, class-derived, previous, and corrected subject
   counts for each active teacher. It is read-only.
6. Restart the cPanel Python application.
7. Sign in to the school and verify:
   - Teacher Dashboard > My Subjects
   - School Management > Staff Records
   - Report Card Settings > Teacher shown on report cards

HOW FORMER STUDENTS AND STAFF ARE HANDLED
-----------------------------------------
Do not delete them. Change a student to Graduated, Relocated, or Withdrawn, and
change a teacher to Former Staff or Retired. Their profile, results, attendance,
report cards, comments, and historical references remain in the database. They
are removed from active counts and lists and cannot use that school's portal.

FILES IN THIS PACKAGE
---------------------
core/models.py
core/views.py
core/forms_school_admin.py
core/views_school_admin.py
core/services_term_placements.py
core/migrations/0071_teacher_archival.py
core/management/commands/audit_teacher_subjects.py
core/test_teacher_subject_report_lifecycle.py
templates/admin/report_card_settings.html
templates/school_admin/staff.html
