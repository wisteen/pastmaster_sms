VIRTUAKIDS CPANEL UPDATE
Results, report cards, broadsheets, attendance, promotion, curriculum installer, global ads, student dashboard and CBT
Prepared: 27 September 2026

INSTALLATION
1. Back up the production database and Django project files.
2. Upload this ZIP to the Django project root (the folder containing manage.py).
3. Extract it there and allow the included files to overwrite their matching paths.
4. Keep the production .env file and uploaded media directory. Neither is included in this ZIP.
5. Activate the production virtual environment and run:

   python manage.py migrate
   python manage.py check
   python manage.py audit_historical_results

6. Review every issue printed by audit_historical_results. The command is read-only: it does not
   invent or repair uncertain historical classes, teachers, attendance or component marks.
7. Restart the cPanel Python application, then reload the affected pages without using an old cache.

IMPORTANT MIGRATION NOTES
- 0065 adds the previous-class field without changing student rows.
- 0066 applies promotions recorded by the earlier faulty implementation.
- 0067 adds StudentTermPlacement for historical class and report signatory preservation.
- 0068 recovers unambiguous placements from saved component marks.
- 0069 is a state-only migration required by this VirtuaKids model history; it makes no schema or
  data change.
- 0070 adds the tenant curriculum-installation audit trail and the platform-wide advertisement
  model. It does not install curriculum or create advertisements automatically.
- The schema and data steps remain separate for PostgreSQL/cPanel compatibility.
- Migration 0068 cannot prove a former teacher from marks alone. Confirm old class-teacher
  assignments before migration. Ambiguous data is left for review rather than guessed.
- Keep existing uploaded signature files in media storage because frozen placements retain their
  file references.

WHAT THIS UPDATE INCLUDES
- Historical class resolution for result entry, broadsheets, exports, report cards, attendance,
  learner domains and class statistics after promotion.
- Transactional promotion and reversal with preserved term placements and signatory information.
- Atomic attendance validation: negative values and days-present above total-days are rejected,
  days absent is calculated, and no row is saved when any submitted row is invalid.
- Correct selected-term vacation and next-resumption dates on individual, admin and bulk reports.
- CE/exam recovery from the assessment components that own the saved marks, aligned component
  columns, fractional marks, genuine zero handling and explicit missing-mark display.
- Read-only consistency warnings and historical-result audit checks; no fabricated score repairs.
- Corrected teacher Assessment & Results page, including publication locks, server grades,
  ordered saves, stale-request protection, visible errors and preserved zero scores.
- Restored student dashboard services and the dedicated student CBT dashboard.
- Student web clock-in/out, duplicate-action protection, school isolation, School Messages/email
  alerts and optional Firebase push delivery.
- Flutter attendance-client source configured through API_BASE_URL, PORTAL_BASE_URL,
  ATTENDANCE_API_KEY and SCHOOL_SLUG compile-time values.
- The mobile school-directory endpoint used by the attendance client, including its required
  core/views_mobile.py module.
- A guided Federal/NERDC and Lagos State 2026/2027 curriculum installer for teachers and school
  administrators. Users choose individual class levels from Basic 1 through SS 3. Installs are
  tenant-scoped, atomic and repeat-safe, and preserve existing school customizations.
- Optional Lagos terms/calendar setup that preserves existing dates and does not change the active
  term unless the installer explicitly requests it.
- A platform global-advertisement section with image upload, links, schedules, priority, pause and
  delete controls. Only a Django platform superuser can manage ads; current ads display across all
  active tenant portals.

OPTIONAL ATTENDANCE ENVIRONMENT SETTINGS
ATTENDANCE_API_KEY=<long random shared scanner key>
FIREBASE_CREDENTIALS_PATH=<absolute service-account JSON path>

Configure the production email backend and mailbox through cPanel environment variables or the
existing production .env. Do not upload a local secret file.

POST-DEPLOYMENT SMOKE CHECKS
- Open Teacher > Assessment & Results and load both an old class/term and the current class/term.
- Confirm zero marks remain 0, blanks remain missing, edits save on leaving the field, and
  published results are locked.
- Open, print and download the same historical broadsheet.
- Open individual, administrator and bulk report cards and confirm class, teacher/signature,
  CE/exam columns, vacation date and resumption date.
- Open historical attendance for a promoted learner, submit valid totals, then confirm the
  learner's current class did not change.
- Try an invalid attendance row and confirm no attendance row in that submission is changed.
- Promote a test learner only after a backup, verify the destination class, then verify the former
  term still appears under the original class. Reverse only the latest test promotion.
- Sign in as a teacher, open Install Curriculum, choose one provider and level, install it, then
  confirm it appears in Curriculum Management. Reinstall the same choice and confirm no duplicate
  curriculum is created.
- Sign in as the Django platform superuser, open Global Advertisements, publish a short test ad,
  and confirm it appears in at least two tenant portals. Pause or delete the test ad afterward.
- Confirm the production media directory is writable so uploaded global-ad images can be stored.

LOCAL VALIDATION COMPLETED BEFORE PACKAGING
- 104 combined Django regression tests passed, covering the new features and the earlier release.
- 54 academic/dashboard regression tests passed after the installer integration.
- 8 focused curriculum-installer and global-advertisement tests passed.
- 3 mobile school-directory endpoint tests passed.
- 9 JavaScript Assessment & Results interaction tests passed.
- 18 affected Django templates compiled successfully.
- Django system check passed.
- Model/migration consistency check reported no changes.
- Flutter analyzer and Flutter widget test passed for the attendance client.

This is a selective source update, not a full-site backup. It intentionally excludes .env files,
database files/dumps, media uploads, virtual environments, caches and generated Flutter builds.
