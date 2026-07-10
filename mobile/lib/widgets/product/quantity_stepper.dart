import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

class QuantityStepper extends StatelessWidget {
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  const QuantityStepper({super.key, required this.value, this.min = 1, required this.max, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(border: Border.all(color: AppColors.line), borderRadius: BorderRadius.circular(AppColors.radiusButton)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            icon: const Icon(Icons.remove, size: 18),
            onPressed: value > min ? () => onChanged(value - 1) : null,
          ),
          SizedBox(width: 28, child: Text('$value', textAlign: TextAlign.center)),
          IconButton(
            icon: const Icon(Icons.add, size: 18),
            onPressed: value < max ? () => onChanged(value + 1) : null,
          ),
        ],
      ),
    );
  }
}
