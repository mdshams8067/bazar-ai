import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../providers/auth_provider.dart';
import '../../theme/app_theme.dart';
import '../../widgets/common/how_it_works_dialog.dart';
import '../../widgets/layout/app_header.dart';
import '../../widgets/product/category_grid.dart';

const _hasSeenHowItWorksKey = 'has_seen_how_it_works';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    // Post-frame, not directly in initState: showDialog needs a fully
    // built widget tree/Navigator to attach to, which isn't guaranteed
    // to exist yet on the very first build.
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowHowItWorks());
  }

  Future<void> _maybeShowHowItWorks() async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_hasSeenHowItWorksKey) ?? false) return;
    await prefs.setBool(_hasSeenHowItWorksKey, true);
    if (!mounted) return;
    showDialog(context: context, builder: (_) => const HowItWorksDialog());
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      appBar: const AppHeader(),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: const Color(0xFFEAF4EC), borderRadius: BorderRadius.circular(8)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Tell us what you\'re cooking.', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                const Text("We'll sort out the rest.", style: proseTextStyle),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () => context.push('/chat'),
                  child: const Text('💬 Tell Bazar Buddy what you\'re cooking'),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: () => context.go('/products'),
                  child: const Text('Browse the catalog'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Text('Shop by category', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          const CategoryGrid(),
          const SizedBox(height: 24),
          Text(auth.isAuthenticated ? 'Welcome back, ${auth.user?.name ?? ''}' : 'Sign in to start shopping',
              style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}
