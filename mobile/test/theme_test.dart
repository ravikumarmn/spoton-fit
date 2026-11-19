import 'dart:math' as math;

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:spoton/ui/theme.dart';

double _lin(double c) =>
    c <= 0.04045 ? c / 12.92 : math.pow((c + 0.055) / 1.055, 2.4).toDouble();

/// WCAG 2.2 relative luminance and contrast ratio.
double luminance(Color c) =>
    0.2126 * _lin(c.r) + 0.7152 * _lin(c.g) + 0.0722 * _lin(c.b);

double contrast(Color a, Color b) {
  final la = luminance(a), lb = luminance(b);
  final hi = math.max(la, lb), lo = math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}

void main() {
  // (name, foreground, background, minimum ratio): 4.5 for text, 3.0 for graphics.
  final pairs = <(String, Color, Color, double)>[
    ('button label on primary', AppColors.onPrimary, AppColors.primary, 4.5),
    ('primary text on surface', AppColors.primary, AppColors.surface, 4.5),
    ('primary text on background', AppColors.primary, AppColors.bg, 4.5),
    (
      'on-container on container',
      AppColors.onContainer,
      AppColors.container,
      4.5,
    ),
    ('text on background', AppColors.text, AppColors.bg, 4.5),
    ('secondary text on surface', AppColors.text2, AppColors.surface, 4.5),
    ('secondary text on background', AppColors.text2, AppColors.bg, 4.5),
    ('tertiary text on surface', AppColors.text3, AppColors.surface, 4.5),
    ('warning text on warning bg', AppColors.warn, AppColors.warnBg, 4.5),
    ('warning text on surface', AppColors.warn, AppColors.surface, 4.5),
    ('info text on info bg', AppColors.info, AppColors.infoBg, 4.5),
    ('error text on error bg', AppColors.error, AppColors.errorBg, 4.5),
    ('error text on surface', AppColors.error, AppColors.surface, 4.5),
    ('error text on background', AppColors.error, AppColors.bg, 4.5),
    ('text on snackbar', AppColors.surface, AppColors.text, 4.5),
    (
      'label on surface-2 (segmented)',
      AppColors.text2,
      AppColors.surface2,
      4.5,
    ),
    ('protein bar on track', AppColors.protein, AppColors.track, 3.0),
    ('carbs bar on track', AppColors.carbs, AppColors.track, 3.0),
    ('fat bar on track', AppColors.fat, AppColors.track, 3.0),
    ('water bar on track', AppColors.water, AppColors.track, 3.0),
    ('ring on track', AppColors.primary, AppColors.track, 3.0),
    ('over-target ring on track', AppColors.amber, AppColors.track, 3.0),
    ('input border on surface', AppColors.input, AppColors.surface, 3.0),
  ];

  for (final (name, fg, bg, min) in pairs) {
    test('contrast: $name >= $min:1', () {
      expect(
        contrast(fg, bg),
        greaterThanOrEqualTo(min),
        reason: '${contrast(fg, bg).toStringAsFixed(2)}:1',
      );
    });
  }

  test('the contrast helper matches known WCAG values', () {
    expect(
      contrast(const Color(0xFF000000), const Color(0xFFFFFFFF)),
      closeTo(21, 0.01),
    );
    expect(
      contrast(const Color(0xFFFFFFFF), const Color(0xFFFFFFFF)),
      closeTo(1, 0.001),
    );
  });

  test('theme uses Inter and 48 dp minimum buttons', () {
    final t = buildTheme();
    expect(t.textTheme.bodyLarge!.fontFamily, 'Inter');
    expect(t.colorScheme.primary, AppColors.primary);
    expect(
      t.filledButtonTheme.style!.minimumSize!.resolve({})!.height,
      AppSpace.minTap,
    );
    expect(
      t.textButtonTheme.style!.minimumSize!.resolve({})!.height,
      AppSpace.minTap,
    );
  });
}
