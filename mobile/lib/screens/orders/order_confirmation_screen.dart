import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../models/order.dart';
import '../../services/orders_service.dart';
import '../../services/payment_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/order/status_timeline.dart';
import '../../widgets/product/product_card.dart';
import '../checkout/payment_webview_screen.dart';

class OrderConfirmationScreen extends StatefulWidget {
  final int orderId;
  final String? payment;
  const OrderConfirmationScreen({super.key, required this.orderId, this.payment});

  @override
  State<OrderConfirmationScreen> createState() => _OrderConfirmationScreenState();
}

class _OrderConfirmationScreenState extends State<OrderConfirmationScreen> {
  final _ordersService = OrdersService();
  final _paymentService = PaymentService();
  Order? _order;
  String? _loadError;
  bool _retrying = false;
  String? _retryError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final o = await _ordersService.getOrder(widget.orderId);
      if (mounted) setState(() => _order = o);
    } catch (e) {
      if (mounted) setState(() => _loadError = e.toString());
    }
  }

  Future<void> _retryPayment() async {
    setState(() {
      _retrying = true;
      _retryError = null;
    });
    try {
      final url = await _paymentService.initSslcommerz(widget.orderId);
      if (!mounted) return;
      final result = await Navigator.of(context).push<String>(
        MaterialPageRoute(builder: (_) => PaymentWebViewScreen(gatewayUrl: url, orderId: widget.orderId)),
      );
      if (mounted && result != null) {
        context.go('/order-confirmation/${widget.orderId}?payment=$result');
        _load();
      }
    } catch (e) {
      setState(() => _retryError = e.toString());
    } finally {
      if (mounted) setState(() => _retrying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loadError != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Order confirmation')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_loadError!, style: const TextStyle(color: AppColors.warning)),
              const SizedBox(height: 12),
              TextButton(onPressed: () => context.go('/orders'), child: const Text('View order history')),
            ],
          ),
        ),
      );
    }
    final order = _order;
    if (order == null) {
      return Scaffold(appBar: AppBar(title: const Text('Order confirmation')), body: const Center(child: Text('Loading your order…')));
    }

    final failed = widget.payment == 'failed' || widget.payment == 'cancelled';
    // Only an incomplete SSLCommerz order can be retried — COD orders get
    // payment_method='cod' set immediately at creation, so paymentMethod
    // stays null only while a gateway payment genuinely hasn't gone through.
    final canRetry = order.paymentMethod == null && order.status == OrderStatus.pending;

    return Scaffold(
      appBar: AppBar(title: const Text('Order confirmation')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (failed) ...[
            const Text('⚠️', style: TextStyle(fontSize: 40)),
            Text(widget.payment == 'cancelled' ? 'Payment cancelled' : 'Payment failed', style: Theme.of(context).textTheme.headlineSmall),
            Text('Order #${order.id} is saved as pending — no payment went through. You can retry below.'),
          ] else ...[
            const Text('🎉', style: TextStyle(fontSize: 40)),
            Text('Order placed!', style: Theme.of(context).textTheme.headlineSmall),
            Text('Order #${order.id} — ${formatBdt(order.totalBdt)}'),
          ],
          const SizedBox(height: 24),
          StatusTimeline(status: order.status),
          const SizedBox(height: 24),
          if (canRetry) ...[
            if (_retryError != null) ...[
              Text(_retryError!, style: const TextStyle(color: AppColors.warning)),
              const SizedBox(height: 8),
            ],
            ElevatedButton(
              onPressed: _retrying ? null : _retryPayment,
              child: Text(_retrying ? 'Redirecting…' : 'Retry payment — ${formatBdt(order.totalBdt)}'),
            ),
          ] else
            Row(
              children: [
                Expanded(child: OutlinedButton(onPressed: () => context.go('/orders'), child: const Text('View order history'))),
                const SizedBox(width: 12),
                Expanded(child: ElevatedButton(onPressed: () => context.go('/products'), child: const Text('Keep shopping'))),
              ],
            ),
        ],
      ),
    );
  }
}
