import 'package:flutter/foundation.dart';
import '../models/cart.dart';
import '../services/cart_service.dart';

/// Mirrors frontend/src/store/cartStore.ts.
class CartProvider extends ChangeNotifier {
  final _service = CartService();

  Cart? cart;
  bool loading = false;
  String? error;

  Future<void> refresh() async {
    loading = true;
    notifyListeners();
    try {
      cart = await _service.getCart();
      error = null;
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> addItem(int productId, {int quantity = 1, String addedVia = 'manual', String? substitutionNote}) async {
    cart = await _service.addItem(productId, quantity: quantity, addedVia: addedVia, substitutionNote: substitutionNote);
    notifyListeners();
  }

  Future<void> updateItem(int itemId, int quantity) async {
    cart = await _service.updateItem(itemId, quantity);
    notifyListeners();
  }

  Future<void> removeItem(int itemId) async {
    cart = await _service.removeItem(itemId);
    notifyListeners();
  }

  Future<void> clear() async {
    await _service.clearCart();
    cart = Cart.empty();
    notifyListeners();
  }

  void setCart(Cart newCart) {
    cart = newCart;
    notifyListeners();
  }

  void reset() {
    cart = null;
    notifyListeners();
  }
}
