import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

enum BadgeTone { primary, blue, warning, muted }

class BadgePill extends StatelessWidget {
  final String label;
  final BadgeTone tone;

  const BadgePill({super.key, required this.label, this.tone = BadgeTone.muted});

  (Color, Color) _colors() => switch (tone) {
        BadgeTone.primary => (AppColors.primaryLight, AppColors.primary),
        BadgeTone.blue => (AppColors.accentBlueTint, AppColors.accentBlue),
        BadgeTone.warning => (AppColors.warningTint, AppColors.warning),
        BadgeTone.muted => (AppColors.line, AppColors.inkMuted),
      };

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = _colors();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(AppColors.radiusButton)),
      child: Text(label, style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }
}
