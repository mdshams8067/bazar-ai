import '../models/order.dart';
import 'api_client.dart';

class OrdersService {
  Future<Order> createOrder({String? paymentMethod}) {
    return ApiClient.instance.run(
      (dio) => dio.post('/orders', data: paymentMethod != null ? {'payment_method': paymentMethod} : {}),
      (data) => Order.fromJson(data as Map<String, dynamic>),
    );
  }

  Future<OrderListResponse> listOrders({int page = 1, int pageSize = 20}) {
    return ApiClient.instance.run(
      (dio) => dio.get('/orders', queryParameters: {'page': page, 'page_size': pageSize}),
      (data) => OrderListResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  Future<Order> getOrder(int id) {
    return ApiClient.instance.run((dio) => dio.get('/orders/$id'), (data) => Order.fromJson(data as Map<String, dynamic>));
  }

  Future<Order> advanceStatus(int id, OrderStatus status) {
    return ApiClient.instance.run(
      (dio) => dio.patch('/orders/$id/status', data: {'status': status.apiValue}),
      (data) => Order.fromJson(data as Map<String, dynamic>),
    );
  }
}
