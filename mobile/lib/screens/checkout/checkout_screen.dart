import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../models/cart.dart';
import '../../providers/cart_provider.dart';
import '../../services/orders_service.dart';
import '../../services/payment_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/product/product_card.dart';
import 'payment_webview_screen.dart';

enum PaymentMethod { sslcommerz, cod }

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _ordersService = OrdersService();
  final _paymentService = PaymentService();

  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _areaCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();

  PaymentMethod _method = PaymentMethod.sslcommerz;
  bool _submitting = false;
  String? _error;
  int? _pendingOrderId;
  Cart? _orderSummary;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    _areaCtrl.dispose();
    _addressCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit(Cart cart) async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (_pendingOrderId != null) {
        final url = await _paymentService.initSslcommerz(_pendingOrderId!);
        if (mounted) await _openGateway(url, _pendingOrderId!);
        return;
      }

      if (_method == PaymentMethod.cod) {
        final order = await _ordersService.createOrder(paymentMethod: 'cod');
        if (mounted) {
          context.read<CartProvider>().setCart(Cart.empty());
          context.go('/order-confirmation/${order.id}');
        }
        return;
      }

      _orderSummary = cart;
      final order = await _ordersService.createOrder();
      _pendingOrderId = order.id;
      context.read<CartProvider>().setCart(Cart.empty());
      final url = await _paymentService.initSslcommerz(order.id);
      if (mounted) await _openGateway(url, order.id);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _openGateway(String url, int orderId) async {
    final result = await openPaymentGateway(context, gatewayUrl: url, orderId: orderId);
    if (mounted && result != null) {
      context.go('/order-confirmation/$orderId?payment=$result');
    }
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<CartProvider>().cart;
    final displayCart = _orderSummary ?? cart;

    if ((displayCart == null || displayCart.items.isEmpty) && _pendingOrderId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Checkout')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Your cart is empty — nothing to check out yet.'),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: () => context.go('/products'), child: const Text('Browse products')),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Checkout')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Delivery details', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(controller: _nameCtrl, decoration: const InputDecoration(hintText: 'Full name')),
          const SizedBox(height: 8),
          TextField(controller: _phoneCtrl, decoration: const InputDecoration(hintText: 'Phone number')),
          const SizedBox(height: 8),
          TextField(controller: _areaCtrl, decoration: const InputDecoration(hintText: 'Area (e.g. Gulshan)')),
          const SizedBox(height: 8),
          TextField(controller: _addressCtrl, maxLines: 2, decoration: const InputDecoration(hintText: 'Full address')),
          const SizedBox(height: 20),
          Text('Payment', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (_pendingOrderId != null)
            const Text("Payment for this order wasn't completed yet — retry below.", style: TextStyle(color: AppColors.warning))
          else
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      backgroundColor: _method == PaymentMethod.sslcommerz ? AppColors.primaryLight : null,
                    ),
                    onPressed: () => setState(() => _method = PaymentMethod.sslcommerz),
                    child: const Text('💳 Pay online'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      backgroundColor: _method == PaymentMethod.cod ? AppColors.primaryLight : null,
                    ),
                    onPressed: () => setState(() => _method = PaymentMethod.cod),
                    child: const Text('💵 Cash on delivery'),
                  ),
                ),
              ],
            ),
          const SizedBox(height: 20),
          Text('Order summary', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (displayCart != null)
            ...displayCart.items.map((item) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(child: Text('${item.quantity} × ${item.product.nameEn}')),
                      Text(formatBdt(item.lineTotalBdt)),
                    ],
                  ),
                )),
          const Divider(),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Total', style: TextStyle(fontWeight: FontWeight.bold)),
              Text(formatBdt(displayCart?.subtotalBdt ?? 0), style: const TextStyle(fontWeight: FontWeight.bold)),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: AppColors.warning)),
            if (_pendingOrderId != null) const Text('Your order is saved — retry when ready.', style: TextStyle(color: AppColors.inkMuted)),
          ],
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _submitting || displayCart == null ? null : () => _submit(displayCart),
            child: Text(_submitLabel(displayCart)),
          ),
        ],
      ),
    );
  }

  String _submitLabel(Cart? cart) {
    final total = formatBdt(cart?.subtotalBdt ?? 0);
    if (_pendingOrderId != null) return _submitting ? 'Redirecting to payment…' : 'Retry payment — $total';
    if (_method == PaymentMethod.cod) return _submitting ? 'Placing order…' : 'Place order (Cash on delivery) — $total';
    return _submitting ? 'Redirecting to payment…' : 'Pay with SSLCommerz — $total';
  }
}
