import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import '../log/log_state.dart';

/// A sensible default meal for the time of day; the user can change it on the review screen.
String slotForNow([DateTime? now]) {
  final h = (now ?? DateTime.now()).hour;
  if (h < 10) return 'breakfast';
  if (h < 12) return 'snack';
  if (h < 16) return 'lunch';
  if (h < 18) return 'snack';
  if (h < 22) return 'dinner';
  return 'bedtime';
}

Future<void> showSuggestionsSheet(BuildContext context) =>
    showAppSheet<void>(context, builder: (_) => const _SuggestionsSheet());

class _SuggestionsSheet extends ConsumerStatefulWidget {
  const _SuggestionsSheet();
  @override
  ConsumerState<_SuggestionsSheet> createState() => _SuggestionsSheetState();
}

class _SuggestionsSheetState extends ConsumerState<_SuggestionsSheet> {
  String _mode = 'my_foods';
  bool _busy = false;
  String? _error;
  Suggestions? _result;

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await ref.read(apiProvider).suggestions(_mode);
      if (mounted) setState(() => _result = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _use(SuggestionOption o) {
    ref
        .read(draftProvider.notifier)
        .startFromItems(o.items, slot: slotForNow());
    Navigator.pop(context);
    context.push('/log/review');
  }

  @override
  Widget build(BuildContext context) {
    final r = _result;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('What should I eat next?', style: AppText.title),
        const SizedBox(height: 12),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'my_foods', label: Text('My foods')),
            ButtonSegment(value: 'ideal', label: Text('Any food')),
          ],
          selected: {_mode},
          showSelectedIcon: false,
          onSelectionChanged: (s) => setState(() {
            _mode = s.first;
            _result = null;
          }),
        ),
        const SizedBox(height: 12),
        if (_error != null) ...[
          InfoBanner(_error!, kind: BannerKind.error),
          const SizedBox(height: 12),
        ],
        if (r == null)
          PrimaryButton(
            label: 'Suggest two options',
            onPressed: _load,
            loading: _busy,
          )
        else ...[
          Text(
            'Left today: ${fmtInt(r.leftKcal)} kcal · ${fmtInt(r.leftProteinG)} g protein',
            style: AppText.caption,
          ),
          if (r.note != null) ...[
            const SizedBox(height: 8),
            InfoBanner(r.note!),
          ],
          const SizedBox(height: 8),
          for (final o in r.options) ...[
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(o.title, style: AppText.section),
                  const SizedBox(height: 2),
                  Text(
                    '${fmtInt(o.totals.kcal)} kcal · ${fmtNum(o.totals.protein)} g protein · ${o.fits ? 'fits your calories' : 'over your calories'}',
                    style: AppText.labelBold.copyWith(
                      color: o.fits ? AppColors.primary : AppColors.warn,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(o.why, style: AppText.caption),
                  const SizedBox(height: 8),
                  for (final i in o.items)
                    Text(
                      '• ${fmtNum(i.quantity)} × ${i.name}',
                      style: AppText.body.copyWith(fontSize: 14),
                    ),
                  const SizedBox(height: 8),
                  SecondaryButton(
                    label: 'Review & log this',
                    onPressed: () => _use(o),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
          ],
          TextButton(
            onPressed: _busy ? null : _load,
            child: const Text('Suggest again'),
          ),
        ],
      ],
    );
  }
}
