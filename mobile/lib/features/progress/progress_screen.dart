import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../today/quick_sheets.dart';
import 'charts.dart';

class ProgressScreen extends ConsumerStatefulWidget {
  const ProgressScreen({super.key});
  @override
  ConsumerState<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends ConsumerState<ProgressScreen> {
  bool _history = false;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Semantics(
                  header: true,
                  child: Text('Progress', style: AppText.title),
                ),
                const SizedBox(height: 12),
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('Trend')),
                    ButtonSegment(value: true, label: Text('History')),
                  ],
                  selected: {_history},
                  showSelectedIcon: false,
                  onSelectionChanged: (s) => setState(() => _history = s.first),
                ),
              ],
            ),
          ),
          Expanded(child: _history ? const _HistoryView() : const _TrendView()),
        ],
      ),
    );
  }
}

// --- Trend ----------------------------------------------------------------------------------

class _TrendView extends ConsumerWidget {
  const _TrendView();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final progress = ref.watch(progressProvider);
    Future<void> refresh() async {
      ref.read(dataVersion.notifier).bump();
      await ref.read(progressProvider.future);
    }

    return RefreshIndicator(
      onRefresh: refresh,
      child: progress.when(
        skipLoadingOnRefresh: true,
        loading: () => ListView(
          children: const [
            SizedBox(height: 200),
            Center(child: CircularProgressIndicator()),
          ],
        ),
        error: (e, _) => ListView(
          children: [
            SizedBox(
              height: 200,
              child: ErrorView(error: e, onRetry: refresh),
            ),
          ],
        ),
        data: (p) => ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
          children: [
            const _ReviewCard(),
            const SizedBox(height: 12),
            _WeightCard(p: p),
            const SizedBox(height: 12),
            _MaintenanceCard(m: p.maintenance),
            const SizedBox(height: 12),
            _MeasurementsCard(items: p.measurements),
          ],
        ),
      ),
    );
  }
}

class _ReviewCard extends ConsumerStatefulWidget {
  const _ReviewCard();
  @override
  ConsumerState<_ReviewCard> createState() => _ReviewCardState();
}

class _ReviewCardState extends ConsumerState<_ReviewCard> {
  bool _busy = false;

