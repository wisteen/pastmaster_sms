PASTMASTER SMS ACTIVE PEOPLE / STAFF UPDATE
Deployment date: 2026-09-29

This package adds active-only statistics, tenant-safe guardian selection,
non-teaching staff roles and custom titles, shared staff-profile backfill,
staff ID cards, staff clock-in/out eligibility, and generic staff routing.

DEPLOYMENT

1. Back up the current application files and the production database.
2. Upload and extract the ZIP in the folder that contains manage.py. Preserve
   the paths inside the archive and allow the listed files to be overwritten.
3. Activate the cPanel Python virtual environment for this application.
4. Run:

       python manage.py migrate

5. Run:

       python manage.py check

6. Restart the cPanel/Passenger Python application (use Restart Application in
   cPanel, or touch tmp/restart.txt if that is how this app is configured).
7. Verify all of the following under at least two school tenants:
   - dashboard/statistics exclude inactive learners, staff, accounts, and memberships;
   - guardian selection shows only active parents from the learner's school;
   - Cleaner, Clerk, Driver, Nurse, Maintenance, Security, Administrator, and
     Other / Non-teaching Staff accounts can be created;
   - Other / Non-teaching Staff requires and displays its custom job title;
   - active staff profiles and ID cards are available, printable, and tenant-scoped;
   - eligible non-teaching staff can clock in and out, while inactive or
     terminated staff are rejected;
   - generic staff login reaches the staff dashboard without admin privileges;
   - the configured Back to Home URL works, and an unconfigured school safely
     falls back to the tenant homepage.

NOTES

- Migration 0072 preserves existing records, adds the new choices/title field,
  converts legacy teacher card holder types to Staff, and backfills only missing
  profiles for active eligible accounts. It does not activate inactive staff.
- Existing legacy TEACHER/TCH card values remain accepted by the scanner.
- Do not skip the database backup or migration step.
