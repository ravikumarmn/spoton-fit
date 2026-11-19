import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';

/// Small tasks that keep you on Today: water, steps, weight, workout.
Future<void> showWaterSheet(BuildContext context) =>
    showAppSheet<void>(context, builder: (_) => const _WaterSheet());
Future<void> showStepsSheet(BuildContext context, int current) =>
    showAppSheet<void>(context, builder: (_) => _StepsSheet(current: current));
Future<void> showWeightSheet(BuildContext context) =>
    showAppSheet<void>(context, builder: (_) => const _WeightSheet());
Future<void> showWorkoutSheet(BuildContext context) =>
    showAppSheet<void>(context, builder: (_) => const _WorkoutSheet());

class _WaterSheet extends ConsumerStatefulWidget {
  const _WaterSheet();
  @override
  ConsumerState<_WaterSheet> createState() => _WaterSheetState();
}

class _WaterSheetState extends ConsumerState<_WaterSheet> {
  final _custom = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _custom.dispose();
    super.dispose();
  }

  Future<void> _add(int ml) async {
    try {
      await ref
          .read(apiProvider)
          .addWater(ml, day: ref.read(selectedDayProvider));
      ref.read(dataVersion.notifier).bump();
      if (!mounted) return;
      final messenger = ScaffoldMessenger.of(context);
      Navigator.pop(context);
      messenger.showSnackBar(SnackBar(content: Text('Added $ml ml of water')));
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text('Add water', style: AppText.title),
      const SizedBox(height: 12),
      if (_error != null) ...[
        InfoBanner(_error!, kind: BannerKind.error),
        const SizedBox(height: 12),
      ],
      Wrap(
        spacing: 8,
        children: [
          for (final ml in const [250, 500, 750])
            AppChip(
              label: '+$ml ml',
              icon: Icons.water_drop_outlined,
              onTap: () => _add(ml),
            ),
        ],
      ),
      const SizedBox(height: 12),
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: NumberField(
              controller: _custom,
              label: 'Other amount',
              suffix: 'ml',
              decimals: false,
              min: 1,
              max: 3000,
              required: false,
            ),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 96,
            child: SecondaryButton(
              label: 'Add',
              onPressed: () {
                final v = parseNumber(_custom.text);
                if (v != null && v > 0 && v <= 3000) _add(v.round());
              },
            ),
          ),
        ],
      ),
    ],
  );
}

class _StepsSheet extends ConsumerStatefulWidget {
  const _StepsSheet({required this.current});
  final int current;
  @override
  ConsumerState<_StepsSheet> createState() => _StepsSheetState();
}

class _StepsSheetState extends ConsumerState<_StepsSheet> {
  final _form = GlobalKey<FormState>();
  late final _steps = TextEditingController(
    text: widget.current > 0 ? '${widget.current}' : '',
  );
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _steps.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      final day = ref.read(selectedDayProvider) ?? DateTime.now();
      await ref
          .read(apiProvider)
          .setSteps(day, parseNumber(_steps.text)!.round());
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
        Text('Steps today', style: AppText.title),
        const SizedBox(height: 4),
        Text(
          'Enter your total for the day. Automatic step counting comes later.',
          style: AppText.caption,
        ),
        const SizedBox(height: 12),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        NumberField(
          controller: _steps,
          label: 'Steps',
          decimals: false,
          min: 0,
          max: 150000,
          textInputAction: TextInputAction.done,
        ),
        const SizedBox(height: 16),
        PrimaryButton(label: 'Save steps', onPressed: _save, loading: _busy),
      ],
    ),
  );
}

class _WeightSheet extends ConsumerStatefulWidget {
  const _WeightSheet();
  @override
  ConsumerState<_WeightSheet> createState() => _WeightSheetState();
}

class _WeightSheetState extends ConsumerState<_WeightSheet> {
  final _form = GlobalKey<FormState>();
  final _kg = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _kg.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(apiProvider)
          .logWeight(
            parseNumber(_kg.text)!,
            day: ref.read(selectedDayProvider),
          );
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
        Text("Today's weight", style: AppText.title),
        const SizedBox(height: 4),
        Text(
          'Weigh yourself at the same time each day, ideally in the morning.',
          style: AppText.caption,
        ),
        const SizedBox(height: 12),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        NumberField(
          controller: _kg,
          label: 'Weight',
          suffix: 'kg',
          min: 30,
          max: 300,
          textInputAction: TextInputAction.done,
        ),
        const SizedBox(height: 16),
        PrimaryButton(label: 'Save weight', onPressed: _save, loading: _busy),
      ],
    ),
  );
}

class _WorkoutSheet extends ConsumerStatefulWidget {
  const _WorkoutSheet();
  @override
  ConsumerState<_WorkoutSheet> createState() => _WorkoutSheetState();
}

class _WorkoutSheetState extends ConsumerState<_WorkoutSheet> {
  final _text = TextEditingController();
  bool _busy = false;
  String? _error;
  List<WorkoutResult>? _done;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _log() async {
    if (_text.text.trim().length < 2) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await ref
          .read(apiProvider)
          .logWorkout(_text.text.trim(), day: ref.read(selectedDayProvider));
      ref.read(dataVersion.notifier).bump();
      if (mounted) setState(() => _done = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final done = _done;
    if (done != null) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Workout logged', style: AppText.title),
          const SizedBox(height: 12),
          for (final w in done)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                '${w.activity}: ${fmtNum(w.minutes)} min · about ${fmtInt(w.kcal)} kcal',
                style: AppText.body,
              ),
            ),
          Text(
            'Exercise is not added back to your food budget.',
            style: AppText.caption,
          ),
          const SizedBox(height: 16),
          PrimaryButton(label: 'Done', onPressed: () => Navigator.pop(context)),
        ],
      );
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Log a workout', style: AppText.title),
        const SizedBox(height: 4),
        Text(
          'Say it in your own words, with the time.',
          style: AppText.caption,
        ),
        const SizedBox(height: 12),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        TextField(
          controller: _text,
          minLines: 2,
          maxLines: 4,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(
            labelText: 'Workout',
            hintText: '15 min cycling, 40 min weights',
          ),
        ),
        const SizedBox(height: 16),
        PrimaryButton(label: 'Log workout', onPressed: _log, loading: _busy),
      ],
    );
  }
}
