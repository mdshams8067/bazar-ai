import 'package:dio/dio.dart';
import '../config/env.dart';

class HealthService {
  final _dio = Dio(BaseOptions(baseUrl: Env.apiBaseUrl));

  Future<bool> ping({Duration timeout = const Duration(seconds: 3)}) async {
    try {
      final res = await _dio.get('/health', options: Options(sendTimeout: timeout, receiveTimeout: timeout));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
