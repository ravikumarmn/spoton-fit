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
    // Newer servers send meals and the review with Today (one call); `??` only falls back to
    // the separate requests when they're missing, so those providers aren't even watched.
    final review = viewingToday
        ? (data.weeklyReview ?? ref.watch(weeklyReviewProvider).value)
        : null;
    final meals =
        (data.meals ?? ref.watch(mealsProvider).value ?? const <Meal>[])
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
                Icon(
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
                Icon(Icons.chevron_right, color: AppColors.onContainer),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        for (final n in data.nudges) ...[
          InfoBanner(n, kind: BannerKind.soft, icon: Icons.rule),
          const SizedBox(height: 12),
        ],
        // The focal point: calories left and protein left, the two numbers that matter.
        AppCard(
          padding: const EdgeInsets.fromLTRB(12, 20, 12, 16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _Goal(
                  title: over ? 'Calories over' : 'Calories left',
                  amount: over ? -left : left,
                  unit: 'kcal',
                  detail:
                      '${fmtInt(t.kcal)} − ${fmtInt(data.eaten.kcal)} eaten',
                  eaten: data.eaten.kcal,
                  target: t.kcal.toDouble(),
                  color: AppColors.primary,
                  over: over,
                  semantics: over
                      ? '${fmtInt(-left)} kilocalories over your target of ${fmtInt(t.kcal)}'
                      : '${fmtInt(left)} kilocalories left. ${fmtInt(t.kcal)} target minus ${fmtInt(data.eaten.kcal)} eaten',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _Goal(
                  title: data.leftProteinG < 0
                      ? 'Protein over'
                      : 'Protein left',
                  amount: data.leftProteinG.abs(),
                  unit: 'g',
                  detail:
                      '${fmtInt(t.proteinG)} − ${fmtInt(data.eaten.protein)} eaten',
                  eaten: data.eaten.protein,
                  target: t.proteinG.toDouble(),
                  color: AppColors.protein,
                  // More protein than the target is fine: never shown as a warning.
                  over: false,
                  semantics:
                      '${fmtInt(data.leftProteinG.abs())} grams of protein ${data.leftProteinG < 0 ? 'over' : 'left'}. '
                      '${fmtInt(t.proteinG)} target minus ${fmtInt(data.eaten.protein)} eaten',
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        // Everything else, quieter.
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _StatGrid(
                stats: [
                  _Stat(
                    'Carbs',
                    data.eaten.carbs,
                    t.carbsG.toDouble(),
                    'g',
                    AppColors.carbs,
                  ),
                  _Stat(
                    'Fat',
                    data.eaten.fat,
                    t.fatG.toDouble(),
                    'g',
                    AppColors.fat,
                  ),
                  _Stat(
                    'Water',
                    data.waterMl.toDouble(),
                    t.waterMl.toDouble(),
                    'ml',
                    AppColors.water,
                    overIsFine: true,
                  ),
                  _Stat(
                    'Steps',
                    data.steps.toDouble(),
                    t.steps.toDouble(),
                    '',
                    AppColors.primary,
                    overIsFine: true,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                'Burned so far: about ${fmtInt(data.burnedKcal)} kcal (an estimate; not added to your budget)',
                style: AppText.caption,
              ),
            ],
          ),
        ),
        // Shown on past days too: each one saves to the day being viewed.
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          children: [
            AppChip(
              label: '+250 ml water',
              icon: Icons.water_drop_outlined,
              onTap: () async {
                Motion.tick();
                await ref
                    .read(apiProvider)
                    .addWater(250, day: ref.read(selectedDayProvider));
                ref.read(dataVersion.notifier).bump();
                if (context.mounted) {
                  showToast(context, 'Added 250 ml of water');
                }
              },
            ),
            AppChip(label: 'More water', onTap: () => showWaterSheet(context)),
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
        child: Icon(Icons.delete_outline, color: AppColors.error),
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
                        Icon(
                          Icons.star,
                          size: 16,
                          color: AppColors.amber,
                          semanticLabel: 'Favourite',
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  // "Oily" sits with the foods, so the slot and time keep one line.
                  Text.rich(
                    TextSpan(
                      children: [
                        TextSpan(text: meal.summary),
                        if (oily)
                          TextSpan(
                            text: ' · Oily',
                            style: AppText.caption.copyWith(
                              color: AppColors.warn,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                      ],
                    ),
                    style: AppText.caption,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            // Up to 30% of the screen: at large text sizes "1,032 kcal" wraps instead of
            // pushing off the card, without squeezing the meal name at normal sizes.
            ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.sizeOf(context).width * 0.3,
              ),
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: fmtInt(meal.totals.kcal),
                      style: AppText.number,
                    ),
                    TextSpan(text: ' kcal', style: AppText.caption),
                  ],
                ),
                textAlign: TextAlign.end,
              ),
            ),
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

/// One of the two focal numbers: a ring with the number inside, the label and the sum below.
class _Goal extends StatelessWidget {
  const _Goal({
    required this.title,
    required this.amount,
    required this.unit,
    required this.detail,
    required this.eaten,
    required this.target,
    required this.color,
    required this.over,
    required this.semantics,
  });
  final String title, unit, detail, semantics;
  final double amount, eaten, target;
  final Color color;
  final bool over;

  @override
  Widget build(BuildContext context) => Semantics(
    label: semantics,
    child: ExcludeSemantics(
      child: Column(
        children: [
          CalorieRing(
            eaten: eaten,
            target: target,
            size: 132,
            stroke: 11,
            color: color,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AnimatedNumber(
                  amount,
                  style: AppText.hero.copyWith(
                    fontSize: 34,
                    height: 1.1,
                    color: over ? AppColors.warn : AppColors.text,
                  ),
                ),
                Text(unit, style: AppText.caption),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Text(title, style: AppText.labelBold, textAlign: TextAlign.center),
          Text(detail, style: AppText.caption, textAlign: TextAlign.center),
        ],
      ),
    ),
  );
}

class _Stat {
  const _Stat(
    this.label,
    this.value,
    this.target,
    this.unit,
    this.color, {
    this.overIsFine = false,
  });
  final String label, unit;
  final double value, target;
  final Color color;

  /// Going past the target is good (water, steps), so it is never shown as "over".
  final bool overIsFine;
}

/// Carbs, fat, water and steps as small labelled bars: two columns, one at large text sizes.
class _StatGrid extends StatelessWidget {
  const _StatGrid({required this.stats});
  final List<_Stat> stats;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, c) {
      final scale = MediaQuery.textScalerOf(context).scale(1);
      final columns = scale > 1.3 ? 1 : 2;
      const gap = 16.0;
      final width = (c.maxWidth - gap * (columns - 1)) / columns;
      return Wrap(
        spacing: gap,
        runSpacing: 14,
        children: [
          for (final s in stats) SizedBox(width: width, child: _MiniStat(s)),
        ],
      );
    },
  );
}

class _MiniStat extends StatelessWidget {
  const _MiniStat(this.s);
  final _Stat s;

  @override
  Widget build(BuildContext context) {
    final t = s.target <= 0 ? 1.0 : s.target;
    final over = !s.overIsFine && s.value > t;
    final unit = s.unit.isEmpty ? '' : ' ${s.unit}';
    final detail = over
        ? '${fmtInt(s.value - t)}$unit over'
        : '${fmtInt(s.value)} / ${fmtInt(t)}$unit';
    return Semantics(
      label:
          '${s.label}: ${fmtInt(s.value)} of ${fmtInt(t)}$unit${over ? ', over target' : ''}',
      child: ExcludeSemantics(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.label, style: AppText.caption),
            Text(
              detail,
              style: AppText.labelBold.copyWith(
                color: over ? AppColors.warn : AppColors.text,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: Motion.tween(
                context,
                value: (s.value / t).clamp(0.0, 1.0),
                builder: (v) => LinearProgressIndicator(
                  value: v,
                  minHeight: 5,
                  color: over ? AppColors.amber : s.color,
                  backgroundColor: AppColors.track,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
