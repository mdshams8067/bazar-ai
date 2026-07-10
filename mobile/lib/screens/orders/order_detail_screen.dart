import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../models/order.dart';
import '../../services/orders_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/order/status_timeline.dart';
import '../../widgets/product/product_card.dart';

class OrderDetailScreen extends StatefulWidget {
  final int orderId;
  const OrderDetailScreen({super.key, required this.orderId});

  @override
  State<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends State<OrderDetailScreen> {
  final _service = OrdersService();
  Order? _order;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final o = await _service.getOrder(widget.orderId);
      if (mounted) setState(() => _order = o);
    } catch (_) {
      if (mounted) setState(() => _order = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final order = _order;
    if (order == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Order')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Loading order…'),
              TextButton(onPressed: () => context.push('/orders'), child: const Text('← Back to orders')),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text('Order #${order.id}')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text('Placed ${DateFormat.yMMMd().add_jm().format(order.createdAt.toLocal())}', style: const TextStyle(color: AppColors.inkMuted)),
          const SizedBox(height: 16),
          StatusTimeline(status: order.status),
          const SizedBox(height: 20),
          ...order.items.map((item) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(child: Text('${item.quantity} × ${item.productNameSnapshot}')),
                    Text(formatBdt(item.lineTotal)),
                  ],
                ),
              )),
          const Divider(),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Total', style: TextStyle(fontWeight: FontWeight.bold)),
              Text(formatBdt(order.totalBdt), style: const TextStyle(fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }
}
