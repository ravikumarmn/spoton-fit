import 'package:material_ui/material_ui.dart';

/// SpotOn design tokens (docs/MOBILE_PLAN.md): a light and a dark palette.
/// Every text/background pair is checked against WCAG AA, in both palettes, in test/theme_test.dart.
class AppPalette {
  const AppPalette._({
    required this.brightness,
    required this.primary,
    required this.onPrimary,
    required this.container,
    required this.onContainer,
    required this.bg,
    required this.surface,
    required this.surface2,
    required this.track,
    required this.text,
    required this.text2,
    required this.text3,
    required this.outline,
    required this.input,
    required this.protein,
    required this.carbs,
    required this.fat,
    required this.water,
    required this.warn,
    required this.warnBg,
    required this.amber,
    required this.info,
    required this.infoBg,
    required this.error,
    required this.errorBg,
    required this.shadow,
  });

  final Brightness brightness;
  final Color primary;
  final Color onPrimary;
  final Color container;
  final Color onContainer;
  final Color bg;
  final Color surface;
  final Color surface2;
  final Color track;
  final Color text;
  final Color text2;
  final Color text3;
  final Color outline;
  final Color input;
  final Color protein;
  final Color carbs;
  final Color fat;
  final Color water;
  final Color warn;
  final Color warnBg;
  final Color amber;
  final Color info;
  final Color infoBg;
  final Color error;
  final Color errorBg;
  final Color shadow;

  static const light = AppPalette._(
    brightness: Brightness.light,
    primary: Color(0xFF2B7A68),
    onPrimary: Color(0xFFFFFFFF),
    container: Color(0xFFD8EFE8),
    onContainer: Color(0xFF0F3D33),
    bg: Color(0xFFF6F7F5),
    surface: Color(0xFFFFFFFF),
    surface2: Color(0xFFEEF2F0),
    track: Color(0xFFE7ECEA),
    text: Color(0xFF1C2925),
    text2: Color(0xFF55635E),
    text3: Color(0xFF6B7873),
    outline: Color(0xFFD3DBD7),
    input: Color(0xFF87948F),
    protein: Color(0xFF3672A3),
    carbs: Color(0xFFB07A1E),
    fat: Color(0xFF82619F),
    water: Color(0xFF2F86BF),
    warn: Color(0xFF8A5A00),
    warnBg: Color(0xFFFFF4DC),
    amber: Color(0xFFB7791F),
    info: Color(0xFF245F94),
    infoBg: Color(0xFFE8F1FA),
    error: Color(0xFFA3271F),
    errorBg: Color(0xFFFCECEA),
    shadow: Color(0x331C2925),
  );

  static const dark = AppPalette._(
    brightness: Brightness.dark,
    primary: Color(0xFF5FC0A6),
    onPrimary: Color(0xFF06241C),
    container: Color(0xFF1E3B33),
    onContainer: Color(0xFFBFEBDD),
    bg: Color(0xFF0F1513),
    surface: Color(0xFF18201D),
    surface2: Color(0xFF222B28),
    track: Color(0xFF2C3632),
    text: Color(0xFFE6ECE9),
    text2: Color(0xFFAAB7B2),
    text3: Color(0xFF95A39E),
    outline: Color(0xFF34413C),
    input: Color(0xFF7F8E88),
    protein: Color(0xFF74AEE0),
    carbs: Color(0xFFD9A441),
    fat: Color(0xFFB79AD8),
    water: Color(0xFF62B6EA),
    warn: Color(0xFFF2C063),
    warnBg: Color(0xFF3A2E12),
    amber: Color(0xFFE0A33C),
    info: Color(0xFF93C4F2),
    infoBg: Color(0xFF13283B),
    error: Color(0xFFF4877E),
    errorBg: Color(0xFF3D1815),
    shadow: Color(0x00000000),
  );
}

/// The active palette's colours. The app sets it from the chosen appearance (Me › Appearance)
/// before building screens, and rebuilds every screen when it changes (see app.dart).
abstract final class AppColors {
  static AppPalette _p = AppPalette.light;
  static AppPalette get current => _p;
  static void use(AppPalette p) => _p = p;

