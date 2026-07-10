import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../../models/product.dart';
import '../../theme/app_colors.dart';
import '../common/badge_pill.dart';

final _bdtFormat = NumberFormat.currency(locale: 'en_US', symbol: '৳', decimalDigits: 2);
String formatBdt(double value) => _bdtFormat.format(value);

Widget _productThumbnail(String? imageUrl) {
  if (imageUrl == null) {
    return Container(color: AppColors.paperWarm, child: const Center(child: Text('🛒', style: TextStyle(fontSize: 32))));
  }
  return CachedNetworkImage(
    imageUrl: imageUrl,
    fit: BoxFit.cover,
    placeholder: (context, url) => Container(color: AppColors.paperWarm),
    errorWidget: (context, url, error) =>
        Container(color: AppColors.paperWarm, child: const Center(child: Text('🛒', style: TextStyle(fontSize: 32)))),
  );
}

class ProductCard extends StatelessWidget {
  final Product product;

  const ProductCard({super.key, required this.product});

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.push('/products/${product.id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: _productThumbnail(product.imageUrl)),
            Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(product.nameEn, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                  const SizedBox(height: 2),
                  Text(product.packLabel, style: const TextStyle(color: AppColors.inkMuted, fontSize: 11)),
                  const SizedBox(height: 4),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Flexible(child: Text(formatBdt(product.priceBdt), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12))),
                      BadgePill(
                        label: product.inStock ? 'In stock' : 'Out of stock',
                        tone: product.inStock ? BadgeTone.primary : BadgeTone.warning,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
