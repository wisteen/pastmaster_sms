import 'package:pastmaster_sms_attendance/models/school.dart';
import 'package:pastmaster_sms_attendance/screens/school_selection_screen.dart';
import 'package:pastmaster_sms_attendance/services/school_directory_service.dart';
import 'package:pastmaster_sms_attendance/services/school_preference_store.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('school builds tenant-specific login and clock-in URLs', () {
    final school = School.fromJson({
      'name': 'Calvary School',
      'slug': 'calvary-school',
      'base_url': 'https://calvary.example.com',
    });

    expect(
      school.loginUrl.toString(),
      'https://calvary.example.com/login/?role=security&next=%2Fattendance%2Fmark%2F',
    );
    expect(
      school.clockInUrl.toString(),
      'https://calvary.example.com/attendance/mark/',
    );
  });

  testWidgets('user must select a school before continuing', (tester) async {
    School? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: SchoolSelectionScreen(
          directory: _FakeDirectory(),
          preferenceStore: _MemoryPreferenceStore(),
          onSchoolSelected: (school) => selected = school,
        ),
      ),
    );
    await tester.pumpAndSettle();

    FilledButton nextButton() => tester.widget<FilledButton>(
          find.byKey(const Key('continue_button')),
        );

    expect(find.text('Calvary School'), findsOneWidget);
    expect(nextButton().onPressed, isNull);

    await tester.tap(find.byKey(const Key('school_calvary-school')));
    await tester.pump();
    expect(nextButton().onPressed, isNotNull);

    await tester.tap(find.byKey(const Key('continue_button')));
    await tester.pumpAndSettle();
    expect(selected?.slug, 'calvary-school');
  });
}

class _FakeDirectory implements SchoolDirectory {
  @override
  Future<List<School>> fetchSchools() async => [
        School.fromJson({
          'name': 'Calvary School',
          'slug': 'calvary-school',
          'base_url': 'https://calvary.example.com',
        }),
      ];
}

class _MemoryPreferenceStore implements SchoolPreferenceStore {
  String? value;

  @override
  Future<String?> readLastSchoolSlug() async => value;

  @override
  Future<void> saveLastSchoolSlug(String slug) async => value = slug;
}
