import 'package:material_ui/material_ui.dart';

/// SpotOn design tokens (docs/MOBILE_PLAN.md). Light theme only for the first release.
/// Every text/background pair here is checked against WCAG AA in test/theme_test.dart.
abstract final class AppColors {
  static const primary = Color(0xFF2B7A68);
  static const onPrimary = Color(0xFFFFFFFF);
  static const container = Color(0xFFD8EFE8);
  static const onContainer = Color(0xFF0F3D33);
  static const bg = Color(0xFFF6F7F5);
  static const surface = Color(0xFFFFFFFF);
  static const surface2 = Color(0xFFEEF2F0);
  static const track = Color(0xFFE7ECEA);
  static const text = Color(0xFF1C2925);
  static const text2 = Color(0xFF55635E);
  static const text3 = Color(0xFF6B7873);
  static const outline = Color(0xFFD3DBD7);
  static const input = Color(0xFF87948F);
  static const protein = Color(0xFF3672A3);
  static const carbs = Color(0xFFB07A1E);
  static const fat = Color(0xFF82619F);
  static const water = Color(0xFF2F86BF);
  static const warn = Color(0xFF8A5A00);
  static const warnBg = Color(0xFFFFF4DC);
  static const amber = Color(0xFFB7791F);
  static const info = Color(0xFF245F94);
  static const infoBg = Color(0xFFE8F1FA);
  static const error = Color(0xFFA3271F);
  static const errorBg = Color(0xFFFCECEA);
}

abstract final class AppSpace {
  static const double gutter = 16;
  static const double gap = 12;
  static const double radiusCard = 16;
  static const double radiusButton = 12;
  static const double radiusSheet = 24;
  static const double minTap = 48;
}

TextStyle _t(
  double size,
  double lineHeight,
  int weight, {
  Color color = AppColors.text,
  bool tabular = false,
}) {
  return TextStyle(
    fontFamily: 'Inter',
    fontSize: size,
    height: lineHeight / size,
    fontWeight: FontWeight.values[(weight ~/ 100) - 1],
    fontVariations: [FontVariation('wght', weight.toDouble())],
    fontFeatures: tabular ? const [FontFeature.tabularFigures()] : null,
    color: color,
  );
}

/// Type scale: sizes scale with the phone's text-size setting (never fixed).
abstract final class AppText {
  static final hero = _t(
    40,
    44,
    700,
    tabular: true,
  ).copyWith(letterSpacing: -0.8);
  static final title = _t(24, 32, 700);
  static final section = _t(17, 24, 600);
  static final body = _t(16, 24, 400);
  static final label = _t(14, 20, 500, tabular: true);
  static final labelBold = _t(14, 20, 600, tabular: true);
  static final caption = _t(12, 16, 400, color: AppColors.text2);
  static final number = _t(16, 24, 600, tabular: true);
}

ThemeData buildTheme() {
  const scheme = ColorScheme.light(
    primary: AppColors.primary,
    onPrimary: AppColors.onPrimary,
    primaryContainer: AppColors.container,
    onPrimaryContainer: AppColors.onContainer,
    secondary: AppColors.primary,
    onSecondary: AppColors.onPrimary,
    surface: AppColors.surface,
    onSurface: AppColors.text,
    onSurfaceVariant: AppColors.text2,
    surfaceContainerHighest: AppColors.surface2,
    outline: AppColors.input,
    outlineVariant: AppColors.outline,
    error: AppColors.error,
    onError: AppColors.onPrimary,
    errorContainer: AppColors.errorBg,
    onErrorContainer: AppColors.error,
  );
  final shapeButton = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(AppSpace.radiusButton),
  );
  OutlineInputBorder border(Color c, [double w = 1]) => OutlineInputBorder(
    borderRadius: BorderRadius.circular(AppSpace.radiusButton),
    borderSide: BorderSide(color: c, width: w),
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.bg,
    fontFamily: 'Inter',
    splashFactory: InkRipple.splashFactory,
    textTheme: TextTheme(
      displayLarge: AppText.hero,
      headlineSmall: AppText.title,
      titleLarge: AppText.title,
      titleMedium: AppText.section,
      bodyLarge: AppText.body,
      bodyMedium: _t(14, 20, 400),
      bodySmall: AppText.caption,
      labelLarge: _t(14, 20, 600),
      labelMedium: _t(12, 16, 500),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: AppColors.bg,
      foregroundColor: AppColors.text,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: AppText.section,
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpace.radiusCard),
        side: const BorderSide(color: AppColors.outline),
      ),
    ),
    dividerTheme: const DividerThemeData(
      color: AppColors.outline,
      thickness: 1,
      space: 1,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(AppSpace.minTap),
        shape: shapeButton,
        textStyle: _t(16, 24, 600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(AppSpace.minTap),
        shape: shapeButton,
        foregroundColor: AppColors.primary,
        side: const BorderSide(color: AppColors.outline),
        textStyle: _t(16, 24, 600),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(AppSpace.minTap, AppSpace.minTap),
        foregroundColor: AppColors.primary,
        textStyle: _t(14, 20, 600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: border(AppColors.input),
      enabledBorder: border(AppColors.input),
      focusedBorder: border(AppColors.primary, 2),
      errorBorder: border(AppColors.error),
      focusedErrorBorder: border(AppColors.error, 2),
      labelStyle: const TextStyle(color: AppColors.text2),
      helperStyle: AppText.caption,
      errorStyle: _t(12, 16, 500, color: AppColors.error),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.surface,
      showDragHandle: true,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppSpace.radiusSheet),
        ),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.text,
      contentTextStyle: _t(14, 20, 500, color: AppColors.surface),
      shape: shapeButton,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpace.radiusCard),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        minimumSize: const Size(AppSpace.minTap, AppSpace.minTap),
        backgroundColor: AppColors.surface2,
        foregroundColor: AppColors.text2,
        selectedBackgroundColor: AppColors.surface,
        selectedForegroundColor: AppColors.text,
        side: BorderSide.none,
        textStyle: _t(14, 20, 600),
      ),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.primary,
      linearTrackColor: AppColors.track,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected)
            ? AppColors.onPrimary
            : AppColors.surface,
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected)
            ? AppColors.primary
            : AppColors.input,
      ),
    ),
  );
}
