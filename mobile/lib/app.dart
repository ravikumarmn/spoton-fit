import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import 'core/providers.dart';
import 'router.dart';
import 'ui/theme.dart';

class SpotOnApp extends ConsumerWidget {
  const SpotOnApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'SpotOn',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(AppPalette.light),
      darkTheme: buildTheme(AppPalette.dark),
      themeMode: ref.watch(appearanceProvider),
      // Switch at once: screens read AppColors directly, so a cross-fade would mix palettes.
      themeAnimationDuration: Duration.zero,
      routerConfig: ref.watch(routerProvider),
      builder: (context, child) {
        final palette = Theme.of(context).brightness == Brightness.dark
            ? AppPalette.dark
            : AppPalette.light;
        AppColors.use(palette);
        // A new key rebuilds every screen (including const widgets) in the new colours.
        return KeyedSubtree(
          key: ValueKey(palette.brightness),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
