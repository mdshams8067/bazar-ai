import 'package:flutter/material.dart';
import '../../models/order.dart';
import '../../theme/app_colors.dart';

const _steps = [
  (OrderStatus.pending, '🕒', 'Pending'),
  (OrderStatus.confirmed, '✅', 'Confirmed'),
  (OrderStatus.delivered, '📦', 'Delivered'),
];

class StatusTimeline extends StatelessWidget {
  final OrderStatus status;

  const StatusTimeline({super.key, required this.status});

  int get _currentIndex => _steps.indexWhere((s) => s.$1 == status);

  @override
  Widget build(BuildContext context) {
    final current = _currentIndex;
    return Row(
      children: List.generate(_steps.length * 2 - 1, (i) {
        if (i.isOdd) {
          final passed = (i ~/ 2) < current;
          return Expanded(child: Container(height: 2, color: passed ? AppColors.primary : AppColors.line));
        }
        final idx = i ~/ 2;
        final (_, icon, label) = _steps[idx];
        final done = idx <= current;
        return Column(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(color: done ? AppColors.primary : AppColors.line, shape: BoxShape.circle),
              child: Center(
                child: done
                    ? Text(icon, style: const TextStyle(fontSize: 14))
                    : Text('${idx + 1}', style: const TextStyle(color: AppColors.inkMuted, fontSize: 12)),
              ),
            ),
            const SizedBox(height: 4),
            Text(label, style: TextStyle(fontSize: 11, fontWeight: done ? FontWeight.bold : FontWeight.normal, color: done ? AppColors.ink : AppColors.inkMuted)),
          ],
        );
      }),
    );
  }
}
