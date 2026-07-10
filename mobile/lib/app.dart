import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'providers/cart_provider.dart';
import 'providers/chat_widget_provider.dart';
import 'providers/products_provider.dart';
import 'routes/app_router.dart';
import 'screens/chat/chat_panel.dart';
import 'theme/app_theme.dart';
import 'widgets/common/cold_start_banner.dart';

class BazarAiApp extends StatelessWidget {
  const BazarAiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()..restore()),
        ChangeNotifierProvider(create: (_) => CartProvider()),
        ChangeNotifierProvider(create: (_) => ChatWidgetProvider()),
        ChangeNotifierProvider(create: (_) => ProductsProvider()),
      ],
      child: Consumer<AuthProvider>(
        builder: (context, auth, _) {
          final router = buildRouter(auth);
          return MaterialApp.router(
            title: 'Bazar AI',
            debugShowCheckedModeBanner: false,
            themeMode: ThemeMode.light,
            theme: AppTheme.light,
            routerConfig: router,
            builder: (context, child) {
              final chatWidget = context.watch<ChatWidgetProvider>();
              return Column(
                children: [
                  const ColdStartBanner(),
                  Expanded(
                    child: Stack(
                      children: [
                        if (child != null) child,
                        if (chatWidget.isOpen) const ChatPanel() else const ChatLauncherButton(),
                      ],
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
