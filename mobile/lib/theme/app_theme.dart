import 'package:flutter/material.dart';
import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get light {
    final base = ThemeData.light(useMaterial3: true);

    final colorScheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.light,
      primary: AppColors.primary,
      secondary: AppColors.accentBlue,
      error: AppColors.warning,
      surface: AppColors.paper,
    );

    final headingStyle = const TextStyle(
      fontFamily: 'CooperHewitt',
      fontWeight: FontWeight.w700,
      color: AppColors.ink,
    );

    return base.copyWith(
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.paperWarm,
      dividerColor: AppColors.line,
      textTheme: base.textTheme.copyWith(
        headlineLarge: headingStyle.copyWith(fontSize: 32),
        headlineMedium: headingStyle.copyWith(fontSize: 26),
        headlineSmall: headingStyle.copyWith(fontSize: 22),
        titleLarge: headingStyle.copyWith(fontSize: 20),
        titleMedium: headingStyle.copyWith(fontSize: 17),
        labelLarge: headingStyle.copyWith(fontSize: 15),
        bodyLarge: const TextStyle(color: AppColors.ink, fontSize: 16),
        bodyMedium: const TextStyle(color: AppColors.ink, fontSize: 14),
        bodySmall: const TextStyle(color: AppColors.inkMuted, fontSize: 12),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.paper,
        foregroundColor: AppColors.ink,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          fontFamily: 'CooperHewitt',
          fontWeight: FontWeight.w700,
          color: AppColors.ink,
          fontSize: 20,
        ),
      ),
      cardTheme: CardThemeData(
        color: AppColors.paper,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppColors.radiusCard),
          side: const BorderSide(color: AppColors.line),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          textStyle: const TextStyle(fontFamily: 'CooperHewitt', fontWeight: FontWeight.w700),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.radiusButton),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary,
          side: const BorderSide(color: AppColors.line),
          textStyle: const TextStyle(fontFamily: 'CooperHewitt', fontWeight: FontWeight.w700),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.radiusButton),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: AppColors.primary,
          textStyle: const TextStyle(fontFamily: 'CooperHewitt', fontWeight: FontWeight.w700),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.paper,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppColors.radiusButton),
          borderSide: const BorderSide(color: AppColors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppColors.radiusButton),
          borderSide: const BorderSide(color: AppColors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppColors.radiusButton),
          borderSide: const BorderSide(color: AppColors.accentBlue, width: 2),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        backgroundColor: AppColors.primaryLight,
        labelStyle: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppColors.radiusButton),
          side: BorderSide.none,
        ),
      ),
    );
  }
}

/// Changa One is only ever applied explicitly (chat prose, hero copy,
/// empty states) — never as a theme-wide default, and never below 16px
/// per the web app's own rule (it's a heavy display face).
const proseTextStyle = TextStyle(
  fontFamily: 'ChangaOne',
  fontSize: 16,
  color: AppColors.ink,
  height: 1.4,
);
