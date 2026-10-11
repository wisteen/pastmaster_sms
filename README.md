# PastMaster SMS

PastMaster SMS is a multi-tenant school management platform hosted at
[`sms.pastmaster.top`](https://sms.pastmaster.top). It includes school portals,
administration, results, attendance, finance, communications, public school
websites, and a Flutter attendance client.

## Local development

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and replace placeholder secrets.
4. For a zero-configuration local database, set `LOCAL_DB_ENGINE=sqlite` and
   `DEBUG=True` in `.env`.
5. Run `python manage.py migrate`.
6. Create an administrator with `python manage.py createsuperuser`.
7. Start the server with `python manage.py runserver`.

The production host defaults to `sms.pastmaster.top`; tenant subdomains use the
`<school>.sms.pastmaster.top` pattern. Production secrets and real database
credentials must stay in `.env`, which is ignored by Git.

## Flutter attendance client

The companion client lives in `flutter_attendance_app`. From that directory,
run `flutter pub get`, then `flutter run`. Its default directory and API host is
`https://sms.pastmaster.top` and can be overridden with Dart defines documented
in the client README.
