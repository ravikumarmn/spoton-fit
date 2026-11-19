import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'item_sheet.dart';
import 'log_state.dart';

/// Waits for the analysis, with honest progress and a way out.
class AnalyzingScreen extends ConsumerStatefulWidget {
  const AnalyzingScreen({super.key});
  @override
  ConsumerState<AnalyzingScreen> createState() => _AnalyzingScreenState();
}

class _AnalyzingScreenState extends ConsumerState<AnalyzingScreen> {
  static const _messages = [
    'Looking at your meal…',
    'Counting the pieces…',
    'Estimating calories and protein…',
  ];
  int _step = 0;
  bool _cancelled = false;
  ApiException? _error;
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(const Duration(milliseconds: 2500), (_) {
      if (mounted && _error == null) {
        setState(() => _step = (_step + 1) % _messages.length);
      }
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _run());
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> _run() async {
    final req = ref.read(captureRequestProvider);
    if (req == null) {
      if (mounted) context.go('/today');
      return;
    }
    setState(() => _error = null);
    try {
      final draft = await ref
          .read(apiProvider)
          .analyze(note: req.note, image: req.image);
      if (!mounted || _cancelled) return;
      ref
          .read(draftProvider.notifier)
          .startFromAnalysis(
            draft,
            source: req.image != null ? 'photo' : 'text',
            note: req.note,
          );
      context.pushReplacement('/log/review');
    } on ApiException catch (e) {
      if (mounted && !_cancelled) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final err = _error;
    return PopScope(
      onPopInvokedWithResult: (_, _) => _cancelled = true,
      child: Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: err == null
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(
                          width: 56,
                          height: 56,
                          child: CircularProgressIndicator(strokeWidth: 5),
                        ),
                        const SizedBox(height: 24),
                        Semantics(
                          liveRegion: true,
                          child: Text(_messages[_step], style: AppText.section),
                        ),
                        const SizedBox(height: 4),
                        Text('Usually a few seconds', style: AppText.caption),
                        const SizedBox(height: 24),
                        TextButton(
                          onPressed: () => context.pop(),
                          child: const Text('Cancel'),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        InfoBanner(err.message, kind: BannerKind.error),
                        const SizedBox(height: 16),
                        if (err.code != 'ai_not_configured')
                          PrimaryButton(label: 'Try again', onPressed: _run),
                        const SizedBox(height: 8),
                        SecondaryButton(
                          label: 'Type it instead',
                          onPressed: () =>
                              context.pushReplacement('/log?mode=type'),
                        ),
                        TextButton(
                          onPressed: () => context.pop(),
                          child: const Text('Close'),
                        ),
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Check and fix the estimate, then save. Nothing is saved before "Save meal".
class ReviewScreen extends ConsumerStatefulWidget {
  const ReviewScreen({super.key});
  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  bool _saving = false;
  String? _error;

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    final remembered = ref
        .read(draftProvider)!
        .items
        .where((i) => i.source == 'edited' || i.source == 'manual')
        .map((i) => i.name)
        .toList();
    try {
      final meal = await ref.read(draftProvider.notifier).save();
      if (!mounted) return;
      showToast(
        context,
        remembered.isEmpty
            ? 'Saved: ${fmtInt(meal.totals.kcal)} kcal'
            : 'Saved: ${fmtInt(meal.totals.kcal)} kcal. Remembered your values for ${remembered.join(', ')}.',
      );
      context.go('/today');
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _leave() async {
    final d = ref.read(draftProvider);
    final needsConfirm = d != null && (d.editingMealId == null || d.edited);
    if (!needsConfirm ||
        await confirm(
          context,
          title: 'Discard this meal?',
          message: "It hasn't been saved yet.",
          confirmLabel: 'Discard',
          cancelLabel: 'Keep editing',
          destructive: true,
        )) {
      ref.read(draftProvider.notifier).clear();
      if (mounted) context.pop();
    }
  }

  Future<void> _editItem(int i) async {
    final notifier = ref.read(draftProvider.notifier);
    final item = ref.read(draftProvider)!.items[i];
    final edited = await showItemSheet(
      context,
      item: item,
      onRemove: () => notifier.removeAt(i),
    );
    if (edited != null) notifier.replaceItem(i, edited);
  }

  Future<void> _addItem() async {
    final item = await showItemSheet(context);
    if (item != null) ref.read(draftProvider.notifier).addItem(item);
  }

  Future<void> _pickSlot() async {
    final current = ref.read(draftProvider)!.slot;
    final slot = await showAppSheet<String>(
      context,
      builder: (ctx) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Which meal?', style: AppText.title),
          const SizedBox(height: 8),
          for (final s in mealSlots)
            ListTile(
              minTileHeight: AppSpace.minTap,
              contentPadding: EdgeInsets.zero,
              title: Text(slotLabel(s), style: AppText.body),
              trailing: s == current
                  ? const Icon(Icons.check, color: AppColors.primary)
                  : null,
              onTap: () => Navigator.pop(ctx, s),
            ),
        ],
      ),
    );
    if (slot != null) ref.read(draftProvider.notifier).setSlot(slot);
  }

  Future<void> _addNote() async {
    final notifier = ref.read(draftProvider.notifier);
    final controller = TextEditingController(
      text: ref.read(draftProvider)?.note ?? '',
    );
    final note = await showAppSheet<String>(
      context,
      builder: (ctx) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Add a note', style: AppText.title),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            maxLines: 3,
            maxLength: 500,
            textCapitalization: TextCapitalization.sentences,
            decoration: const InputDecoration(labelText: 'Note'),
          ),
          const SizedBox(height: 12),
          PrimaryButton(
            label: 'Save note',
            onPressed: () => Navigator.pop(ctx, controller.text),
          ),
        ],
      ),
    );
    controller.dispose();
    if (note != null) notifier.setNote(note);
  }

  @override
  Widget build(BuildContext context) {
    final d = ref.watch(draftProvider);
    if (d == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) context.go('/today');
      });
      return const Scaffold();
    }
    final total = d.total;
    final editing = d.editingMealId != null;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_leave());
      },
      child: Scaffold(
        appBar: AppBar(
          leading: IconButton(
            tooltip: 'Close',
            icon: const Icon(Icons.close),
            onPressed: _leave,
          ),
          title: Text(editing ? 'Edit meal' : 'Review meal'),
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: AppChip(
                label: '${slotLabel(d.slot)} ▾',
                selected: true,
                onTap: _pickSlot,
              ),
            ),
          ],
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  children: [
                    if (_error != null) ...[
                      InfoBanner(_error!, kind: BannerKind.error),
                      const SizedBox(height: 12),
                    ],
                    if (d.clarify != null) ...[
                      InfoBanner(d.clarify!, icon: Icons.help_outline),
                      const SizedBox(height: 12),
                    ],
                    for (final w in d.warnings) ...[
                      InfoBanner(w, kind: BannerKind.warn),
                      const SizedBox(height: 12),
                    ],
                    if (d.oilyItems.isNotEmpty) ...[
                      InfoBanner(
                        '${d.oilyItems.join(', ')} looks oily or fried. Check the amounts: photos can miss oil.',
                        kind: BannerKind.warn,
                        icon: Icons.opacity,
                      ),
                      const SizedBox(height: 12),
                    ],
                    if (d.items.isEmpty)
                      const AppCard(
                        child: EmptyState(
                          icon: Icons.no_food_outlined,
                          message: 'No foods yet. Add what you ate below.',
                        ),
                      ),
                    for (var i = 0; i < d.items.length; i++) ...[
                      _ItemCard(
                        item: d.items[i],
                        onEdit: () => _editItem(i),
                        onQuantity: (q) =>
                            ref.read(draftProvider.notifier).setQuantity(i, q),
                      ),
                      const SizedBox(height: 8),
                    ],
                    Wrap(
                      spacing: 8,
                      children: [
                        AppChip(
                          label: 'Add food',
                          icon: Icons.add,
                          onTap: _addItem,
                        ),
                        AppChip(
                          label: d.favourite
                              ? 'Favourite'
                              : 'Save as favourite',
                          icon: d.favourite ? Icons.star : Icons.star_outline,
                          selected: d.favourite,
                          onTap: ref
                              .read(draftProvider.notifier)
                              .toggleFavourite,
                        ),
                        AppChip(
                          label: (d.note ?? '').isEmpty
                              ? 'Add note'
                              : 'Edit note',
                          icon: Icons.notes,
                          onTap: _addNote,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Calories are estimates. Change a count with − and +, or tap a food to correct its values.',
                      style: AppText.caption,
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                decoration: const BoxDecoration(
                  color: AppColors.surface,
                  border: Border(top: BorderSide(color: AppColors.outline)),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Wrap(
                      alignment: WrapAlignment.spaceBetween,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 12,
                      children: [
                        Text(
                          'Total ${fmtInt(total.kcal)} kcal',
                          style: AppText.section.copyWith(
                            fontFeatures: const [FontFeature.tabularFigures()],
                          ),
                        ),
                        Text(
                          'P ${fmtNum(total.protein)} g · C ${fmtNum(total.carbs)} g · F ${fmtNum(total.fat)} g',
                          style: AppText.caption,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    PrimaryButton(
                      label: editing ? 'Save changes' : 'Save meal',
                      loading: _saving,
                      onPressed: d.items.isEmpty ? null : _save,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ItemCard extends StatelessWidget {
  const _ItemCard({
    required this.item,
    required this.onEdit,
    required this.onQuantity,
  });
  final FoodItem item;
  final VoidCallback onEdit;
  final ValueChanged<double> onQuantity;

  String get _source => switch (item.source) {
    'memory' => 'your saved values',
    'edited' || 'manual' => 'your values',
    _ => 'AI estimate',
  };

  @override
  Widget build(BuildContext context) {
    final per = item.perUnit;
    final total = item.total;
    final estimate = item.source == 'ai_estimate';
    return AppCard(
      padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
      onTap: onEdit,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 6,
                      children: [
                        Text(
                          item.name,
                          style: AppText.labelBold.copyWith(fontSize: 16),
                        ),
                        if (item.isOily)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.warnBg,
                              borderRadius: BorderRadius.circular(99),
                            ),
                            child: Text(
                              'Oily',
                              style: AppText.caption.copyWith(
                                color: AppColors.warn,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${estimate ? '≈ ' : ''}${fmtInt(per.kcal)} kcal · ${fmtNum(per.protein)} g protein each · $_source',
                      style: AppText.caption,
                    ),
                    if (item.remark != null && item.remark!.isNotEmpty)
                      Text(
                        item.remark!,
                        style: AppText.caption.copyWith(color: AppColors.warn),
                      ),
                  ],
                ),
              ),
              QuantityStepper(
                value: item.quantity,
                itemName: item.name,
                onChanged: onQuantity,
              ),
            ],
          ),
          Align(
            alignment: Alignment.centerRight,
            child: Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Text(
                '${fmtInt(total.kcal)} kcal · ${fmtNum(total.protein)} g protein',
                style: AppText.label,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
