import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

class EmptyState extends StatelessWidget {
  final String title;
  final String subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const EmptyState({super.key, required this.title, required this.subtitle, this.actionLabel, this.onAction});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge, textAlign: TextAlign.center),
          const SizedBox(height: 8),
          Text(subtitle, style: const TextStyle(color: AppColors.inkMuted), textAlign: TextAlign.center),
          if (actionLabel != null) ...[
            const SizedBox(height: 16),
            ElevatedButton(onPressed: onAction, child: Text(actionLabel!)),
          ],
        ],
      ),
    );
  }
}
