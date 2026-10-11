PASTMASTER SMS ID CARD CLOCK-IN HOTFIX - 27 SEPTEMBER 2026

Problem corrected
-----------------
The generated ID card encodes a tenant-prefixed barcode value, but the mobile
attendance API was treating that scanned value only as a plain student number.
The web scanner also required one exact barcode field and returned the same
unclear "Invalid ID card" message for every failure.

Files in this package
---------------------
core/services_id_cards.py
core/views_attendance.py
core/views_attendance_api.py

Installation
------------
1. Back up the current project and database.
2. Extract this ZIP into the Django project root (the folder containing
   manage.py), preserving the core/ directory.
3. Replace the three packaged files when prompted.
4. Restart the cPanel Python application.
5. Reload the attendance clock-in page and scan the QR code again.

No database migration is required for this hotfix.

Supported values after this update
----------------------------------
- The exact QR/barcode value encoded on a generated card.
- The card number printed on the card.
- The existing student-number input used by the attendance API.

All lookups remain restricted to the selected school. Inactive cards are still
rejected and now return a clear inactive-card message.

Verification completed
----------------------
- 18 focused attendance and tenant-isolation tests passed.
- Django system check passed with no issues.
