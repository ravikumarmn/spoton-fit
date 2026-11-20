import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../log/log_state.dart';

/// Log again, favourite, edit or delete a saved meal.
Future<void> showMealActions(BuildContext context, WidgetRef ref, Meal meal) {
  return showAppSheet<void>(
    context,
    builder: (sheet) => Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '${slotLabel(meal.slot)} · ${clock(meal.eatenAt.toLocal())}',
          style: AppText.title,
        ),
        const SizedBox(height: 4),
        Text(
          '${fmtInt(meal.totals.kcal)} kcal · ${meal.summary}',
          style: AppText.caption,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 8),
        _Action(Symbols.edit_rounded, 'Edit meal', () {
          Navigator.pop(sheet);
          ref
              .read(draftProvider.notifier)
              .startFromItems(
                meal.items,
                slot: meal.slot,
                editingMealId: meal.id,
              );
          context.push('/log/review');
        }),
        _Action(Symbols.replay_rounded, 'Log again now', () async {
          Navigator.pop(sheet);
          await _run(
            context,
            ref,
            () => ref.read(apiProvider).repeatMeal(meal.id),
            done: 'Logged again',
          );
        }),
        _Action(
          Symbols.star_rounded,
          meal.isFavourite ? 'Remove from favourites' : 'Add to favourites',
          () async {
            Navigator.pop(sheet);
            await _run(
              context,
              ref,
              () => ref
                  .read(apiProvider)
                  .setFavourite(meal.id, !meal.isFavourite),
              done: meal.isFavourite
                  ? 'Removed from favourites'
                  : 'Added to favourites',
            );
          },
          fill: meal.isFavourite,
        ),
        _Action(Symbols.delete_rounded, 'Delete meal', () async {
          Navigator.pop(sheet);
          await deleteMealWithUndo(context, ref, meal);
        }, color: AppColors.error),
      ],
    ),
  );
}

Future<void> _run(
  BuildContext context,
  WidgetRef ref,
  Future<Object?> Function() action, {
  required String done,
}) async {
  try {
    await action();
    ref.read(dataVersion.notifier).bump();
    if (context.mounted) showToast(context, done);
  } on ApiException catch (e) {
    if (context.mounted) showToast(context, e.message);
  }
}

/// Deletes right away and offers Undo (which saves the same meal again).
Future<void> deleteMealWithUndo(
  BuildContext context,
  WidgetRef ref,
  Meal meal,
) async {
  final api = ref.read(apiProvider);
  final messenger = ScaffoldMessenger.of(context);
  try {
    await api.deleteMeal(meal.id);
  } on ApiException catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(e.message)));
    return;
  }
  ref.read(dataVersion.notifier).bump();
  messenger.hideCurrentSnackBar();
  messenger.showSnackBar(
    SnackBar(
      content: const Text('Meal deleted'),
      duration: const Duration(seconds: 6),
      action: SnackBarAction(
        label: 'Undo',
        onPressed: () async {
          try {
            await api.saveMeal(
              slot: meal.slot,
              items: meal.items,
              source: const {'photo', 'text', 'repeat'}.contains(meal.source)
                  ? meal.source
                  : 'text',
              idempotencyKey:
                  'undo-${meal.id}-${DateTime.now().microsecondsSinceEpoch}',
              note: meal.note,
              isFavourite: meal.isFavourite,
              eatenAt: meal.eatenAt,
            );
            ref.read(dataVersion.notifier).bump();
          } on ApiException catch (e) {
            messenger.showSnackBar(SnackBar(content: Text(e.message)));
          }
        },
      ),
    ),
  );
}

class _Action extends StatelessWidget {
  const _Action(
    this.icon,
    this.label,
    this.onTap, {
    this.color,
    this.fill = false,
  });
  final IconData icon;
  final bool fill;
  final String label;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) => ListTile(
    minTileHeight: AppSpace.minTap,
    contentPadding: EdgeInsets.zero,
    leading: Icon(icon, color: color ?? AppColors.text2, fill: fill ? 1 : 0),
    title: Text(
      label,
      style: AppText.body.copyWith(color: color ?? AppColors.text),
    ),
    onTap: onTap,
  );
}
