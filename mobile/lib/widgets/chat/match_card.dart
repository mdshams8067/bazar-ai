import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../../models/chat.dart';
import '../../theme/app_colors.dart';
import '../common/badge_pill.dart';
import '../product/product_card.dart';
import 'pack_size_picker.dart';

(String, String, BadgeTone) _tag(MatchStatus status) => switch (status) {
      MatchStatus.ok => ('✅', 'Added', BadgeTone.primary),
      MatchStatus.substitutedBrand => ('🔁', 'Brand swap', BadgeTone.blue),
      MatchStatus.substitutedFunctional => ('⚠️', 'Substitute', BadgeTone.warning),
      MatchStatus.skippedOptional => ('➖', 'Skipped (optional)', BadgeTone.muted),
      MatchStatus.unavailableEssential => ('⚠️', "Couldn't fulfil", BadgeTone.warning),
      MatchStatus.unmatched => ('➖', 'Not found', BadgeTone.muted),
      MatchStatus.error => ('➖', 'Error', BadgeTone.muted),
      MatchStatus.needsClarification => ('❓', 'Pick a size', BadgeTone.blue),
    };

class MatchCard extends StatelessWidget {
  final IngredientMatch match;

  const MatchCard({super.key, required this.match});

  @override
  Widget build(BuildContext context) {
    if (match.status == MatchStatus.needsClarification && (match.candidates?.isNotEmpty ?? false)) {
      return PackSizePicker(match: match);
    }

    final (icon, label, tone) = _tag(match.status);
    final product = match.product;

    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(color: AppColors.line),
        borderRadius: BorderRadius.circular(AppColors.radiusCard),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 44,
            height: 44,
            child: product?.imageUrl != null
                ? CachedNetworkImage(imageUrl: product!.imageUrl!, fit: BoxFit.cover)
                : Container(color: AppColors.paperWarm),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(product?.nameEn ?? 'Not in catalog', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                const SizedBox(height: 3),
                BadgePill(label: '$icon $label', tone: tone),
                if (product != null) ...[
                  const SizedBox(height: 3),
                  Text('${product.packLabel} · ${formatBdt(product.priceBdt)}',
                      style: const TextStyle(fontSize: 11, color: AppColors.inkMuted)),
                ],
                if (match.note != null) ...[
                  const SizedBox(height: 3),
                  Text(match.note!, style: const TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: AppColors.inkMuted)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
