import 'package:flutter/material.dart';

/// Mirrors frontend/src/index.css's `@theme` block exactly — do not
/// substitute Material defaults here, the sharp radii and this exact
/// palette are what distinguishes this app from a generic Flutter look.
class AppColors {
  AppColors._();

  static const primary = Color(0xFF1F5C3F);
  static const primaryDark = Color(0xFF143D2A);
  static const primaryLight = Color(0xFFEAF4EC);
  static const accentBlue = Color(0xFF2450A8);
  static const accentBlueTint = Color(0xFFE7EEFB);
  static const ink = Color(0xFF14161A);
  static const inkMuted = Color(0xFF4A4D52);
  static const paper = Color(0xFFFFFFFF);
  static const paperWarm = Color(0xFFF7F6F1);
  static const warning = Color(0xFFC7622A);
  static const warningTint = Color(0xFFF9ECE4);
  static const line = Color(0xFFE3E1DA);

  static const radiusCard = 6.0;
  static const radiusButton = 2.0;
}
