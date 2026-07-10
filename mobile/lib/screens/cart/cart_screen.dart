import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/cart_provider.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/empty_state.dart';
import '../../widgets/cart/cart_line_item.dart';
import '../../widgets/layout/app_header.dart';
import '../../widgets/product/product_card.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key});

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => context.read<CartProvider>().refresh());
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<CartProvider>();
    final cart = provider.cart;

    if (provider.loading && cart == null) {
      return Scaffold(appBar: const AppHeader(), body: const Center(child: Text('Loading your cart…')));
    }
    if (cart == null || cart.items.isEmpty) {
      return Scaffold(
        appBar: const AppHeader(),
        body: EmptyState(
          title: "Your cart's as empty as a Monday fridge",
          subtitle: "Let's fix that — browse the catalog or tell Bazar Buddy what you're cooking.",
          actionLabel: 'Browse products',
          onAction: () => context.go('/products'),
        ),
      );
    }

    return Scaffold(
      appBar: const AppHeader(),
      body: Column(
        children: [
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: cart.items.length,
              separatorBuilder: (_, __) => const Divider(color: AppColors.line),
              itemBuilder: (context, i) {
                final item = cart.items[i];
                return CartLineItem(
                  item: item,
                  onQuantityChanged: (q) => provider.updateItem(item.id, q),
                  onRemove: () => provider.removeItem(item.id),
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: AppColors.paper,
              border: Border(top: BorderSide(color: AppColors.line)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Subtotal (${cart.itemCount} item${cart.itemCount == 1 ? '' : 's'})',
                          style: const TextStyle(color: AppColors.inkMuted)),
                      Text(formatBdt(cart.subtotalBdt), style: Theme.of(context).textTheme.titleLarge),
                    ],
                  ),
                ),
                ElevatedButton(onPressed: () => context.push('/checkout'), child: const Text('Proceed to checkout')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
