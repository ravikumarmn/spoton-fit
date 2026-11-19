import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'meal_actions.dart';
import 'quick_sheets.dart';

class TodayScreen extends ConsumerStatefulWidget {
  const TodayScreen({super.key});
  @override
  ConsumerState<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends ConsumerState<TodayScreen> {
  /// Meals swiped away; hidden at once so the list stays in step with the Dismissible.
  final _hidden = <String>{};

  Future<void> _refresh() async {
    ref.read(dataVersion.notifier).bump();
    await ref.read(todayProvider.future);
  }

  @override
  Widget build(BuildContext context) {
    final today = ref.watch(todayProvider);
    final day = ref.watch(selectedDayProvider);
    final viewingToday = day == null;
    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        onRefresh: _refresh,
        child: today.when(
          skipLoadingOnRefresh: true,
          loading: () => ListView(
            children: const [
              SizedBox(height: 240),
              Center(child: CircularProgressIndicator()),
            ],
          ),
          error: (e, _) => ListView(
            children: [
              SizedBox(
                height: 160,
                child: ErrorView(error: e, onRetry: _refresh),
              ),
            ],
          ),
          data: (t) => _Body(
            data: t,
            viewingToday: viewingToday,
            hidden: _hidden,
            onHide: (id) => setState(() => _hidden.add(id)),
          ),
        ),
      ),
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({
    required this.data,
    required this.viewingToday,
    required this.hidden,
    required this.onHide,
  });
  final Today data;
  final bool viewingToday;
  final Set<String> hidden;
  final ValueChanged<String> onHide;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = data.targets;
    final left = data.leftKcal;
    final over = left < 0;
    final review = viewingToday ? ref.watch(weeklyReviewProvider).value : null;
    final meals = (ref.watch(mealsProvider).value ?? const <Meal>[])
        .where((m) => !hidden.contains(m.id))
        .toList();

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        _Header(day: data.day),
        const SizedBox(height: 12),
        if (review != null && review.pendingDecision) ...[
          AppCard(
            color: AppColors.container,
            onTap: () => context.go('/progress'),
            child: Row(
              children: [
                const Icon(
                  Icons.event_available_outlined,
                  color: AppColors.onContainer,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Your weekly review is ready',
                        style: AppText.labelBold.copyWith(
                          color: AppColors.onContainer,
                        ),
                      ),
                      Text(
                        review.review!.proposal!.text,
                        style: AppText.caption.copyWith(
                          color: AppColors.onContainer,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: AppColors.onContainer),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        for (final n in data.nudges) ...[
          InfoBanner(n, kind: BannerKind.soft, icon: Icons.rule),
          const SizedBox(height: 12),
        ],
        AppCard(
          child: Row(
            children: [
              Stack(
                alignment: Alignment.center,
                children: [
                  CalorieRing(
                    eaten: data.eaten.kcal,
                    target: t.kcal.toDouble(),
                  ),
                  ExcludeSemantics(
                    child: Icon(
                      over
                          ? Icons.warning_amber_rounded
                          : Icons.local_fire_department_outlined,
                      color: over ? AppColors.amber : AppColors.primary,
                      size: 28,
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Semantics(
                  label: over
                      ? '${fmtInt(-left)} kilocalories over your target of ${fmtInt(t.kcal)}'
                      : '${fmtInt(left)} kilocalories left. ${fmtInt(t.kcal)} target minus ${fmtInt(data.eaten.kcal)} eaten',
                  child: ExcludeSemantics(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          over ? 'Calories over' : 'Calories left',
                          style: AppText.caption,
                        ),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Text(
                            fmtInt(over ? -left : left),
                            style: AppText.hero.copyWith(
                              color: over ? AppColors.warn : AppColors.text,
                            ),
                          ),
                        ),
                        Text(
                          '${fmtInt(t.kcal)} target − ${fmtInt(data.eaten.kcal)} eaten',
                          style: AppText.caption,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        AppCard(
          child: Column(
            children: [
              MacroBar(
                label: 'Protein',
                value: data.eaten.protein,
                target: t.proteinG.toDouble(),
                unit: 'g',
                color: AppColors.protein,
                showLeft: true,
              ),
              const SizedBox(height: 14),
              MacroBar(
                label: 'Carbs',
                value: data.eaten.carbs,
                target: t.carbsG.toDouble(),
                unit: 'g',
                color: AppColors.carbs,
              ),
              const SizedBox(height: 14),
              MacroBar(
                label: 'Fat',
                value: data.eaten.fat,
                target: t.fatG.toDouble(),
                unit: 'g',
                color: AppColors.fat,
              ),
            ],
          ),
        ),
        // Shown on past days too: each one saves to the day being viewed.
        ...[
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              AppChip(
                label: '+250 ml water',
                icon: Icons.water_drop_outlined,
                onTap: () async {
                  await ref
                      .read(apiProvider)
                      .addWater(250, day: ref.read(selectedDayProvider));
                  ref.read(dataVersion.notifier).bump();
                  if (context.mounted) {
                    showToast(context, 'Added 250 ml of water');
                  }
                },
              ),
              AppChip(
                label: 'More water',
                onTap: () => showWaterSheet(context),
              ),
              AppChip(
                label: 'Steps',
                icon: Icons.directions_walk,
                onTap: () => showStepsSheet(context, data.steps),
              ),
              AppChip(
                label: 'Weight',
                icon: Icons.monitor_weight_outlined,
                onTap: () => showWeightSheet(context),
              ),
              AppChip(
                label: 'Workout',
                icon: Icons.fitness_center,
                onTap: () => showWorkoutSheet(context),
              ),
            ],
          ),
        ],
        const SizedBox(height: 8),
        AppCard(
          child: Column(
            children: [
              MacroBar(
                label: 'Water',
                value: data.waterMl.toDouble(),
                target: t.waterMl.toDouble(),
                unit: 'ml',
                color: AppColors.water,
              ),
              const SizedBox(height: 14),
              MacroBar(
                label: 'Steps',
                value: data.steps.toDouble(),
                target: t.steps.toDouble(),
                unit: '',
                color: AppColors.primary,
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Burned so far: about ${fmtInt(data.burnedKcal)} kcal (an estimate; not added to your budget)',
                  style: AppText.caption,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        const SectionTitle('Meals'),
        const SizedBox(height: 8),
        if (meals.isEmpty)
          const AppCard(
            child: EmptyState(
              icon: Icons.restaurant_outlined,
              message: 'Nothing logged yet. Tap + to add a meal.',
            ),
          )
        else
          for (final m in meals) ...[
            _MealCard(meal: m, onHide: onHide),
            const SizedBox(height: 8),
          ],
      ],
    );
  }
}

class _Header extends ConsumerWidget {
  const _Header({required this.day});
  final DateTime day;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now();
    final isToday = ref.watch(selectedDayProvider) == null;
    void shift(int days) {
      final next = DateTime(
        day.year,
        day.month,
        day.day,
      ).add(Duration(days: days));
      final todayDate = DateTime(now.year, now.month, now.day);
      ref
          .read(selectedDayProvider.notifier)
          .set(next.isBefore(todayDate) ? next : null);
    }

    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                header: true,
                child: Text(dayTitle(day, now), style: AppText.title),
              ),
              Text(longDate(day), style: AppText.caption),
            ],
          ),
        ),
        IconButton(
          tooltip: 'Previous day',
          onPressed: () => shift(-1),
          icon: const Icon(Icons.chevron_left),
        ),
        IconButton(
          tooltip: 'Next day',
          onPressed: isToday ? null : () => shift(1),
          icon: const Icon(Icons.chevron_right),
        ),
      ],
    );
  }
}

class _MealCard extends ConsumerWidget {
  const _MealCard({required this.meal, required this.onHide});
  final Meal meal;
  final ValueChanged<String> onHide;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final oily = meal.items.any((i) => i.isOily);
    return Dismissible(
      key: ValueKey(meal.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 24),
        decoration: BoxDecoration(
          color: AppColors.errorBg,
          borderRadius: BorderRadius.circular(AppSpace.radiusCard),
        ),
        child: const Icon(Icons.delete_outline, color: AppColors.error),
      ),
      onDismissed: (_) {
        onHide(meal.id);
        deleteMealWithUndo(context, ref, meal);
      },
      child: AppCard(
        padding: const EdgeInsets.fromLTRB(16, 12, 4, 12),
        onTap: () => showMealActions(context, ref, meal),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          '${slotLabel(meal.slot)} · ${clock(meal.eatenAt.toLocal())}',
                          style: AppText.labelBold,
                        ),
                      ),
                      if (meal.isFavourite) ...[
                        const SizedBox(width: 6),
                        const Icon(
                          Icons.star,
                          size: 16,
                          color: AppColors.amber,
                          semanticLabel: 'Favourite',
                        ),
                      ],
                      if (oily) ...[
                        const SizedBox(width: 6),
                        Text(
                          'Oily',
                          style: AppText.caption.copyWith(
                            color: AppColors.warn,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    meal.summary,
                    style: AppText.caption,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(fmtInt(meal.totals.kcal), style: AppText.number),
            Text(' kcal', style: AppText.caption),
            IconButton(
              tooltip: 'Meal options',
              icon: const Icon(Icons.more_vert),
              onPressed: () => showMealActions(context, ref, meal),
            ),
          ],
        ),
      ),
    );
  }
}
