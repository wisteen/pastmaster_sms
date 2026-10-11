# PastMaster SMS Attendance

The app uses a tenant-aware three-step flow:

1. Fetch active schools from the PastMaster SMS school directory.
2. Let the user choose a school and sign in on that school's domain.
3. Redirect the authenticated security user to that school's attendance clock-in page.

The selected school controls every portal URL. The app does not send attendance activity through a different tenant's domain.

## Backend requirement

Deploy the Django route below before distributing the app:

```text
GET /api/mobile/schools/
```

It returns active schools with their primary domain:

```json
{
  "schools": [
    {
      "name": "Example School",
      "slug": "example-school",
      "base_url": "https://example.sms.pastmaster.top"
    }
  ]
}
```

Each school must have an active `SchoolTenant` and a valid `SchoolDomain`. Mark the preferred domain as primary.

## Run

```powershell
cd flutter_attendance_app
flutter pub get
flutter run --dart-define=DIRECTORY_BASE_URL=https://sms.pastmaster.top
```

`DIRECTORY_BASE_URL` is only used to discover schools. Login, cookies, camera scanning, and attendance requests run on the selected school's `base_url`.

## Validate

```powershell
flutter analyze
flutter test
flutter build apk --debug --dart-define=DIRECTORY_BASE_URL=https://sms.pastmaster.top
```

Android asks for camera access when the school portal opens. If access is denied, the app shows a direct link to system settings.
