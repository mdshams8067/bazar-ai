import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../../models/product.dart';
import '../../providers/auth_provider.dart';
import '../../providers/cart_provider.dart';
import '../../services/products_service.dart';
import '../../theme/app_colors.dart';
import '../../widgets/common/badge_pill.dart';
import '../../widgets/product/product_card.dart';
import '../../widgets/product/quantity_stepper.dart';

class ProductDetailScreen extends StatefulWidget {
  final int productId;
  const ProductDetailScreen({super.key, required this.productId});

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  final _service = ProductsService();
  Product? _product;
  bool _notFound = false;
  int _qty = 1;
  bool _adding = false;
  bool _added = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final p = await _service.getProduct(widget.productId);
      if (mounted) setState(() => _product = p);
    } catch (_) {
      if (mounted) setState(() => _notFound = true);
    }
  }

  Future<void> _addToCart() async {
    final auth = context.read<AuthProvider>();
    if (!auth.isAuthenticated) {
      context.push('/login?redirect=${Uri.encodeComponent('/products/${widget.productId}')}');
      return;
    }
    setState(() {
      _adding = true;
      _error = null;
    });
    try {
      await context.read<CartProvider>().addItem(widget.productId, quantity: _qty);
      setState(() => _added = true);
      Future.delayed(const Duration(milliseconds: 1500), () {
        if (mounted) setState(() => _added = false);
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_notFound) {
      return Scaffold(
        appBar: AppBar(title: const Text('Product not found')),
        body: Center(
          child: TextButton(onPressed: () => context.push('/products'), child: const Text('Back to products')),
        ),
      );
    }
    final product = _product;
    if (product == null) {
      return const Scaffold(body: Center(child: Text('Loading…')));
    }
    return Scaffold(
      appBar: AppBar(title: Text(product.nameEn)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          AspectRatio(
            aspectRatio: 1.3,
            child: product.imageUrl != null
                ? CachedNetworkImage(imageUrl: product.imageUrl!, fit: BoxFit.cover)
                : Container(color: AppColors.paperWarm, child: const Center(child: Text('🛒', style: TextStyle(fontSize: 48)))),
          ),
          const SizedBox(height: 16),
          Text(product.category, style: const TextStyle(color: AppColors.accentBlue)),
          const SizedBox(height: 4),
          Text(product.nameEn, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text('${product.packLabel} pack', style: const TextStyle(color: AppColors.inkMuted)),
          const SizedBox(height: 8),
          Row(
            children: [
              Text(formatBdt(product.priceBdt), style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(width: 12),
              BadgePill(
                label: product.inStock ? '${product.stockQty} in stock' : 'Out of stock',
                tone: product.inStock ? BadgeTone.primary : BadgeTone.warning,
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (product.inStock)
            Row(
              children: [
                QuantityStepper(
                  value: _qty,
                  max: product.stockQty,
                  onChanged: (v) => setState(() => _qty = v),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: ElevatedButton(
                    onPressed: (_adding || _added) ? null : _addToCart,
                    child: Text(_added ? 'Added to cart ✓' : (_adding ? 'Adding…' : 'Add to cart')),
                  ),
                ),
              ],
            ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: const TextStyle(color: AppColors.warning)),
          ],
        ],
      ),
    );
  }
}