  static Color get primary => _p.primary;
  static Color get onPrimary => _p.onPrimary;
  static Color get container => _p.container;
  static Color get onContainer => _p.onContainer;
  static Color get bg => _p.bg;
  static Color get surface => _p.surface;
  static Color get surface2 => _p.surface2;
  static Color get track => _p.track;
  static Color get text => _p.text;
  static Color get text2 => _p.text2;
  static Color get text3 => _p.text3;
  static Color get outline => _p.outline;
  static Color get input => _p.input;
  static Color get protein => _p.protein;
  static Color get carbs => _p.carbs;
  static Color get fat => _p.fat;
  static Color get water => _p.water;
  static Color get warn => _p.warn;
  static Color get warnBg => _p.warnBg;
  static Color get amber => _p.amber;
  static Color get info => _p.info;
  static Color get infoBg => _p.infoBg;
  static Color get error => _p.error;
  static Color get errorBg => _p.errorBg;
  static Color get shadow => _p.shadow;
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
  required Color color,
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
class AppTextStyles {
  AppTextStyles(AppPalette p)
    : hero = _t(
        40,
        44,
        700,
        color: p.text,
        tabular: true,
      ).copyWith(letterSpacing: -0.8),
      title = _t(24, 32, 700, color: p.text),
      section = _t(17, 24, 600, color: p.text),
      body = _t(16, 24, 400, color: p.text),
      label = _t(14, 20, 500, color: p.text, tabular: true),
      labelBold = _t(14, 20, 600, color: p.text, tabular: true),
      caption = _t(12, 16, 400, color: p.text2),
      number = _t(16, 24, 600, color: p.text, tabular: true);

  final TextStyle hero, title, section, body, label, labelBold, caption, number;
}

/// Text styles for the active palette.
abstract final class AppText {
  static final _cache = <Brightness, AppTextStyles>{};
  static AppTextStyles get _s => _cache.putIfAbsent(
    AppColors.current.brightness,
    () => AppTextStyles(AppColors.current),
  );
  static TextStyle get hero => _s.hero;
  static TextStyle get title => _s.title;
  static TextStyle get section => _s.section;
  static TextStyle get body => _s.body;
  static TextStyle get label => _s.label;
  static TextStyle get labelBold => _s.labelBold;
  static TextStyle get caption => _s.caption;
  static TextStyle get number => _s.number;
}

ThemeData buildTheme(AppPalette p) {
  final text = AppTextStyles(p);
  final scheme = ColorScheme(
    brightness: p.brightness,
    primary: p.primary,
    onPrimary: p.onPrimary,
    primaryContainer: p.container,
    onPrimaryContainer: p.onContainer,
    secondary: p.primary,
    onSecondary: p.onPrimary,
    surface: p.surface,
    onSurface: p.text,
    onSurfaceVariant: p.text2,
    surfaceContainerHighest: p.surface2,
    outline: p.input,
    outlineVariant: p.outline,
    error: p.error,
    onError: p.onPrimary,
    errorContainer: p.errorBg,
    onErrorContainer: p.error,
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
    scaffoldBackgroundColor: p.bg,
    fontFamily: 'Inter',
    splashFactory: InkRipple.splashFactory,
    textTheme: TextTheme(
      displayLarge: text.hero,
      headlineSmall: text.title,
      titleLarge: text.title,
      titleMedium: text.section,
      bodyLarge: text.body,
      bodyMedium: _t(14, 20, 400, color: p.text),
      bodySmall: text.caption,
      labelLarge: _t(14, 20, 600, color: p.text),
      labelMedium: _t(12, 16, 500, color: p.text),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: p.bg,
      foregroundColor: p.text,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: text.section,
    ),
    cardTheme: CardThemeData(
      color: p.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpace.radiusCard),
        side: BorderSide(color: p.outline),
      ),
    ),
    dividerTheme: DividerThemeData(color: p.outline, thickness: 1, space: 1),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(AppSpace.minTap),
        shape: shapeButton,
        textStyle: _t(16, 24, 600, color: p.text),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(AppSpace.minTap),
        shape: shapeButton,
        foregroundColor: p.primary,
        side: BorderSide(color: p.outline),
        textStyle: _t(16, 24, 600, color: p.text),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(AppSpace.minTap, AppSpace.minTap),
        foregroundColor: p.primary,
        textStyle: _t(14, 20, 600, color: p.text),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: p.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      border: border(p.input),
      enabledBorder: border(p.input),
      focusedBorder: border(p.primary, 2),
      errorBorder: border(p.error),
      focusedErrorBorder: border(p.error, 2),
      labelStyle: TextStyle(color: p.text2),
      helperStyle: text.caption,
      errorStyle: _t(12, 16, 500, color: p.error),
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: p.surface,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppSpace.radiusSheet),
        ),
      ),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: p.text,
      contentTextStyle: _t(14, 20, 500, color: p.surface),
      shape: shapeButton,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: p.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpace.radiusCard),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: SegmentedButton.styleFrom(
        minimumSize: const Size(AppSpace.minTap, AppSpace.minTap),
        backgroundColor: p.surface2,
        foregroundColor: p.text2,
        selectedBackgroundColor: p.surface,
        selectedForegroundColor: p.text,
        side: BorderSide.none,
        textStyle: _t(14, 20, 600, color: p.text),
      ),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: p.primary,
      linearTrackColor: p.track,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected) ? p.onPrimary : p.surface,
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.selected) ? p.primary : p.input,
      ),
    ),
  );
}
