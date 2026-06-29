import 'dart:convert';
import 'package:http/http.dart' as http;

class DBHelper {
  
  static const String baseUrl = 'http://192.168.1.7:5000';

  static Map<String, String> get _headers => {
        'Content-Type': 'application/json',
      };

  static dynamic _decodeResponse(http.Response response) {
    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  static Future<Map<String, dynamic>?> login(
    String email,
    String password,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl/login'),
      headers: _headers,
      body: jsonEncode({
        'email': email,
        'password': password,
      }),
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is Map<String, dynamic>) {
        return data['user'] as Map<String, dynamic>?;
      }
    }

    return null;
  }

  static Future<int> insertCustomer(Map<String, dynamic> customer) async {
    final response = await http.post(
      Uri.parse('$baseUrl/register'),
      headers: _headers,
      body: jsonEncode(customer),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = _decodeResponse(response);
      return data['CustomerID'] as int;
    }

    throw Exception('Failed to register customer: ${response.body}');
  }

  static Future<int> insertVehicle(Map<String, dynamic> vehicle) async {
    final response = await http.post(
      Uri.parse('$baseUrl/add_vehicle'),
      headers: _headers,
      body: jsonEncode(vehicle),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = _decodeResponse(response);
      return data['VehicleID'] as int;
    }

    throw Exception('Failed to add vehicle: ${response.body}');
  }

  static Future<Map<String, dynamic>?> getCustomerById(int customerId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/customer/$customerId'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is Map<String, dynamic>) {
        return data;
      }
    }

    return null;
  }

  static Future<int> updateCustomer(
    int customerId,
    Map<String, dynamic> data,
  ) async {
    final response = await http.put(
      Uri.parse('$baseUrl/customer/$customerId'),
      headers: _headers,
      body: jsonEncode(data),
    );

    if (response.statusCode == 200) {
      return 1;
    }

    throw Exception('Failed to update profile: ${response.body}');
  }

  static Future<List<Map<String, dynamic>>> getVehiclesByCustomerId(
    int customerId,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/customer/$customerId/vehicles'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is List) {
        return List<Map<String, dynamic>>.from(data);
      }
    }

    return [];
  }

  static Future<List<Map<String, dynamic>>> getAvailableSpots() async {
    final response = await http.get(
      Uri.parse('$baseUrl/available_spots'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is List) {
        return List<Map<String, dynamic>>.from(data);
      }
    }

    return [];
  }

  static Future<int> startParkingSession({
    required int vehicleId,
    required int spotId,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/start_parking'),
      headers: _headers,
      body: jsonEncode({
        'vehicle_id': vehicleId,
        'spot_id': spotId,
      }),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = _decodeResponse(response);
      return data['SessionID'] as int;
    }

    throw Exception('Failed to start parking session: ${response.body}');
  }

  static Future<Map<String, dynamic>?> retrieveCar(int vehicleId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/retrieve_car'),
      headers: _headers,
      body: jsonEncode({
        'vehicle_id': vehicleId,
      }),
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is Map<String, dynamic>) {
        return data;
      }
    }

    return null;
  }

  static Future<List<Map<String, dynamic>>> getParkingSessionsByCustomerId(
    int customerId,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/customer/$customerId/sessions'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is List) {
        return List<Map<String, dynamic>>.from(data);
      }
    }

    return [];
  }

  static Future<Map<String, dynamic>?> getCurrentParkingStatusByVehicleId(
    int vehicleId,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/vehicle/$vehicleId/current_status'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is Map<String, dynamic>) {
        return data;
      }
    }

    return null;
  }

  static Future<Map<String, dynamic>?> getLatestOpenSessionByVehicleId(
    int vehicleId,
  ) async {
    final response = await http.get(
      Uri.parse('$baseUrl/vehicle/$vehicleId/latest_open_session'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = _decodeResponse(response);
      if (data is Map<String, dynamic>) {
        return data;
      }
    }

    return null;
  }
}