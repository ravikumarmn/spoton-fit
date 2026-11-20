import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:material_symbols_icons/symbols.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../auth/server_sheet.dart';
import '../onboarding/onboarding.dart';

// --- Me (hub) -----------------------------------------------------------------------------

class MeScreen extends ConsumerWidget {
  const MeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(sessionProvider);
    final t = s.profile?.targets;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          Semantics(header: true, child: Text('Me', style: AppText.title)),
          const SizedBox(height: 12),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(s.email ?? '', style: AppText.section),
                if (t != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    '${fmtInt(t.kcal)} kcal · ${t.proteinG} g protein · ${fmtInt(t.steps)} steps a day',
                    style: AppText.caption,
                  ),
                ],
                const SizedBox(height: 12),
                SecondaryButton(
                  label: 'Edit profile',
                  onPressed: () => context.push('/me/profile'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          _Group(
            children: [
              _Row(
                'My foods',
                Symbols.restaurant_menu_rounded,
                () => context.push('/me/foods'),
              ),
              _Row(
                'Food rules',
                Symbols.rule_rounded,
                () => context.push('/me/rules'),
              ),
              _Row(
                'Coach notes',
                Symbols.sticky_note_2_rounded,
                () => context.push('/me/notes'),
              ),
              _Row(
                'Remembered foods',
                Symbols.bookmark_rounded,
                () => context.push('/me/remembered'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _Group(
            children: [
              _Row(
                'Export my data',
                Symbols.ios_share_rounded,
                () => context.push('/me/data'),
              ),
              _Row(
                'Appearance',
                Symbols.contrast_rounded,
                () => showAppearanceSheet(context, ref),
              ),
              _Row(
                'Change password',
                Symbols.lock_rounded,
                () => context.push('/me/password'),
              ),
              _Row(
                'Privacy policy',
                Symbols.privacy_tip_rounded,
                () => openPrivacyPolicy(context, ref),
              ),
              if (ref.watch(serverPickerProvider))
                _Row(
                  'Server address',
                  Symbols.dns_rounded,
                  () => showServerSheet(context),
                ),
              _Row(
                'Delete account',
                Symbols.delete_rounded,
                () => context.push('/me/delete'),
                color: AppColors.error,
              ),
            ],
          ),
          const SizedBox(height: 12),
          SecondaryButton(
            label: 'Sign out',
            onPressed: () async {
              if (await confirm(
                context,
                title: 'Sign out?',
                message: 'Your data stays safe on the server.',
                confirmLabel: 'Sign out',
              )) {
                await ref.read(sessionProvider.notifier).signOut();
              }
            },
          ),
          const SizedBox(height: 16),
          Text(
            'AI nutrition values are estimates. Not medical advice.',
            style: AppText.caption,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _Group extends StatelessWidget {
  const _Group({required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => AppCard(
    padding: const EdgeInsets.symmetric(horizontal: 4),
    child: Column(
      children: [
        for (var i = 0; i < children.length; i++) ...[
          if (i > 0) const Divider(height: 1),
          children[i],
        ],
      ],
    ),
  );
}

class _Row extends StatelessWidget {
  const _Row(this.label, this.icon, this.onTap, {this.color});
  final String label;
  final IconData icon;
  final VoidCallback onTap;
  final Color? color;
  @override
  Widget build(BuildContext context) => ListTile(
    minTileHeight: AppSpace.minTap + 4,
    leading: Icon(icon, color: color ?? AppColors.text2),
    title: Text(
      label,
      style: AppText.body.copyWith(color: color ?? AppColors.text),
    ),
    trailing: Icon(Symbols.chevron_right_rounded, color: AppColors.text3),
    onTap: onTap,
  );
}

class SubScaffold extends StatelessWidget {
  const SubScaffold({
    super.key,
    required this.title,
    required this.child,
    this.actions,
  });
  final String title;
  final Widget child;
  final List<Widget>? actions;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      leading: BackButton(onPressed: () => context.pop()),
      title: Text(title),
      actions: actions,
    ),
    body: SafeArea(child: child),
  );
}

// --- Edit profile ---------------------------------------------------------------------------

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});
  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _form = GlobalKey<FormState>();
  late final ProfileInput _p = ref.read(sessionProvider).profile!.input.copy();
  late final _age = TextEditingController(text: '${_p.age}');
  late final _height = TextEditingController(text: fmtNum(_p.heightCm));
  late final _weight = TextEditingController(text: fmtNum(_p.weightKg));
  late final _bodyFat = TextEditingController(
    text: _p.bodyFatPct == null ? '' : fmtNum(_p.bodyFatPct!),
  );
  late final _goalWeight = TextEditingController(
    text: _p.goalWeightKg == null ? '' : fmtNum(_p.goalWeightKg!),
  );
  late final _steps = TextEditingController(text: '${_p.baselineSteps}');
  final _scroll = ScrollController();
  bool _busy = false;
  String? _error;
  Profile? _saved;

  @override
  void dispose() {
    for (final c in [_age, _height, _weight, _bodyFat, _goalWeight, _steps]) {
      c.dispose();
    }
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    _p
      ..age = parseNumber(_age.text)!.round()
      ..heightCm = parseNumber(_height.text)!
      ..weightKg = parseNumber(_weight.text)!
      ..bodyFatPct = parseNumber(_bodyFat.text)
      ..goalWeightKg = _p.goal == 'maintain'
          ? null
          : parseNumber(_goalWeight.text)
      ..baselineSteps = parseNumber(_steps.text)?.round() ?? 5000;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final saved = await ref.read(sessionProvider.notifier).saveProfile(_p);
      if (!mounted) return;
      setState(() => _saved = saved);
      // The confirmation is at the top of a long form: bring it into view and say it out loud.
      showToast(context, 'Profile saved');
      if (_scroll.hasClients) {
        unawaited(
          _scroll.animateTo(
            0,
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOut,
          ),
        );
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final saved = _saved;
    return SubScaffold(
      title: 'Edit profile',
      child: Form(
        key: _form,
        child: ListView(
          controller: _scroll,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            if (_error != null) ...[
              InfoBanner(_error!, kind: BannerKind.error),
              const SizedBox(height: 12),
            ],
            if (saved != null) ...[
              for (final w in saved.warnings) ...[
                InfoBanner(w, kind: BannerKind.warn),
                const SizedBox(height: 12),
              ],
              InfoBanner(
                'Saved. Your target is now ${fmtInt(saved.targets.kcal)} kcal and ${saved.targets.proteinG} g protein a day.',
                kind: BannerKind.soft,
                icon: Symbols.check_circle_rounded,
              ),
              const SizedBox(height: 12),
            ],
            Text('Goal', style: AppText.label),
            const SizedBox(height: 8),
            for (final g in goalOptions) ...[
              ChoiceCard(
                title: g.$2,
                subtitle: g.$3,
                selected: _p.goal == g.$1,
                onTap: () => setState(() => _p.goal = g.$1),
              ),
              const SizedBox(height: 8),
            ],
            const SizedBox(height: 8),
            Text('Activity', style: AppText.label),
            const SizedBox(height: 8),
            for (final a in activityOptions) ...[
              ChoiceCard(
                title: a.$2,
                subtitle: a.$3,
                selected: _p.activity == a.$1,
                onTap: () => setState(() => _p.activity = a.$1),
              ),
              const SizedBox(height: 8),
            ],
            const SizedBox(height: 8),
            Text('Sex', style: AppText.label),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'male', label: Text('Male')),
                ButtonSegment(value: 'female', label: Text('Female')),
              ],
              selected: {_p.sex},
              showSelectedIcon: false,
              onSelectionChanged: (s) => setState(() => _p.sex = s.first),
            ),
            const SizedBox(height: 16),
            NumberField(
              controller: _age,
              label: 'Age',
              suffix: 'years',
              min: 18,
              max: 100,
              decimals: false,
            ),
            const SizedBox(height: 12),
            NumberField(
              controller: _height,
              label: 'Height',
              suffix: 'cm',
              min: 100,
              max: 250,
            ),
            const SizedBox(height: 12),
            NumberField(
              controller: _weight,
              label: 'Weight',
              suffix: 'kg',
              min: 30,
              max: 300,
            ),
            const SizedBox(height: 12),
            NumberField(
              controller: _bodyFat,
              label: 'Body fat % (optional)',
              suffix: '%',
              min: 3,
              max: 70,
              required: false,
              helper: 'From a body-composition report. A wrong value changes your targets a lot.',
            ),
            const SizedBox(height: 12),
            if (_p.goal != 'maintain') ...[
              NumberField(
                controller: _goalWeight,
                label: 'Goal weight (optional)',
                suffix: 'kg',
                min: 30,
                max: 300,
                required: false,
              ),
              const SizedBox(height: 12),
            ],
            NumberField(
              controller: _steps,
              label: 'Usual daily steps',
              decimals: false,
              min: 0,
              max: 50000,
              textInputAction: TextInputAction.done,
              helper:
                  'Your step target starts here and grows a little each week.',
            ),
            const SizedBox(height: 20),
            PrimaryButton(label: 'Save', onPressed: _save, loading: _busy),
          ],
        ),
      ),
    );
  }
}

// --- My foods ---------------------------------------------------------------------------------

const _efforts = {
  'no_cook': 'No cooking',
  '5_min': '5-minute prep',
  'buy_nearby': 'Buy nearby',
  'order': 'Order in',
};

class MyFoodsScreen extends ConsumerWidget {
  const MyFoodsScreen({super.key});

  Future<void> _save(
    BuildContext context,
    WidgetRef ref,
    List<MyFood> foods,
  ) async {
    try {
      await ref.read(apiProvider).saveMyFoods(foods);
      ref.read(dataVersion.notifier).bump();
    } on ApiException catch (e) {
      if (context.mounted) showToast(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final foods = ref.watch(myFoodsProvider);
    return SubScaffold(
      title: 'My foods',
      child: AsyncView<List<MyFood>>(
        value: foods,
        onRetry: () => ref.invalidate(myFoodsProvider),
        builder: (list) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            Text(
              'Foods you can actually get. Suggestions use only the ones marked available.',
              style: AppText.caption,
            ),
            const SizedBox(height: 12),
            if (list.isEmpty)
              const AppCard(
                child: EmptyState(
                  icon: Symbols.restaurant_menu_rounded,
                  message: 'No foods yet. Add oats, eggs, curd, idli… whatever you really have.',
                ),
              ),
            for (final f in list) ...[
              Dismissible(
                key: ValueKey('${f.id}-${f.name}'),
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.only(right: 24),
                  decoration: BoxDecoration(
                    color: AppColors.errorBg,
                    borderRadius: BorderRadius.circular(AppSpace.radiusCard),
                  ),
                  child: Icon(Symbols.delete_rounded, color: AppColors.error),
                ),
                onDismissed: (_) => _save(context, ref, [...list]..remove(f)),
                child: AppCard(
                  padding: const EdgeInsets.fromLTRB(16, 4, 8, 4),
                  onTap: () async {
                    final edited = await _foodSheet(context, f);
                    if (edited != null && context.mounted) {
                      await _save(context, ref, [
                        for (final x in list) x == f ? edited : x,
                      ]);
                    }
                  },
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              f.name,
                              style: AppText.labelBold.copyWith(fontSize: 16),
                            ),
                            Text(
                              '${_efforts[f.effort] ?? f.effort}${f.slots.isEmpty ? '' : ' · ${f.slots.map(slotLabel).join(', ')}'}${f.available ? '' : ' · not available now'}',
                              style: AppText.caption,
                            ),
                          ],
                        ),
                      ),
                      Switch(
                        value: f.available,
                        onChanged: (v) => _save(context, ref, [
                          for (final x in list)
                            x == f ? f.copyWith(available: v) : x,
                        ]),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 8),
            ],
            const SizedBox(height: 4),
            PrimaryButton(
              label: 'Add food',
              icon: Symbols.add_rounded,
              onPressed: () async {
                final created = await _foodSheet(context, null);
                if (created != null && context.mounted) {
                  await _save(context, ref, [...list, created]);
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}

Future<MyFood?> _foodSheet(BuildContext context, MyFood? food) =>
    showAppSheet<MyFood>(context, builder: (_) => _FoodSheet(food: food));

class _FoodSheet extends StatefulWidget {
  const _FoodSheet({this.food});
  final MyFood? food;
  @override
  State<_FoodSheet> createState() => _FoodSheetState();
}

class _FoodSheetState extends State<_FoodSheet> {
  late final _name = TextEditingController(text: widget.food?.name ?? '');
  late String _effort = widget.food?.effort ?? 'no_cook';
  late final Set<String> _slots = {...?widget.food?.slots};
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(
        widget.food == null ? 'Add a food' : 'Edit food',
        style: AppText.title,
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _name,
        textCapitalization: TextCapitalization.sentences,
        decoration: InputDecoration(labelText: 'Food', errorText: _error),
      ),
      const SizedBox(height: 12),
      Text('How much effort is it?', style: AppText.label),
      const SizedBox(height: 4),
      Wrap(
        spacing: 8,
        children: [
          for (final e in _efforts.entries)
            AppChip(
              label: e.value,
              selected: _effort == e.key,
              onTap: () => setState(() => _effort = e.key),
            ),
        ],
      ),
      const SizedBox(height: 12),
      Text('Good for (leave empty for any meal)', style: AppText.label),
      const SizedBox(height: 4),
      Wrap(
        spacing: 8,
        children: [
          for (final s in mealSlots)
            AppChip(
              label: slotLabel(s),
              selected: _slots.contains(s),
              onTap: () => setState(
                () => _slots.contains(s) ? _slots.remove(s) : _slots.add(s),
              ),
            ),
        ],
      ),
      const SizedBox(height: 16),
      PrimaryButton(
        label: 'Save',
        onPressed: () {
          if (_name.text.trim().isEmpty) {
            setState(() => _error = 'Enter the food name');
            return;
          }
          Navigator.pop(
            context,
            (widget.food ?? const MyFood(name: '')).copyWith(
              name: _name.text.trim(),
              effort: _effort,
              slots: mealSlots.where(_slots.contains).toList(),
            ),
          );
        },
      ),
    ],
  );
}

// --- Food rules -------------------------------------------------------------------------------

class RulesScreen extends ConsumerWidget {
  const RulesScreen({super.key});

  static (IconData, Color, String) _status(String? state) => switch (state) {
    'broken' => (Symbols.error_rounded, AppColors.warn, 'Broken today'),
    'at_limit' => (
      Symbols.pause_circle_rounded,
      AppColors.amber,
      'At the limit',
    ),
    _ => (Symbols.check_circle_rounded, AppColors.primary, 'On track'),
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rules = ref.watch(rulesProvider);
    return SubScaffold(
      title: 'Food rules',
      child: AsyncView<List<FoodRule>>(
        value: rules,
        onRetry: () => ref.invalidate(rulesProvider),
        builder: (list) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            Text(
              'Write a rule in your own words. SpotOn shows how it understood it before saving. '
              'Rules shape suggestions and give gentle nudges, never blame.',
              style: AppText.caption,
            ),
            const SizedBox(height: 12),
            if (list.isEmpty)
              const AppCard(
                child: EmptyState(
                  icon: Symbols.rule_rounded,
                  message: 'No rules yet. Try "no tea after 4 PM" or "idli at most 3 days a week".',
                ),
              ),
            for (final r in list) ...[
              Builder(
                builder: (_) {
                  final (icon, color, label) = _status(r.state);
                  return AppCard(
                    padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
                    child: Row(
                      children: [
                        Icon(icon, color: color, semanticLabel: label),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                r.summary,
                                style: AppText.labelBold.copyWith(fontSize: 16),
                              ),
                              Text(r.status ?? label, style: AppText.caption),
                            ],
                          ),
                        ),
                        IconButton(
                          tooltip: 'Delete rule',
                          icon: const Icon(Symbols.delete_rounded),
                          onPressed: () async {
                            if (await confirm(
                              context,
                              title: 'Delete this rule?',
                              message: r.summary,
                              confirmLabel: 'Delete',
                              destructive: true,
                            )) {
                              await ref.read(apiProvider).deleteRule(r.id!);
                              ref.read(dataVersion.notifier).bump();
                            }
                          },
                        ),
                      ],
                    ),
                  );
                },
              ),
              const SizedBox(height: 8),
            ],
            const SizedBox(height: 4),
            PrimaryButton(
              label: 'Add rule',
              icon: Symbols.add_rounded,
              onPressed: () => showAppSheet<void>(
                context,
                builder: (_) => const _RuleSheet(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RuleSheet extends ConsumerStatefulWidget {
  const _RuleSheet();
  @override
  ConsumerState<_RuleSheet> createState() => _RuleSheetState();
}

class _RuleSheetState extends ConsumerState<_RuleSheet> {
  final _text = TextEditingController();
  FoodRule? _draft;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _check() async {
    if (_text.text.trim().length < 3) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await ref.read(apiProvider).parseRule(_text.text.trim());
      if (mounted) setState(() => _draft = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await ref.read(apiProvider).saveRule(_draft!);
      ref.read(dataVersion.notifier).bump();
      if (mounted) Navigator.pop(context);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _draft;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Add a rule', style: AppText.title),
        const SizedBox(height: 12),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        if (d == null) ...[
          TextField(
            controller: _text,
            textCapitalization: TextCapitalization.sentences,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _check(),
            decoration: const InputDecoration(
              labelText: 'Your rule',
              hintText: 'no tea after 4 PM',
            ),
          ),
          const SizedBox(height: 16),
          PrimaryButton(label: 'Check rule', onPressed: _check, loading: _busy),
        ] else ...[
          InfoBanner(
            'I understood: ${d.summary}',
            kind: BannerKind.soft,
            icon: Symbols.check_circle_rounded,
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            label: 'Save this rule',
            onPressed: _save,
            loading: _busy,
          ),
          const SizedBox(height: 4),
          TextButton(
            onPressed: () => setState(() => _draft = null),
            child: const Text("That's not right"),
          ),
        ],
      ],
    );
  }
}

// --- Remembered foods -------------------------------------------------------------------------

class RememberedScreen extends ConsumerWidget {
  const RememberedScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final foods = ref.watch(rememberedFoodsProvider);
    return SubScaffold(
      title: 'Remembered foods',
      child: AsyncView<List<RememberedFood>>(
        value: foods,
        onRetry: () => ref.invalidate(rememberedFoodsProvider),
        builder: (list) => ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          children: [
            Text(
              'When you correct a food\'s values while logging, SpotOn remembers them and uses them next time.',
              style: AppText.caption,
            ),
            const SizedBox(height: 12),
            if (list.isEmpty)
              const AppCard(
                child: EmptyState(
                  icon: Symbols.bookmark_rounded,
                  message: 'Nothing yet. Tap a food on the review screen and fix its values to teach SpotOn.',
                ),
              ),
            for (final f in list) ...[
              AppCard(
                padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            f.name,
                            style: AppText.labelBold.copyWith(fontSize: 16),
                          ),
                          Text(
                            'per ${f.unit}: ${fmtInt(f.kcal)} kcal · ${fmtNum(f.protein)} g protein · used ${f.timesUsed}×',
                            style: AppText.caption,
                          ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: () async {
                        await ref.read(apiProvider).forgetFood(f.id);
                        ref.read(dataVersion.notifier).bump();
                      },
                      child: const Text('Forget'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
            ],
          ],
        ),
      ),
    );
  }
}

// --- Your data: export and delete -------------------------------------------------------------

/// Hands the exported file to the phone's share sheet. Replaced in tests.
typedef ShareFile = Future<void> Function(
  List<int> bytes,
  String filename,
  String mimeType,
);

final shareFileProvider = Provider<ShareFile>((ref) {
  return (bytes, filename, mimeType) async {
    // In a browser there is no temporary folder; share_plus hands the bytes to the browser's
    // share sheet, or downloads the file when the browser has none.
    final XFile file;
    if (kIsWeb) {
      file = XFile.fromData(
        Uint8List.fromList(bytes),
        mimeType: mimeType,
        name: filename,
      );
    } else {
      final dir = await getTemporaryDirectory();
      final saved = File('${dir.path}/$filename');
      await saved.writeAsBytes(bytes, flush: true);
      file = XFile(saved.path, mimeType: mimeType);
    }
    await SharePlus.instance.share(
      ShareParams(files: [file], subject: 'My SpotOn data'),
    );
  };
});

class DataScreen extends ConsumerStatefulWidget {
  const DataScreen({super.key});
  @override
  ConsumerState<DataScreen> createState() => _DataScreenState();
}

class _DataScreenState extends ConsumerState<DataScreen> {
  String? _busy;

  Future<void> _export(String format) async {
    setState(() => _busy = format);
    try {
      final bytes = await ref.read(apiProvider).export(format);
      final stamp = DateTime.now().toIso8601String().substring(0, 10);
      await ref.read(shareFileProvider)(
        bytes,
        'spoton-export-$stamp.${format == 'csv' ? 'zip' : 'json'}',
        format == 'csv' ? 'application/zip' : 'application/json',
      );
    } catch (e) {
      if (mounted) showToast(context, errorMessage(e));
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  @override
  Widget build(BuildContext context) => SubScaffold(
    title: 'Export my data',
    child: ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        Text(
          'Your data belongs to you. Download everything you logged, any time.',
          style: AppText.body,
        ),
        const SizedBox(height: 16),
        PrimaryButton(
          label: 'Export as JSON',
          icon: Symbols.ios_share_rounded,
          loading: _busy == 'json',
          onPressed: _busy == null ? () => _export('json') : null,
        ),
        const SizedBox(height: 8),
        SecondaryButton(
          label: 'Export as CSV (zip)',
          icon: Symbols.table_chart_rounded,
          onPressed: _busy == null ? () => _export('csv') : null,
        ),
      ],
    ),
  );
}

/// Light, dark, or follow the phone's setting.
Future<void> showAppearanceSheet(BuildContext context, WidgetRef ref) =>
    showAppSheet<void>(
      context,
      builder: (sheet) => Consumer(
        builder: (context, ref, _) {
          Widget option(ThemeMode m, String label, String detail) =>
              RadioListTile<ThemeMode>(
                value: m,
                title: Text(label, style: AppText.body),
                subtitle: Text(detail, style: AppText.caption),
              );
          return RadioGroup<ThemeMode>(
            groupValue: ref.watch(appearanceProvider),
            onChanged: (v) async {
              if (v == null) return;
              await ref.read(appearanceProvider.notifier).set(v);
              if (sheet.mounted) Navigator.pop(sheet);
            },
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: Text('Appearance', style: AppText.section),
                ),
                option(
                  ThemeMode.system,
                  'Same as phone',
                  'Light or dark, following your phone',
                ),
                option(ThemeMode.light, 'Light', 'Always light'),
                option(
                  ThemeMode.dark,
                  'Dark',
                  'Always dark: easier on the eyes at night',
                ),
                const SizedBox(height: 8),
              ],
            ),
          );
        },
      ),
    );

/// Opens the server's privacy policy page (GET /privacy) in the browser.
Future<void> openPrivacyPolicy(BuildContext context, WidgetRef ref) async {
  final base = ref.read(serverUrlProvider).replaceAll(RegExp(r'/+$'), '');
  final url = Uri.parse('$base/privacy');
  final messenger = ScaffoldMessenger.of(context);
  if (!await launchUrl(url, mode: LaunchMode.externalApplication)) {
    messenger.showSnackBar(
      SnackBar(content: Text('Open $url in your browser')),
    );
  }
}

class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});
  @override
  ConsumerState<ChangePasswordScreen> createState() =>
      _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> {
  final _current = TextEditingController();
  final _next = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_current.text.isEmpty) {
      setState(() => _error = 'Enter your current password.');
      return;
    }
    if (_next.text.length < 8) {
      setState(() => _error = 'The new password needs at least 8 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(apiProvider).changePassword(_current.text, _next.text);
      if (!mounted) return;
      showToast(context, 'Password changed. Other devices are signed out.');
      context.pop();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => SubScaffold(
    title: 'Change password',
    child: ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        TextField(
          controller: _current,
          obscureText: true,
          autofillHints: const [AutofillHints.password],
          decoration: const InputDecoration(labelText: 'Current password'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _next,
          obscureText: true,
          autofillHints: const [AutofillHints.newPassword],
          decoration: const InputDecoration(
            labelText: 'New password',
            helperText: 'At least 8 characters',
          ),
          onSubmitted: (_) => _save(),
        ),
        const SizedBox(height: 16),
        PrimaryButton(
          label: 'Change password',
          loading: _busy,
          onPressed: _save,
        ),
      ],
    ),
  );
}

/// Things the coach remembers on every day: diet pattern, allergies, dislikes, schedule.
class CoachNotesScreen extends ConsumerStatefulWidget {
  const CoachNotesScreen({super.key});
  @override
  ConsumerState<CoachNotesScreen> createState() => _CoachNotesScreenState();
}

class _CoachNotesScreenState extends ConsumerState<CoachNotesScreen> {
  final _notes = TextEditingController();
  bool _loading = true, _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      _notes.text = await ref.read(apiProvider).coachNotes();
    } on ApiException catch (e) {
      _error = e.message;
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      _notes.text = await ref.read(apiProvider).setCoachNotes(_notes.text);
      if (mounted) {
        showToast(context, 'Saved. The coach will keep these in mind.');
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => SubScaffold(
    title: 'Coach notes',
    child: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              Text(
                'Things your coach should remember every day, for example '
                '"vegetarian on Tuesdays", "no dairy" or "I train at 6 PM". '
                'Suggestions follow them too.',
                style: AppText.body,
              ),
              const SizedBox(height: 16),
              if (_error != null) ...[
                InfoBanner(_error!, kind: BannerKind.error),
                const SizedBox(height: 12),
              ],
              TextField(
                controller: _notes,
                minLines: 4,
                maxLines: 10,
                maxLength: 1000,
                decoration: const InputDecoration(labelText: 'Your notes'),
              ),
              const SizedBox(height: 12),
              PrimaryButton(
                label: 'Save notes',
                loading: _busy,
                onPressed: _save,
              ),
            ],
          ),
  );
}

