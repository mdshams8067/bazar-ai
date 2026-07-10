import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/cart_provider.dart';

class AppHeader extends StatelessWidget implements PreferredSizeWidget {
  const AppHeader({super.key});

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final cart = context.watch<CartProvider>().cart;

    return AppBar(
      title: const Text('Bazar AI'),
      actions: [
        IconButton(
          tooltip: 'Ask Bazar Buddy',
          icon: const Text('💬'),
          onPressed: () => context.push('/chat'),
        ),
        Stack(
          alignment: Alignment.topRight,
          children: [
            IconButton(
              icon: const Icon(Icons.shopping_cart_outlined),
              onPressed: () => context.go('/cart'),
            ),
            if (cart != null && cart.itemCount > 0)
              Positioned(
                right: 6,
                top: 6,
                child: Container(
                  padding: const EdgeInsets.all(3),
                  decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                  constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                  child: Text('${cart.itemCount}',
                      style: const TextStyle(color: Colors.white, fontSize: 9), textAlign: TextAlign.center),
                ),
              ),
          ],
        ),
        TextButton(
          onPressed: () => context.go(auth.isAuthenticated ? '/account' : '/login'),
          child: Text(auth.isAuthenticated ? (auth.user?.name.split(' ').first ?? 'Account') : 'Sign in'),
        ),
      ],
    );
  }
}