  Future<void> _decide(Review r, {required bool accept}) async {
    setState(() => _busy = true);
    try {
      await ref.read(apiProvider).decideReview(r.id, accept: accept);
      ref.read(dataVersion.notifier).bump();
      if (mounted) {
        showToast(
          context,
          accept ? 'Targets updated' : 'Targets kept as they are',
        );
      }
    } on ApiException catch (e) {
      if (mounted) showToast(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(weeklyReviewProvider);
    return async.when(
      loading: () => const SizedBox.shrink(),
      error: (_, _) => const SizedBox.shrink(),
      data: (w) {
        final r = w.review;
        if (r == null) {
          return AppCard(
            child: Row(
              children: [
                Icon(Icons.event_outlined, color: AppColors.text2),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Your first weekly review arrives on ${longDate(w.nextReviewOn)}.',
                    style: AppText.body,
                  ),
                ),
              ],
            ),
          );
        }
        final trend = r.trendChangeKg == null
            ? ''
            : ' · trend ${signed(r.trendChangeKg!, unit: 'kg')}';
        final p = r.proposal;
        return AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Weekly review · ${shortDate(r.weekStart)}–${shortDate(r.weekEnd)}',
                style: AppText.section,
              ),
              const SizedBox(height: 4),
              Text(
                '${r.daysLogged} of 7 days logged$trend · protein target hit ${r.proteinHitDays} of 7 days'
                '${r.avgKcal == null ? '' : ' · average ${fmtInt(r.avgKcal!)} kcal'}',
                style: AppText.caption,
              ),
              for (final n in r.notes) ...[
                const SizedBox(height: 6),
                Text(n, style: AppText.body),
              ],
              if (r.waistChangeCm != null) ...[
                const SizedBox(height: 6),
                Text(
                  'Waist ${signed(r.waistChangeCm!, unit: 'cm')} this week',
                  style: AppText.body,
                ),
              ],
              if (p != null) ...[
                const SizedBox(height: 12),
                InfoBanner(
                  'Suggested: ${p.text}',
                  icon: Icons.tips_and_updates_outlined,
                  child: Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      p.reason,
                      style: AppText.caption.copyWith(color: AppColors.info),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                if (r.decision != null)
                  Text(
                    r.decision == 'accepted'
                        ? 'You accepted this change.'
                        : 'You kept your targets as they were.',
                    style: AppText.caption,
                  )
                else
                  Row(
                    children: [
                      Expanded(
                        child: SecondaryButton(
                          label: 'Keep as is',
                          onPressed: _busy
                              ? null
                              : () => _decide(r, accept: false),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: PrimaryButton(
                          label: 'Accept',
                          loading: _busy,
                          onPressed: () => _decide(r, accept: true),
                        ),
                      ),
                    ],
                  ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _WeightCard extends StatelessWidget {
  const _WeightCard({required this.p});
  final Progress p;

  @override
  Widget build(BuildContext context) {
    final change = p.trendChange4wKg;
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionTitle(
            'Weight',
            trailing: AppChip(
              label: 'Log weight',
              icon: Icons.add,
              onTap: () => showWeightSheet(context),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              _Metric(
                'Trend weight',
                p.trendKg == null ? '–' : '${fmtNum(p.trendKg!)} kg',
              ),
              _Metric(
                'Last 4 weeks',
                change == null ? '–' : signed(change, unit: 'kg'),
              ),
              if (p.rangeLowKg != null)
                _Metric(
                  'In ${p.rangeWeeks} weeks',
                  '${fmtNum(p.rangeLowKg!)}–${fmtNum(p.rangeHighKg!)} kg',
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (p.series.length >= 2)
            Semantics(
              label: 'Weight chart: dots are weigh-ins, the line is your smoothed trend.',
              child: ExcludeSemantics(child: WeightChart(points: p.series)),
            )
          else
            Text(
              'Log your weight a few times to see your trend.',
              style: AppText.caption,
            ),
          const SizedBox(height: 4),
          Text(
            'The trend smooths out day-to-day water swings. Targets and predictions use it.',
            style: AppText.caption,
          ),
          if (p.predictionMessage != null) ...[
            const SizedBox(height: 12),
            InfoBanner(
              p.predictionMessage!,
              kind: BannerKind.soft,
              icon: Icons.flag_outlined,
            ),
          ] else ...[
            const SizedBox(height: 8),
            Text(
              'Add a goal weight in Me → Edit profile to see when you may reach it.',
              style: AppText.caption,
            ),
          ],
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value);
  final String label, value;
  @override
  Widget build(BuildContext context) => Expanded(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppText.caption),
        Text(value, style: AppText.number),
      ],
    ),
  );
}

class _MaintenanceCard extends StatelessWidget {
  const _MaintenanceCard({required this.m});
  final Maintenance m;

  @override
  Widget build(BuildContext context) => AppCard(
    onTap: () => showAppSheet<void>(
      context,
      builder: (_) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Maintenance calories', style: AppText.title),
          const SizedBox(height: 8),
          Text(
            '${fmtInt(m.kcal)} kcal a day',
            style: AppText.hero.copyWith(fontSize: 28),
          ),
          const SizedBox(height: 8),
          Text(m.explanation, style: AppText.body),
          const SizedBox(height: 8),
          Text(
            'The formula alone would say ${fmtInt(m.formulaKcal)} kcal.',
            style: AppText.caption,
          ),
        ],
      ),
    ),
    child: Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Maintenance', style: AppText.section),
              Text(
                m.active
                    ? 'Learned from your own data'
                    : 'From the formula, for now',
                style: AppText.caption,
              ),
            ],
          ),
        ),
        // Flexible: at large text sizes the number wraps instead of pushing past the card.
        Flexible(
          child: Text(
            '${fmtInt(m.kcal)} kcal',
            style: AppText.number,
            textAlign: TextAlign.end,
          ),
        ),
        Icon(Icons.chevron_right, color: AppColors.text3),
      ],
    ),
  );
}

class _MeasurementsCard extends ConsumerWidget {
  const _MeasurementsCard({required this.items});
  final List<Measurement> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final latest = items.isEmpty ? null : items.last;
    final parts = [
      if (latest?.waistCm != null) 'Waist ${fmtNum(latest!.waistCm!)} cm',
      if (latest?.hipCm != null) 'Hip ${fmtNum(latest!.hipCm!)} cm',
      if (latest?.bodyFatPct != null)
        'Body fat ${fmtNum(latest!.bodyFatPct!)}%',
    ];
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionTitle(
            'Measurements',
            trailing: AppChip(
              label: 'Add',
              icon: Icons.add,
              onTap: () => _showMeasurementSheet(context),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            latest == null
                ? 'Waist, hip and body fat show how you are changing beyond the scale.'
                : '${parts.join(' · ')} (${shortDate(latest.day)})',
            style: latest == null ? AppText.caption : AppText.body,
          ),
          if (items.length > 1) ...[
            const SizedBox(height: 4),
            Text('${items.length} measurements logged', style: AppText.caption),
          ],
        ],
      ),
    );
  }
}

Future<void> _showMeasurementSheet(BuildContext context) =>
    showAppSheet<void>(context, builder: (_) => const _MeasurementSheet());

class _MeasurementSheet extends ConsumerStatefulWidget {
  const _MeasurementSheet();
  @override
  ConsumerState<_MeasurementSheet> createState() => _MeasurementSheetState();
}

