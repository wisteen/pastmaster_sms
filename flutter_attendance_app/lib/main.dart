import 'package:flutter/material.dart';

import 'models/school.dart';
import 'screens/attendance_screen.dart';
import 'screens/school_selection_screen.dart';
import 'services/school_directory_service.dart';
import 'services/school_preference_store.dart';

void main() {
  runApp(const AttendanceApp());
}

class AttendanceApp extends StatelessWidget {
  const AttendanceApp({
    super.key,
    this.schoolDirectory,
    this.preferenceStore,
  });

  final SchoolDirectory? schoolDirectory;
  final SchoolPreferenceStore? preferenceStore;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: navigatorKey,
      title: 'Virtuakids Attendance',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF2459C4),
          brightness: Brightness.light,
          surface: const Color(0xFFF9FAFC),
        ),
        scaffoldBackgroundColor: const Color(0xFFF9FAFC),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(8)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(8)),
            borderSide: BorderSide(color: Color(0xFFD8DEE9)),
          ),
          contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
        ),
      ),
      home: SchoolSelectionScreen(
        directory: schoolDirectory ?? RemoteSchoolDirectory(),
        preferenceStore: preferenceStore ?? SharedPreferencesSchoolStore(),
        onSchoolSelected: (school) => _openAttendance(school),
      ),
      debugShowCheckedModeBanner: false,
    );
  }

  void _openAttendance(School school) {
    navigatorKey.currentState?.push(
      MaterialPageRoute<void>(
        builder: (_) => AttendanceScreen(school: school),
      ),
    );
  }

  static final navigatorKey = GlobalKey<NavigatorState>();
}
