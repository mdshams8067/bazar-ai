import 'package:flutter/material.dart';
import '../../theme/app_colors.dart';

class _HowItWorksStep {
  final String icon;
  final String title;
  final String body;

  const _HowItWorksStep({required this.icon, required this.title, required this.body});
}

// Mirrors frontend/src/pages/HomePage.tsx's HOW_IT_WORKS copy exactly —
// keep both in sync if either changes. "Honest substitutions" was
// reworded there to drop a "brand swap" promise that isn't reliable
// once embedding retrieval became the primary matching path (see
// PROJECT_CONTEXT.md); this list carries that same fix.
const _steps = [
  _HowItWorksStep(icon: '💬', title: 'Tell Bazar Buddy', body: "Say what you're cooking — English, Bangla, or Banglish."),
  _HowItWorksStep(icon: '🧾', title: 'It checks real stock', body: 'Every ingredient is matched against our live catalog, not guessed.'),
  _HowItWorksStep(
    icon: '🔁',
    title: 'Honest substitutions',
    body: 'Out of stock? You get a real substitute, or an honest skip — never a silent guess.',
  ),
  _HowItWorksStep(icon: '🛒', title: 'Cart, filled', body: 'Everything in stock lands straight in your cart, ready to check out.'),
];

/// Shown once, on the app's first launch (see HomeScreen) — a quick
/// orientation to what Bazar Buddy actually does, since a first-time
/// customer has no way to know this is a real-stock-checking assistant
/// rather than a generic chat box until they've already tried it.
class HowItWorksDialog extends StatelessWidget {
  const HowItWorksDialog({super.key});

  @override
  Widget build(BuildContext context) {
    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(AppColors.radiusCard)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('How Bazar Buddy works', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            for (final step in _steps) ...[
              _StepRow(step: step),
              if (step != _steps.last) const SizedBox(height: 14),
            ],
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Got it'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  final _HowItWorksStep step;

  const _StepRow({required this.step});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(step.icon, style: const TextStyle(fontSize: 22)),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(step.title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 2),
              Text(step.body, style: const TextStyle(color: AppColors.inkMuted, fontSize: 13, height: 1.35)),
            ],
          ),
        ),
      ],
    );
  }
}
