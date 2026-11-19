import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api/spoton_api.dart';
import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';
import '../../ui/format.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'log_state.dart';

enum CaptureMode { recent, photo, type }

/// Opens from the + button. All three ways in are visible at once.
class CaptureScreen extends ConsumerStatefulWidget {
  const CaptureScreen({super.key, this.initialMode = CaptureMode.photo});
  final CaptureMode initialMode;

  @override
  ConsumerState<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends ConsumerState<CaptureScreen> {
  late CaptureMode _mode = widget.initialMode;
  final _note = TextEditingController();
  final _typed = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    _typed.dispose();
    super.dispose();
  }

  void _analyze({UploadImage? image, String? note}) {
    ref
        .read(captureRequestProvider.notifier)
        .set(CaptureRequest(image: image, note: note));
    context.pushReplacement('/log/analyzing');
  }

  Future<void> _pick({required bool camera}) async {
    try {
      final image = await ref.read(pickPhotoProvider)(camera: camera);
      if (image == null || !mounted) return;
      _analyze(image: image, note: _note.text);
    } catch (_) {
      if (mounted) {
        showToast(
          context,
          camera
              ? "Couldn't open the camera. Check SpotOn's camera permission in your phone's settings."
              : "Couldn't open your photos. Check SpotOn's photo permission in your phone's settings.",
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'Close',
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
        title: const Text('Log a meal'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            SegmentedButton<CaptureMode>(
              segments: const [
                ButtonSegment(
                  value: CaptureMode.recent,
                  label: Text('Recent'),
                  icon: Icon(Icons.history),
                ),
                ButtonSegment(
                  value: CaptureMode.photo,
                  label: Text('Photo'),
                  icon: Icon(Icons.photo_camera_outlined),
                ),
                ButtonSegment(
                  value: CaptureMode.type,
                  label: Text('Type'),
                  icon: Icon(Icons.keyboard_outlined),
                ),
              ],
              selected: {_mode},
              showSelectedIcon: false,
              onSelectionChanged: (s) => setState(() => _mode = s.first),
            ),
            const SizedBox(height: 16),
            switch (_mode) {
              CaptureMode.photo => _photo(),
              CaptureMode.type => _type(),
              CaptureMode.recent => const _RecentList(),
            },
          ],
        ),
      ),
    );
  }

  Widget _photo() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      AppCard(
        color: AppColors.container,
        padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
        child: Column(
          children: [
            const Icon(
              Icons.restaurant,
              size: 40,
              color: AppColors.onContainer,
            ),
            const SizedBox(height: 12),
            Text(
              'Fit the whole plate in the photo',
              style: AppText.section.copyWith(color: AppColors.onContainer),
            ),
            const SizedBox(height: 4),
            Text(
              'Good light helps. SpotOn counts the pieces and estimates the calories.',
              textAlign: TextAlign.center,
              style: AppText.caption.copyWith(color: AppColors.onContainer),
            ),
          ],
        ),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _note,
        textCapitalization: TextCapitalization.sentences,
        decoration: const InputDecoration(
          labelText: 'Add a note (optional)',
          hintText: "e.g. ate only 2 idlis",
        ),
      ),
      const SizedBox(height: 16),
      PrimaryButton(
        label: 'Take photo',
        icon: Icons.photo_camera,
        onPressed: () => _pick(camera: true),
      ),
      const SizedBox(height: 8),
      SecondaryButton(
        label: 'Choose from gallery',
        icon: Icons.photo_library_outlined,
        onPressed: () => _pick(camera: false),
      ),
    ],
  );

  Widget _type() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      TextField(
        controller: _typed,
        minLines: 3,
        maxLines: 6,
        textCapitalization: TextCapitalization.sentences,
        onChanged: (_) => setState(() {}),
        decoration: const InputDecoration(
          labelText: 'What did you eat?',
          hintText: '6 boiled eggs and 2 chapatis with dal',
          alignLabelWithHint: true,
        ),
      ),
      const SizedBox(height: 8),
      Text(
        'Include how many of each. SpotOn estimates the rest and you check it before saving.',
        style: AppText.caption,
      ),
      const SizedBox(height: 16),
      PrimaryButton(
        label: 'Analyze',
        onPressed: _typed.text.trim().isEmpty
            ? null
            : () => _analyze(note: _typed.text.trim()),
      ),
    ],
  );
}

class _RecentList extends ConsumerWidget {
  const _RecentList();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final favs = ref.watch(favouriteMealsProvider);
    final recent = ref.watch(recentMealsProvider);
    if (favs.isLoading || recent.isLoading) {
      return const Padding(
        padding: EdgeInsets.all(32),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    final favourites = favs.value ?? const <Meal>[];
    final favIds = favourites.map((m) => m.id).toSet();
    final others = (recent.value ?? const <Meal>[])
        .where((m) => !favIds.contains(m.id))
        .toList();
    if (favourites.isEmpty && others.isEmpty) {
      return const EmptyState(
        icon: Icons.history,
        message: 'Meals you log show up here, so you can log them again in one tap. Mark a meal ⭐ to keep it at the top.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (favourites.isNotEmpty) ...[
          const SectionTitle('Favourites'),
          const SizedBox(height: 8),
          for (final m in favourites) _row(context, ref, m),
        ],
        if (others.isNotEmpty) ...[
          const SizedBox(height: 8),
          const SectionTitle('Recent'),
          const SizedBox(height: 8),
          for (final m in others) _row(context, ref, m),
        ],
      ],
    );
  }

  Widget _row(BuildContext context, WidgetRef ref, Meal m) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: AppCard(
      padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  m.summary,
                  style: AppText.labelBold,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '${slotLabel(m.slot)} · ${fmtInt(m.totals.kcal)} kcal · ${fmtNum(m.totals.protein)} g protein',
                  style: AppText.caption,
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          TextButton(
            onPressed: () async {
              try {
                await ref.read(apiProvider).repeatMeal(m.id);
                ref.read(dataVersion.notifier).bump();
                if (!context.mounted) return;
                showToast(context, 'Logged again');
                context.go('/today');
              } on ApiException catch (e) {
                if (context.mounted) showToast(context, e.message);
              }
            },
            child: const Text('Log'),
          ),
        ],
      ),
    ),
  );
}