class DeleteAccountScreen extends ConsumerStatefulWidget {
  const DeleteAccountScreen({super.key});
  @override
  ConsumerState<DeleteAccountScreen> createState() =>
      _DeleteAccountScreenState();
}

class _DeleteAccountScreenState extends ConsumerState<DeleteAccountScreen> {
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  Future<void> _delete() async {
    if (_password.text.isEmpty) {
      setState(() => _error = 'Enter your password to confirm.');
      return;
    }
    if (!await confirm(
      context,
      title: 'Delete your account?',
      message: 'This permanently deletes your account and everything you logged. It cannot be undone.',
      confirmLabel: 'Delete everything',
      destructive: true,
    )) {
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(sessionProvider.notifier).deleteAccount(_password.text);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => SubScaffold(
    title: 'Delete account',
    child: ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        const InfoBanner(
          'Deleting your account removes your profile, meals, weights, chats and everything else SpotOn stored. '
          'Export your data first if you want a copy.',
          kind: BannerKind.warn,
        ),
        const SizedBox(height: 16),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        TextField(
          controller: _password,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Your password'),
          onSubmitted: (_) => _delete(),
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _busy ? null : _delete,
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.error,
            foregroundColor: AppColors.onPrimary,
          ),
          child: _busy
              ? SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.5,
                    color: AppColors.onPrimary,
                  ),
                )
              : const Text('Delete my account'),
        ),
      ],
    ),
  );
}
