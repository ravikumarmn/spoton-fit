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

class OnboardingNotifier extends Notifier<ProfileInput> {
  @override
  ProfileInput build() => ProfileInput();

  void update(void Function(ProfileInput p) change) {
    final c = state.copy();
    change(c);
    state = c;
  }
}

final onboardingProvider = NotifierProvider<OnboardingNotifier, ProfileInput>(
  OnboardingNotifier.new,
);

const goalOptions = [
  ('lose_fat', 'Lose fat', 'Eat a bit below maintenance and keep your muscle'),
  ('build_muscle', 'Build muscle', 'A small surplus with plenty of protein'),
  ('maintain', 'Maintain', 'Hold your weight steady'),
];

const activityOptions = [
  ('sedentary', 'Mostly sitting', 'Desk job, little exercise'),
  ('light', 'Light', 'Training 1–3 days a week'),
  ('moderate', 'Moderate', 'Training 3–5 days a week'),
  ('active', 'Very active', 'Hard training 6–7 days a week'),
];

/// A big selectable option (one of a set). Announced to screen readers as a radio choice.
class ChoiceCard extends StatelessWidget {
  const ChoiceCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });
  final String title, subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
    inMutuallyExclusiveGroup: true,
    checked: selected,
    button: true,
    label: '$title. $subtitle',
    child: ExcludeSemantics(
      child: Material(
        color: selected ? AppColors.container : AppColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpace.radiusCard),
          side: BorderSide(
            color: selected ? AppColors.primary : AppColors.outline,
            width: selected ? 2 : 1,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: AppText.section.copyWith(
                          color: selected
                              ? AppColors.onContainer
                              : AppColors.text,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: AppText.caption.copyWith(
                          color: selected
                              ? AppColors.onContainer
                              : AppColors.text2,
                        ),
                      ),
                    ],
                  ),
                ),
                Icon(
                  selected
                      ? Symbols.radio_button_checked_rounded
                      : Symbols.radio_button_unchecked_rounded,
                  color: selected ? AppColors.primary : AppColors.input,
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _Step extends StatelessWidget {
  const _Step({
    required this.step,
    required this.title,
    required this.subtitle,
    required this.child,
    required this.primaryLabel,
    required this.onPrimary,
    this.loading = false,
    this.onBack,
  });

  final int step;
  final String title, subtitle, primaryLabel;
  final Widget child;
  final VoidCallback? onPrimary, onBack;
  final bool loading;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: onBack == null ? null : BackButton(onPressed: onBack),
    ),
    body: SafeArea(
      child: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Semantics(
                    label: 'Step $step of 3',
                    child: Row(
                      children: [
                        for (var i = 1; i <= 3; i++)
                          Expanded(
                            child: Container(
                              height: 5,
                              margin: EdgeInsets.only(right: i < 3 ? 6 : 0),
                              decoration: BoxDecoration(
                                color: i <= step
                                    ? AppColors.primary
                                    : AppColors.track,
                                borderRadius: BorderRadius.circular(99),
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text('Step $step of 3', style: AppText.caption),
                  const SizedBox(height: 4),
                  Semantics(
                    header: true,
                    child: Text(title, style: AppText.title),
                  ),
                  const SizedBox(height: 4),
                  Text(subtitle, style: AppText.caption),
                  const SizedBox(height: 20),
                  child,
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
            child: PrimaryButton(
              label: primaryLabel,
              onPressed: onPrimary,
              loading: loading,
            ),
          ),
        ],
      ),
    ),
  );
}

// --- 1. Goal ---------------------------------------------------------------------------

class GoalScreen extends ConsumerStatefulWidget {
  const GoalScreen({super.key});
  @override
  ConsumerState<GoalScreen> createState() => _GoalScreenState();
}

class _GoalScreenState extends ConsumerState<GoalScreen> {
  late final TextEditingController _goalWeight = TextEditingController(
    text: ref.read(onboardingProvider).goalWeightKg?.toString() ?? '',
  );
  final _form = GlobalKey<FormState>();

  @override
  void dispose() {
    _goalWeight.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = ref.watch(onboardingProvider);
    return _Step(
      step: 1,
      title: "What's your goal?",
      subtitle: 'You can change this any time.',
      primaryLabel: 'Continue',
      onPrimary: () {
        if (!_form.currentState!.validate()) return;
        ref.read(onboardingProvider.notifier).update((p) {
          p.goalWeightKg = p.goal == 'maintain'
              ? null
              : parseNumber(_goalWeight.text);
        });
        context.go('/onboarding/about');
      },
      child: Form(
        key: _form,
        child: Column(
          children: [
            for (final g in goalOptions) ...[
              ChoiceCard(
                title: g.$2,
                subtitle: g.$3,
                selected: p.goal == g.$1,
                onTap: () => ref
                    .read(onboardingProvider.notifier)
                    .update((p) => p.goal = g.$1),
              ),
              const SizedBox(height: 12),
            ],
            if (p.goal != 'maintain') ...[
              const SizedBox(height: 4),
              NumberField(
                controller: _goalWeight,
                label: 'Goal weight (optional)',
                suffix: 'kg',
                required: false,
                min: 30,
                max: 300,
                helper: 'Lets SpotOn show when you are likely to reach it, as a range.',
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// --- 2. About you ---------------------------------------------------------------------

class AboutScreen extends ConsumerStatefulWidget {
  const AboutScreen({super.key});
  @override
  ConsumerState<AboutScreen> createState() => _AboutScreenState();
}

class _AboutScreenState extends ConsumerState<AboutScreen> {
  final _form = GlobalKey<FormState>();
  late final _age = TextEditingController(
    text: ref.read(onboardingProvider).age.toString(),
  );
  late final _height = TextEditingController(
    text: fmtNum(ref.read(onboardingProvider).heightCm),
  );
  late final _weight = TextEditingController(
    text: fmtNum(ref.read(onboardingProvider).weightKg),
  );

  @override
  void dispose() {
    _age.dispose();
    _height.dispose();
    _weight.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = ref.watch(onboardingProvider);
    return _Step(
      step: 2,
      title: 'About you',
      subtitle: 'Used only to work out your calorie and protein targets.',
      primaryLabel: 'Continue',
      onBack: () => context.go('/onboarding/goal'),
      onPrimary: () {
        if (!_form.currentState!.validate()) return;
        ref.read(onboardingProvider.notifier).update((p) {
          p.age = parseNumber(_age.text)!.round();
          p.heightCm = parseNumber(_height.text)!;
          p.weightKg = parseNumber(_weight.text)!;
        });
        context.go('/onboarding/activity');
      },
      child: Form(
        key: _form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Sex', style: AppText.label),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'male', label: Text('Male')),
                ButtonSegment(value: 'female', label: Text('Female')),
              ],
              selected: {p.sex},
              showSelectedIcon: false,
              onSelectionChanged: (s) => ref
                  .read(onboardingProvider.notifier)
                  .update((p) => p.sex = s.first),
            ),
            const SizedBox(height: 16),
            NumberField(
              controller: _age,
              label: 'Age',
              suffix: 'years',
              min: 18,
              max: 100,
              decimals: false,
              helper: 'SpotOn is for adults (18+).',
            ),
            const SizedBox(height: 16),
            NumberField(
              controller: _height,
              label: 'Height',
              suffix: 'cm',
              min: 100,
              max: 250,
            ),
            const SizedBox(height: 16),
            NumberField(
              controller: _weight,
              label: 'Weight',
              suffix: 'kg',
              min: 30,
              max: 300,
              textInputAction: TextInputAction.done,
            ),
          ],
        ),
      ),
    );
  }
}

// --- 3. Activity ----------------------------------------------------------------------

class ActivityScreen extends ConsumerStatefulWidget {
  const ActivityScreen({super.key});
  @override
  ConsumerState<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends ConsumerState<ActivityScreen> {
  final _form = GlobalKey<FormState>();
  late final _bodyFat = TextEditingController(
    text: ref.read(onboardingProvider).bodyFatPct?.toString() ?? '',
  );
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _bodyFat.dispose();
    super.dispose();
  }

  Future<void> _plan() async {
    if (!_form.currentState!.validate()) return;
    ref
        .read(onboardingProvider.notifier)
        .update((p) => p.bodyFatPct = parseNumber(_bodyFat.text));
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(sessionProvider.notifier)
          .saveProfile(ref.read(onboardingProvider));
      if (mounted) context.go('/onboarding/plan');
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = ref.watch(onboardingProvider);
    return _Step(
      step: 3,
      title: 'How active are you?',
      subtitle: 'Think of a normal week, not your best one.',
      primaryLabel: 'See my plan',
      loading: _busy,
      onBack: () => context.go('/onboarding/about'),
      onPrimary: _plan,
      child: Form(
        key: _form,
        child: Column(
          children: [
            if (_error != null) ...[
              InfoBanner(_error!, kind: BannerKind.error),
              const SizedBox(height: 12),
            ],
            for (final a in activityOptions) ...[
              ChoiceCard(
                title: a.$2,
                subtitle: a.$3,
                selected: p.activity == a.$1,
                onTap: () => ref
                    .read(onboardingProvider.notifier)
                    .update((p) => p.activity = a.$1),
              ),
              const SizedBox(height: 12),
            ],
            const SizedBox(height: 4),
            NumberField(
              controller: _bodyFat,
              label: 'Body fat % (optional)',
              suffix: '%',
              required: false,
              min: 3,
              max: 70,
              textInputAction: TextInputAction.done,
              helper: 'From a body-composition report. Leave it empty if unsure: a wrong value changes your targets a lot.',
            ),
          ],
        ),
      ),
    );
  }
}

// --- 4. Your plan -----------------------------------------------------------------------

/// Plain-language reasons for the numbers, computed from the real targets (nothing assumed).
List<String> explainPlan(Targets t, ProfileInput p) {
  final lines = <String>[
    'At rest your body burns about ${fmtInt(t.bmr)} kcal a day (BMR).',
    'With your activity, holding your weight takes about ${fmtInt(t.maintenance)} kcal a day (maintenance).',
  ];
  final diff = t.kcal - t.maintenance;
  if (p.goal == 'maintain' || diff.abs() < 1) {
    lines.add(
      'Your goal is to maintain, so your target is close to maintenance.',
    );
  } else {
    final pct = (diff.abs() / t.maintenance * 100).round();
    lines.add(
      'To ${p.goal == 'lose_fat' ? 'lose fat' : 'build muscle'}, your target is about $pct% '
      '${diff < 0 ? 'below' : 'above'} maintenance: ${fmtInt(t.kcal)} kcal.',
    );
  }
  if (t.kcal <= t.kcalFloor) {
    lines.add(
      'It is held at your safe minimum of ${fmtInt(t.kcalFloor)} kcal; SpotOn never goes below it.',
    );
  } else {
    lines.add(
      'SpotOn never goes below your safe minimum of ${fmtInt(t.kcalFloor)} kcal.',
    );
  }
  lines.add('Protein of ${t.proteinG} g a day helps you keep muscle.');
  if (t.maintenanceSource == 'learned') {
    lines.add('Maintenance now comes from your own weight and food data.');
  } else {
    lines.add(
      'After about 2 weeks of logging, SpotOn replaces the maintenance formula with your own data.',
    );
  }
  return lines;
}

class PlanScreen extends ConsumerWidget {
  const PlanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(sessionProvider).profile;
    if (profile == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final t = profile.targets;
    return Scaffold(
      appBar: AppBar(
        leading: BackButton(
          onPressed: () => context.go('/onboarding/activity'),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Semantics(
                      header: true,
                      child: Text('Your plan', style: AppText.title),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Worked out from what you told us. Targets adjust as SpotOn learns from you.',
                      style: AppText.caption,
                    ),
                    const SizedBox(height: 20),
                    for (final w in profile.warnings) ...[
                      InfoBanner(w, kind: BannerKind.warn),
                      const SizedBox(height: 12),
                    ],
                    AppCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Daily calories', style: AppText.caption),
                          Text('${fmtInt(t.kcal)} kcal', style: AppText.hero),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              _Stat('Protein', '${t.proteinG} g'),
                              _Stat('Steps', fmtInt(t.steps)),
                              _Stat(
                                'Water',
                                '${(t.waterMl / 1000).toStringAsFixed(1)} L',
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    AppCard(
                      child: Theme(
                        data: Theme.of(context)
                            .copyWith(dividerColor: Colors.transparent),
                        child: ExpansionTile(
                          tilePadding: EdgeInsets.zero,
                          childrenPadding: EdgeInsets.zero,
                          title: Text(
                            'How this was worked out',
                            style: AppText.section,
                          ),
                          children: [
                            for (final line in explainPlan(
                              t,
                              ref.read(onboardingProvider),
                            ))
                              Padding(
                                padding: const EdgeInsets.only(bottom: 8),
                                child: Align(
                                  alignment: Alignment.centerLeft,
                                  child: Text(line, style: AppText.body),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'These are estimates, not medical advice.',
                      style: AppText.caption,
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
              child: PrimaryButton(
                label: 'Start logging',
                onPressed: () =>
                    ref.read(sessionProvider.notifier).finishOnboarding(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);
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
