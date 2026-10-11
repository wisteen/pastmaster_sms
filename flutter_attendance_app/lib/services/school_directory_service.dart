import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/school.dart';

abstract interface class SchoolDirectory {
  Future<List<School>> fetchSchools();
}

class RemoteSchoolDirectory implements SchoolDirectory {
  RemoteSchoolDirectory({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  static const String directoryBaseUrl = String.fromEnvironment(
    'DIRECTORY_BASE_URL',
    defaultValue: 'https://sms.pastmaster.top',
  );

  @override
  Future<List<School>> fetchSchools() async {
    final endpoint = Uri.parse(directoryBaseUrl).resolve('/api/mobile/schools/');
    try {
      final response = await _client.get(endpoint).timeout(
            const Duration(seconds: 15),
          );
      if (response.statusCode != 200) {
        throw const SchoolDirectoryException(
          'The school list is temporarily unavailable.',
        );
      }

      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic> || decoded['schools'] is! List) {
        throw const SchoolDirectoryException(
          'The school list returned an unexpected response.',
        );
      }

      final schools = <School>[];
      for (final item in decoded['schools'] as List<dynamic>) {
        if (item is Map<String, dynamic>) {
          schools.add(School.fromJson(item));
        }
      }
      return schools;
    } on SchoolDirectoryException {
      rethrow;
    } on FormatException {
      throw const SchoolDirectoryException(
        'The school list returned an unexpected response.',
      );
    } catch (_) {
      throw const SchoolDirectoryException(
        'Check your internet connection and try again.',
      );
    }
  }
}

class SchoolDirectoryException implements Exception {
  const SchoolDirectoryException(this.message);

  final String message;
}
