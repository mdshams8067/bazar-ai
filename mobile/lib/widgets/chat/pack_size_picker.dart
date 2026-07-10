import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/chat.dart';
import '../../providers/cart_provider.dart';
import '../../theme/app_colors.dart';
import '../product/product_card.dart';

/// Mirrors MatchCard.tsx's PackSizePicker branch for `needs_clarification`:
/// nothing is added to cart until a candidate is tapped, which calls
/// POST /cart/items directly — no further chat round-trip.
class PackSizePicker extends StatefulWidget {
  final IngredientMatch match;

  const PackSizePicker({super.key, required this.match});

  @override
  State<PackSizePicker> createState() => _PackSizePickerState();
}

class _PackSizePickerState extends State<PackSizePicker> {
  int? _pickedId;
  bool _adding = false;
  String? _error;

  Future<void> _pick(int productId) async {
    setState(() {
      _adding = true;
      _error = null;
    });
    try {
      await context.read<CartProvider>().addItem(productId, quantity: 1);
      setState(() => _pickedId = productId);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _adding = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final candidates = widget.match.candidates ?? [];
    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.accentBlueTint,
        borderRadius: BorderRadius.circular(AppColors.radiusCard),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.match.note ?? 'Which size would you like?', style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: candidates.map((c) {
              final picked = _pickedId == c.id;
              final disabled = _adding || _pickedId != null;
              return OutlinedButton(
                onPressed: disabled ? null : () => _pick(c.id),
                child: Text(picked ? '✓ ${c.packLabel} · ${formatBdt(c.priceBdt)}' : '${c.packLabel} · ${formatBdt(c.priceBdt)}'),
              );
            }).toList(),
          ),
          if (_error != null) ...[
            const SizedBox(height: 6),
            Text(_error!, style: const TextStyle(color: AppColors.warning, fontSize: 12)),
          ],
        ],
      ),
    );
  }
}
