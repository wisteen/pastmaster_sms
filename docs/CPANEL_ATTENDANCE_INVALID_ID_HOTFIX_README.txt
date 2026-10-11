VIRTUAKIDS ATTENDANCE INVALID-ID HOTFIX
========================================

CAUSES FIXED
------------
1. The mobile attendance API forced every scanned card to be a student card,
   so every teacher card returned "Invalid ID card".
2. Newly generated cards use a tenant-prefixed barcode. When an older card was
   upgraded in the database, the already printed legacy barcode could stop
   matching the stored value exactly.

BEHAVIOUR AFTER THIS UPDATE
---------------------------
- Student and teacher cards work in the web scanner and attendance API.
- Current tenant-prefixed barcodes, printed card numbers, legacy STUDENT-/
  TEACHER- barcodes, and plain student/employee IDs are accepted.
- Every lookup remains limited to the selected school.
- A tenant-prefixed card from another school is rejected even if both schools
  use the same student or employee number.
- Archived teachers and inactive cards return "This ID card is inactive."

DEPLOYMENT
----------
Upload the files using their relative paths, then restart the cPanel Python
application. There is no database migration for this hotfix.

FILES
-----
core/services_id_cards.py
core/views_attendance.py
core/views_attendance_api.py
core/test_attendance_id_hotfix.py

