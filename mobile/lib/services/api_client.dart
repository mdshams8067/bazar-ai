import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../config/env.dart';

class ApiError implements Exception {
  final int status;
  final String detail;

  ApiError(this.status, this.detail);

  @override
  String toString() => detail;
}

/// Thin Dio wrapper mirroring frontend/src/api/client.ts's apiRequest:
/// pulls the current Supabase access token fresh on every request (never
/// cached), and surfaces FastAPI's `{"detail": ...}` error body as ApiError.
class ApiClient {
  ApiClient._internal() {
    _dio = Dio(BaseOptions(baseUrl: Env.apiBaseUrl, connectTimeout: const Duration(seconds: 20)));
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        final session = Supabase.instance.client.auth.currentSession;
        if (session != null) {
          options.headers['Authorization'] = 'Bearer ${session.accessToken}';
        }
        handler.next(options);
      },
      onError: (error, handler) {
        final response = error.response;
        if (response != null) {
          final data = response.data;
          final detail = (data is Map && data['detail'] != null) ? data['detail'].toString() : error.message ?? 'Request failed';
          handler.reject(DioException(
            requestOptions: error.requestOptions,
            error: ApiError(response.statusCode ?? 0, detail),
            response: response,
          ));
          return;
        }
        handler.reject(DioException(
          requestOptions: error.requestOptions,
          error: ApiError(0, 'Could not reach the server. Check your connection.'),
        ));
      },
    ));
  }

  static final ApiClient instance = ApiClient._internal();
  late final Dio _dio;

  Dio get dio => _dio;

  Future<T> run<T>(Future<Response> Function(Dio dio) call, T Function(dynamic data) parse) async {
    try {
      final response = await call(_dio);
      return parse(response.data);
    } on DioException catch (e) {
      if (e.error is ApiError) throw e.error as ApiError;
      throw ApiError(0, e.message ?? 'Request failed');
    }
  }
}
