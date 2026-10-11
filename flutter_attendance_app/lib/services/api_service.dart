import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://virtuakids.com.ng',
  );
  static const String attendanceApiKey = String.fromEnvironment(
    'ATTENDANCE_API_KEY',
    defaultValue: '',
  );
  static const String schoolSlug = String.fromEnvironment(
    'SCHOOL_SLUG',
    defaultValue: '',
  );

  Map<String, String> get _headers => attendanceApiKey.isEmpty
      ? const {}
      : {'X-Attendance-Key': attendanceApiKey};
  
  Future<Map<String, dynamic>> markAttendance({
    required String studentId,
    File? imageFile,
    Uint8List? imageBytes,
    String? imageName,
    required String sessionId,
    String action = 'auto',
  }) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/api/attendance/mark/'),
      );
      request.headers.addAll(_headers);
      
      request.fields['student_id'] = studentId;
      request.fields['session_id'] = sessionId;
      request.fields['action'] = action;
      if (schoolSlug.isNotEmpty) {
        request.fields['school'] = schoolSlug;
      }
      
      if (kIsWeb && imageBytes != null) {
        request.files.add(http.MultipartFile.fromBytes(
          'image',
          imageBytes,
          filename: imageName ?? 'attendance.jpg',
        ));
      } else if (imageFile != null) {
        request.files.add(await http.MultipartFile.fromPath('image', imageFile.path));
      }
      
      var response = await request.send();
      var responseData = await response.stream.bytesToString();
      
      return json.decode(responseData);
    } catch (e) {
      return {'success': false, 'message': 'Error: $e'};
    }
  }
  
  Future<Map<String, dynamic>> getActiveSession() async {
    try {
      final uri = Uri.parse('$baseUrl/api/attendance/active-session/').replace(
        queryParameters: schoolSlug.isEmpty ? null : {'school': schoolSlug},
      );
      final response = await http.get(
        uri,
        headers: _headers,
      );
      return json.decode(response.body);
    } catch (e) {
      return {'success': false, 'message': 'Error: $e'};
    }
  }
  
  Future<List<dynamic>> getTodayAttendance(String sessionId) async {
    try {
      final uri = Uri.parse('$baseUrl/api/attendance/today/$sessionId/').replace(
        queryParameters: schoolSlug.isEmpty ? null : {'school': schoolSlug},
      );
      final response = await http.get(
        uri,
        headers: _headers,
      );
      final decoded = json.decode(response.body);
      if (decoded is Map<String, dynamic>) {
        return decoded['records'] as List<dynamic>? ?? [];
      }
      return decoded is List<dynamic> ? decoded : [];
    } catch (e) {
      return [];
    }
  }
}
