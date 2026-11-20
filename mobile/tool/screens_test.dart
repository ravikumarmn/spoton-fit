// Renders the main screens to PNG for design review (not part of `flutter test`).
//
//   flutter test tool/screens_test.dart --update-goldens
//
// Writes build/screens/<name>_<light|dark>.png at 390 x 844 dp (iPhone 14 / Pixel 7 size),
// with the real Inter and Material Symbols fonts, from the API fixtures in test/fixtures.
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:spoton/app.dart';
import 'package:spoton/core/api/spoton_api.dart';
import 'package:spoton/core/providers.dart';
import 'package:spoton/features/log/log_state.dart';

import '../test/support.dart';

Future<void> _loadFont(String family, Future<ByteData> bytes) async {
  await (FontLoader(family)..addFont(bytes)).load();
}

Future<ByteData> _file(String path) async =>
    ByteData.sublistView(await File(path).readAsBytes());

void main() {
  setUpAll(() async {
    await _loadFont('Inter', rootBundle.load('assets/fonts/Inter.ttf'));
    final flutterRoot =
        Platform.environment['FLUTTER_ROOT'] ??
        '${Platform.environment['HOME']}/development/flutter';
    await _loadFont(
      'MaterialIcons',
      _file(
        '$flutterRoot/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf',
      ),
    );
    for (final f in Directory(
      '${Directory.current.path}/build/symbols_fonts',
    ).listSync().whereType<File>()) {
      final name = f.uri.pathSegments.last.split('.').first;
      await _loadFont(name, _file(f.path));
    }
  });

  Future<void> pump(WidgetTester tester, Brightness brightness) async {
    // ignore: invalid_use_of_visible_for_testing_member
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3.0;
    tester.platformDispatcher.platformBrightnessTestValue = brightness;
    addTearDown(() {
      tester.view.reset();
      tester.platformDispatcher.clearAllTestValues();
    });
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          prefsProvider.overrideWithValue(prefs),
          apiProvider.overrideWithValue(FakeApi()),
          pickPhotoProvider.overrideWithValue(
            ({required bool camera}) async => UploadImage(
              name: 'meal.jpg',
              bytes: Uint8List.fromList([1, 2, 3]),
            ),
          ),
        ],
        child: const SpotOnApp(),
      ),
    );
    await settle(tester);
  }

  for (final brightness in Brightness.values) {
    final mode = brightness == Brightness.dark ? 'dark' : 'light';
    Future<void> shot(WidgetTester tester, String name) => expectLater(
      find.byType(SpotOnApp),
      matchesGoldenFile('../build/screens/${name}_$mode.png'),
    );

    testWidgets('today ($mode)', (tester) async {
      await pump(tester, brightness);
      await shot(tester, 'today');
      await tester.drag(
        find.byType(Scrollable).hitTestable().first,
        const Offset(0, -500),
      );
      await settle(tester);
      await shot(tester, 'today_meals');
    });

    testWidgets('review ($mode)', (tester) async {
      await pump(tester, brightness);
      await tester.tap(find.bySemanticsLabel('Log a meal'));
      await settle(tester);
      await tester.tap(find.text('Type'));
      await settle(tester);
      await tester.enterText(
        find.byType(TextField).first,
        '6 boiled eggs and 3 puris',
      );
      await tester.tap(find.text('Analyze'));
      await settle(tester);
      await shot(tester, 'review');
    });

    for (final tab in ['Progress', 'Coach', 'Me']) {
      testWidgets('${tab.toLowerCase()} ($mode)', (tester) async {
        await pump(tester, brightness);
        await tester.tap(find.text(tab).last);
        await settle(tester);
        await shot(tester, tab.toLowerCase());
      });
    }
  }
}

Future<void> settle(WidgetTester tester) async {
  for (var i = 0; i < 40; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}
