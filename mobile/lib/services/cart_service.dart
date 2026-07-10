import '../models/cart.dart';
import 'api_client.dart';

class CartService {
  Future<Cart> getCart() {
    return ApiClient.instance.run((dio) => dio.get('/cart'), (data) => Cart.fromJson(data as Map<String, dynamic>));
  }

  Future<Cart> addItem(int productId, {int quantity = 1, String addedVia = 'manual', String? substitutionNote}) {
    return ApiClient.instance.run(
      (dio) => dio.post('/cart/items', data: {
        'product_id': productId,
        'quantity': quantity,
        'added_via': addedVia,
        if (substitutionNote != null) 'substitution_note': substitutionNote,
      }),
      (data) => Cart.fromJson(data as Map<String, dynamic>),
    );
  }

  Future<Cart> updateItem(int itemId, int quantity) {
    return ApiClient.instance.run(
      (dio) => dio.patch('/cart/items/$itemId', data: {'quantity': quantity}),
      (data) => Cart.fromJson(data as Map<String, dynamic>),
    );
  }

  Future<Cart> removeItem(int itemId) {
    return ApiClient.instance.run(
      (dio) => dio.delete('/cart/items/$itemId'),
      (data) => Cart.fromJson(data as Map<String, dynamic>),
    );
  }

  Future<void> clearCart() {
    return ApiClient.instance.run((dio) => dio.delete('/cart'), (_) => null);
  }
}
