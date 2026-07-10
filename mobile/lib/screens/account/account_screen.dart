import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/cart_provider.dart';
import '../../theme/app_colors.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.user;
    if (user == null) {
      return const Scaffold(body: SizedBox.shrink());
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(user.name, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 4),
                    Text(user.email, style: const TextStyle(color: AppColors.inkMuted)),
                    if (user.phone != null) ...[
                      const SizedBox(height: 4),
                      Text(user.phone!, style: const TextStyle(color: AppColors.inkMuted)),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                title: const Text('Order history'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push('/orders'),
              ),
            ),
            const SizedBox(height: 24),
            OutlinedButton(
              onPressed: () async {
                await auth.logout();
                context.read<CartProvider>().reset();
                if (context.mounted) context.go('/');
              },
              child: const Text('Sign out'),
            ),
          ],
        ),
      ),
    );
  }
}
