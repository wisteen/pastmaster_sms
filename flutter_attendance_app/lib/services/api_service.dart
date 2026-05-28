import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';
  
  Future<Map<String, dynamic>> markAttendance({
    required String studentId,
    File? imageFile,
    Uint8List? imageBytes,
    String? imageName,
    required String sessionId,
  }) async {
    try {
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/api/attendance/mark/'),
      );
      
      request.fields['student_id'] = studentId;
      request.fields['session_id'] = sessionId;
      
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
      final response = await http.get(Uri.parse('$baseUrl/api/attendance/active-session/'));
      return json.decode(response.body);
    } catch (e) {
      return {'success': false, 'message': 'Error: $e'};
    }
  }
  
  Future<List<dynamic>> getTodayAttendance(String sessionId) async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/attendance/today/$sessionId/'));
      return json.decode(response.body);
    } catch (e) {
      return [];
    }
  }
}
