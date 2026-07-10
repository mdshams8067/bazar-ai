import 'api_client.dart';

class PaymentService {
  Future<String> initSslcommerz(int orderId) {
    return ApiClient.instance.run(
      (dio) => dio.post('/payment/sslcommerz/init/$orderId'),
      (data) => (data as Map<String, dynamic>)['gateway_url'] as String,
    );
  }
}