class _MeasurementSheetState extends ConsumerState<_MeasurementSheet> {
  final _form = GlobalKey<FormState>();
  final _waist = TextEditingController();
  final _hip = TextEditingController();
  final _fat = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _waist.dispose();
    _hip.dispose();
    _fat.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    final waist = parseNumber(_waist.text),
        hip = parseNumber(_hip.text),
        fat = parseNumber(_fat.text);
    if (waist == null && hip == null && fat == null) {
      setState(() => _error = 'Enter at least one measurement.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(apiProvider)
          .logMeasurement(waistCm: waist, hipCm: hip, bodyFatPct: fat);
      ref.read(dataVersion.notifier).bump();
      if (mounted) Navigator.pop(context);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Form(
    key: _form,
    child: Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Add measurements', style: AppText.title),
        const SizedBox(height: 4),
        Text(
          'Fill in what you have. Body fat % from a report also improves your calorie targets.',
          style: AppText.caption,
        ),
        const SizedBox(height: 12),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        NumberField(
          controller: _waist,
          label: 'Waist',
          suffix: 'cm',
          min: 40,
          max: 250,
          required: false,
        ),
        const SizedBox(height: 12),
        NumberField(
          controller: _hip,
          label: 'Hip',
          suffix: 'cm',
          min: 40,
          max: 250,
          required: false,
        ),
        const SizedBox(height: 12),
        NumberField(
          controller: _fat,
          label: 'Body fat',
          suffix: '%',
          min: 3,
          max: 70,
          required: false,
          textInputAction: TextInputAction.done,
        ),
        const SizedBox(height: 16),
        PrimaryButton(label: 'Save', onPressed: _save, loading: _busy),
      ],
    ),
  );
}

// --- History --------------------------------------------------------------------------------

class _HistoryView extends ConsumerStatefulWidget {
  const _HistoryView();
  @override
  ConsumerState<_HistoryView> createState() => _HistoryViewState();
}

class _HistoryViewState extends ConsumerState<_HistoryView> {
  String _period = 'day';
  static const _keep = {'day': 30, 'week': 12, 'month': 12, 'year': 5};
  static const _names = {
    'day': 'Day',
    'week': 'Week',
    'month': 'Month',
    'year': 'Year',
  };

  String _label(HistoryPoint p) => switch (_period) {
    'month' => [
      '',
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ][p.date.month],
    'year' => '${p.date.year}',
    _ => shortDate(p.date),
  };

  @override
  Widget build(BuildContext context) {
    final history = ref.watch(historyProvider(_period));
    final targets = ref.watch(sessionProvider).profile?.targets;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
      children: [
        Wrap(
          spacing: 8,
          children: [
            for (final e in _names.entries)
              AppChip(
                label: e.value,
                selected: _period == e.key,
                onTap: () => setState(() => _period = e.key),
              ),
          ],
        ),
        const SizedBox(height: 8),
        history.when(
          skipLoadingOnRefresh: true,
          loading: () => const Padding(
            padding: EdgeInsets.all(48),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (e, _) => ErrorView(
            error: e,
            onRetry: () => ref.invalidate(historyProvider(_period)),
          ),
          data: (h) {
            final n = _keep[_period]!;
            final pts = h.points.length > n
                ? h.points.sublist(h.points.length - n)
                : h.points;
            final logged = pts.where((p) => p.kcal > 0).length;
            if (pts.isEmpty || logged == 0) {
              return const AppCard(
                child: EmptyState(
                  icon: Icons.insights_outlined,
                  message: 'Log a few meals to see your history here.',
                ),
              );
            }
            final labels = pts.map(_label).toList();
            final weights = pts.where((p) => p.weightKg != null).toList();
            Widget chart(
              String title,
              String note,
              List<double> v,
              Color c, {
              double? target,
            }) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(title, style: AppText.section),
                    Text(note, style: AppText.caption),
                    const SizedBox(height: 8),
                    Semantics(
                      label: '$title chart',
                      child: ExcludeSemantics(
                        child: BarsChart(
                          values: v,
                          labels: labels,
                          color: c,
                          target: target,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '${h.daysLogged} days logged since you started. ${_period == 'day' ? '' : 'Bars show the average on days you logged.'}',
                  style: AppText.caption,
                ),
                const SizedBox(height: 8),
                chart(
                  'Calories',
                  targets == null
                      ? 'kcal'
                      : 'kcal · dashed line is your target of ${fmtInt(targets.kcal)}',
                  pts.map((p) => p.kcal).toList(),
                  AppColors.primary,
                  target: targets?.kcal.toDouble(),
                ),
                chart(
                  'Protein',
                  targets == null
                      ? 'g'
                      : 'g · dashed line is your target of ${targets.proteinG} g',
                  pts.map((p) => p.protein).toList(),
                  AppColors.protein,
                  target: targets?.proteinG.toDouble(),
                ),
                chart(
                  'Steps',
                  'per day',
                  pts.map((p) => p.steps).toList(),
                  AppColors.water,
                  target: targets?.steps.toDouble(),
                ),
                if (weights.length >= 2)
                  AppCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text('Weight', style: AppText.section),
                        Text(
                          '${fmtNum(weights.first.weightKg!)} → ${fmtNum(weights.last.weightKg!)} kg',
                          style: AppText.caption,
                        ),
                      ],
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}
