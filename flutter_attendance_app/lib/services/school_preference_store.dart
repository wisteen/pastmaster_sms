import 'package:shared_preferences/shared_preferences.dart';

abstract interface class SchoolPreferenceStore {
  Future<String?> readLastSchoolSlug();

  Future<void> saveLastSchoolSlug(String slug);
}

class SharedPreferencesSchoolStore implements SchoolPreferenceStore {
  static const _key = 'last_school_slug';

  @override
  Future<String?> readLastSchoolSlug() async {
    final preferences = await SharedPreferences.getInstance();
    return preferences.getString(_key);
  }

  @override
  Future<void> saveLastSchoolSlug(String slug) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(_key, slug);
  }
}
