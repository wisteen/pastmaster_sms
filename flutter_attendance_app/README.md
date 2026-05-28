# Attendance Mobile App

Flutter mobile app for marking attendance with camera integration.

## Setup Instructions

### 1. Install Flutter
Download from: https://flutter.dev/docs/get-started/install

### 2. Install Dependencies
```bash
cd flutter_attendance_app
flutter pub get
```

### 3. Configure Django Backend

Add to your main urls.py:
```python
from core import urls_attendance_api

urlpatterns += [
    path('', include('core.urls_attendance_api')),
]
```

### 4. Update API Base URL
Edit `lib/services/api_service.dart`:
```dart
static const String baseUrl = 'http://YOUR_IP:8000';
```

### 5. Android Permissions
Create `android/app/src/main/AndroidManifest.xml` and add:
```xml
<uses-permission android:name="android.permission.CAMERA"/>
<uses-permission android:name="android.permission.INTERNET"/>
```

### 6. Run the App
```bash
flutter run
```

## Features
- ✅ Camera capture for attendance
- ✅ Gallery image selection
- ✅ Real-time API integration
- ✅ Student ID input
- ✅ Active session detection

## API Endpoints
- POST `/api/attendance/mark/` - Mark attendance
- GET `/api/attendance/active-session/` - Get active session
- GET `/api/attendance/today/<session_id>/` - Get today's records

## Usage
1. Enter Student ID
2. Capture photo or select from gallery
3. Attendance is automatically submitted to server
