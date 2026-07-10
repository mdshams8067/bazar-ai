import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key});

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator> with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 40,
      height: 20,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: List.generate(3, (i) {
              final t = (_controller.value - i * 0.2) % 1.0;
              final scale = 0.6 + 0.4 * (t < 0.5 ? t * 2 : (1 - t) * 2).clamp(0.0, 1.0);
              return Transform.scale(
                scale: scale,
                child: Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(color: AppColors.inkMuted, shape: BoxShape.circle),
                ),
              );
            }),
          );
        },
      ),
    );
  }
}
