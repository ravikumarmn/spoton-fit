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
  List<(String, Color, Color, double)> pairsFor(AppPalette p) => [
    ('button label on primary', p.onPrimary, p.primary, 4.5),
    ('primary text on surface', p.primary, p.surface, 4.5),
    ('primary text on background', p.primary, p.bg, 4.5),
    ('on-container on container', p.onContainer, p.container, 4.5),
    ('text on background', p.text, p.bg, 4.5),
    ('secondary text on surface', p.text2, p.surface, 4.5),
    ('secondary text on background', p.text2, p.bg, 4.5),
    ('tertiary text on surface', p.text3, p.surface, 4.5),
    ('warning text on warning bg', p.warn, p.warnBg, 4.5),
    ('warning text on surface', p.warn, p.surface, 4.5),
    ('info text on info bg', p.info, p.infoBg, 4.5),
    ('error text on error bg', p.error, p.errorBg, 4.5),
    ('error text on surface', p.error, p.surface, 4.5),
    ('error text on background', p.error, p.bg, 4.5),
    ('text on snackbar', p.surface, p.text, 4.5),
    ('label on surface-2 (segmented)', p.text2, p.surface2, 4.5),
    ('protein bar on track', p.protein, p.track, 3.0),
    ('carbs bar on track', p.carbs, p.track, 3.0),
    ('fat bar on track', p.fat, p.track, 3.0),
    ('water bar on track', p.water, p.track, 3.0),
    ('ring on track', p.primary, p.track, 3.0),
    ('over-target ring on track', p.amber, p.track, 3.0),
    ('input border on surface', p.input, p.surface, 3.0),
  ];

  for (final (mode, palette) in [
    ('light', AppPalette.light),
    ('dark', AppPalette.dark),
  ]) {
    for (final (name, fg, bg, min) in pairsFor(palette)) {
      test('contrast ($mode): $name >= $min:1', () {
        expect(
          contrast(fg, bg),
          greaterThanOrEqualTo(min),
          reason: '${contrast(fg, bg).toStringAsFixed(2)}:1',
        );
      });
    }
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
    final t = buildTheme(AppPalette.light);
    expect(t.textTheme.bodyLarge!.fontFamily, 'Inter');
    expect(t.colorScheme.primary, AppPalette.light.primary);
    final d = buildTheme(AppPalette.dark);
    expect(d.brightness, Brightness.dark);
    expect(d.scaffoldBackgroundColor, AppPalette.dark.bg);
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
