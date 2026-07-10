import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../models/cart.dart';
import '../../theme/app_colors.dart';
import '../common/badge_pill.dart';
import '../product/product_card.dart';
import '../product/quantity_stepper.dart';

class CartLineItem extends StatelessWidget {
  final CartItem item;
  final ValueChanged<int> onQuantityChanged;
  final VoidCallback onRemove;

  const CartLineItem({super.key, required this.item, required this.onQuantityChanged, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 56,
            height: 56,
            child: item.product.imageUrl != null
                ? CachedNetworkImage(imageUrl: item.product.imageUrl!, fit: BoxFit.cover)
                : Container(color: AppColors.paperWarm, child: const Center(child: Text('🛒'))),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.product.nameEn, style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(item.product.packLabel, style: const TextStyle(color: AppColors.inkMuted, fontSize: 12)),
                if (item.addedVia == AddedVia.assistant) ...[
                  const SizedBox(height: 4),
                  const BadgePill(label: '💬 Added by Bazar Buddy', tone: BadgeTone.blue),
                  if (item.substitutionNote != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(item.substitutionNote!, style: const TextStyle(fontStyle: FontStyle.italic, fontSize: 12, color: AppColors.inkMuted)),
                    ),
                ],
                const SizedBox(height: 6),
                QuantityStepper(value: item.quantity, max: item.product.stockQty, onChanged: onQuantityChanged),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              IconButton(icon: const Icon(Icons.close, size: 18), onPressed: onRemove),
              Text(formatBdt(item.lineTotalBdt), style: const TextStyle(fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }
}
