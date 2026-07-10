import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../models/order.dart';
import '../../services/orders_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/badge_pill.dart';
import '../../widgets/common/empty_state.dart';
import '../../widgets/layout/app_header.dart';
import '../../widgets/product/product_card.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  final _service = OrdersService();
  List<Order> _orders = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await _service.listOrders();
      setState(() {
        _orders = res.items;
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  BadgeTone _tone(OrderStatus s) => switch (s) {
        OrderStatus.pending => BadgeTone.muted,
        OrderStatus.confirmed => BadgeTone.blue,
        OrderStatus.delivered => BadgeTone.primary,
      };

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(appBar: const AppHeader(), body: const Center(child: Text('Loading orders…')));
    }
    if (_orders.isEmpty) {
      return Scaffold(
        appBar: const AppHeader(),
        body: const EmptyState(title: 'No orders yet', subtitle: 'Once you check out, your order history shows up here.'),
      );
    }
    return Scaffold(
      appBar: const AppHeader(),
      body: ListView.separated(
        padding: const EdgeInsets.all(12),
        itemCount: _orders.length,
        separatorBuilder: (_, __) => const Divider(color: AppColors.line),
        itemBuilder: (context, i) {
          final order = _orders[i];
          return ListTile(
            title: Text('Order #${order.id}'),
            subtitle: Text(DateFormat.yMMMd().add_jm().format(order.createdAt.toLocal())),
            trailing: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(formatBdt(order.totalBdt)),
                const SizedBox(height: 4),
                BadgePill(label: order.status.label, tone: _tone(order.status)),
              ],
            ),
            onTap: () => context.push('/orders/${order.id}'),
          );
        },
      ),
    );
  }
}
