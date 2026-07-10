import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../screens/account/account_screen.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/signup_screen.dart';
import '../screens/cart/cart_screen.dart';
import '../screens/checkout/checkout_screen.dart';
import '../screens/home/home_screen.dart';
import '../screens/orders/order_confirmation_screen.dart';
import '../screens/orders/order_detail_screen.dart';
import '../screens/orders/orders_screen.dart';
import '../screens/products/product_detail_screen.dart';
import '../screens/products/products_screen.dart';

const _authGatedPaths = ['/cart', '/checkout', '/orders', '/account'];

GoRouter buildRouter(AuthProvider auth) {
  return GoRouter(
    refreshListenable: auth,
    initialLocation: '/',
    redirect: (context, state) {
      if (auth.status != AuthStatus.ready) return null;
      final path = state.uri.path;
      final needsAuth = _authGatedPaths.any((p) => path.startsWith(p)) || path.startsWith('/orders/');
      if (needsAuth && !auth.isAuthenticated) {
        return '/login?redirect=${Uri.encodeComponent(state.uri.toString())}';
      }
      return null;
    },
    routes: [
      GoRoute(path: '/', builder: (context, state) => const HomeScreen()),
      GoRoute(
        path: '/login',
        builder: (context, state) => LoginScreen(redirect: state.uri.queryParameters['redirect'] ?? '/'),
      ),
      GoRoute(
        path: '/signup',
        builder: (context, state) => SignupScreen(redirect: state.uri.queryParameters['redirect'] ?? '/'),
      ),
      GoRoute(
        path: '/products',
        builder: (context, state) => ProductsScreen(
          initialCategory: state.uri.queryParameters['category'],
          initialSearch: state.uri.queryParameters['search'],
        ),
      ),
      GoRoute(
        path: '/products/:id',
        builder: (context, state) => ProductDetailScreen(productId: int.parse(state.pathParameters['id']!)),
      ),
      GoRoute(path: '/cart', builder: (context, state) => const CartScreen()),
      GoRoute(path: '/checkout', builder: (context, state) => const CheckoutScreen()),
      GoRoute(
        path: '/order-confirmation/:id',
        builder: (context, state) => OrderConfirmationScreen(
          orderId: int.parse(state.pathParameters['id']!),
          payment: state.uri.queryParameters['payment'],
        ),
      ),
      GoRoute(path: '/orders', builder: (context, state) => const OrdersScreen()),
      GoRoute(
        path: '/orders/:id',
        builder: (context, state) => OrderDetailScreen(orderId: int.parse(state.pathParameters['id']!)),
      ),
      GoRoute(path: '/account', builder: (context, state) => const AccountScreen()),
    ],
  );
}
