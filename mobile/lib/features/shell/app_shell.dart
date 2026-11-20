import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../ui/theme.dart';

/// The bottom bar: Today · Progress · [+ Log] · Coach · Me.
/// The + opens the camera screen from any tab; it is the only floating element.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.shell});
  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
      bottomNavigationBar: _BottomBar(
        index: shell.currentIndex,
        onTab: (i) =>
            shell.goBranch(i, initialLocation: i == shell.currentIndex),
        onAdd: () => context.push('/log'),
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.index,
    required this.onTab,
    required this.onAdd,
  });
  final int index;
  final ValueChanged<int> onTab;
  final VoidCallback onAdd;

  static const _tabs = [
    (Icons.today_outlined, Icons.today, 'Today'),
    (Icons.insights_outlined, Icons.insights, 'Progress'),
    (Icons.forum_outlined, Icons.forum, 'Coach'),
    (Icons.person_outline, Icons.person, 'Me'),
  ];

  @override
  Widget build(BuildContext context) {
    // Labels stop growing at 130% so the bar stays usable at the largest text sizes.
    final media = MediaQuery.of(context);
    final scaler = media.textScaler.clamp(maxScaleFactor: 1.3);
    Widget tab(int branch) {
      final t = _tabs[branch];
      final selected = index == branch;
      return Expanded(
        child: Semantics(
          button: true,
          selected: selected,
          label: t.$3,
          child: ExcludeSemantics(
            child: InkWell(
              onTap: () => onTab(branch),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      selected ? t.$2 : t.$1,
                      size: 24,
                      color: selected ? AppColors.primary : AppColors.text3,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      t.$3,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: selected
                            ? FontWeight.w700
                            : FontWeight.w500,
                        color: selected ? AppColors.primary : AppColors.text3,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    return MediaQuery(
      data: media.copyWith(textScaler: scaler),
      child: Material(
        color: AppColors.surface,
        elevation: 0,
        child: DecoratedBox(
          decoration: BoxDecoration(
            border: Border(top: BorderSide(color: AppColors.outline)),
          ),
          child: SafeArea(
            top: false,
            child: SizedBox(
              height: 64,
              child: Row(
                children: [
                  tab(0),
                  tab(1),
                  Expanded(
                    child: Center(
                      child: Semantics(
                        button: true,
                        label: 'Log a meal',
                        child: ExcludeSemantics(
                          child: Transform.translate(
                            offset: const Offset(0, -10),
                            child: Material(
                              color: AppColors.primary,
                              shape: const CircleBorder(),
                              elevation: 4,
                              shadowColor: const Color(0x2E1C2925),
                              child: InkWell(
                                customBorder: const CircleBorder(),
                                onTap: onAdd,
                                child: SizedBox(
                                  width: 56,
                                  height: 56,
                                  child: Icon(
                                    Icons.add,
                                    color: AppColors.onPrimary,
                                    size: 30,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  tab(2),
                  tab(3),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
