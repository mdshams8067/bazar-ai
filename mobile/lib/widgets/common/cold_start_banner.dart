import 'dart:async';
import 'package:flutter/material.dart';
import '../../services/health_service.dart';
import '../../theme/app_colors.dart';

class ColdStartBanner extends StatefulWidget {
  const ColdStartBanner({super.key});

  @override
  State<ColdStartBanner> createState() => _ColdStartBannerState();
}

class _ColdStartBannerState extends State<ColdStartBanner> {
  final _health = HealthService();
  bool _waking = false;
  bool _healthy = false;

  @override
  void initState() {
    super.initState();
    _check(first: true);
  }

  Future<void> _check({bool first = false}) async {
    final pingTimeout = Duration(seconds: first ? 3 : 6);
    final ok = await _health.ping(timeout: pingTimeout);
    if (!mounted) return;
    if (ok) {
      setState(() {
        _healthy = true;
        _waking = false;
      });
      return;
    }
    setState(() => _waking = true);
    Timer(const Duration(seconds: 3), () => _check());
  }

  @override
  Widget build(BuildContext context) {
    if (_healthy || !_waking) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: AppColors.accentBlueTint,
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
      child: const Text(
        'Waking up the server — first load can take up to a minute on the free tier. Hang tight…',
        style: TextStyle(color: AppColors.accentBlue, fontSize: 12),
        textAlign: TextAlign.center,
      ),
    );
  }
}
