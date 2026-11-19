import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/models.dart';
import '../../ui/markdown_text.dart';
import '../../ui/theme.dart';
import '../../ui/widgets.dart';
import 'coach_state.dart';
import 'suggestions_sheet.dart';

/// Friendly names for what the coach is checking while it works.
const _toolLabels = {
  'get_today': "today's numbers",
  'get_targets': 'your targets',
  'estimate_food': 'the food',
  'simulate_add': 'what that would do',
  'suggest_meal': 'meal ideas',
  'get_rules': 'your rules',
  'get_my_foods': 'your foods',
  'get_progress': 'your progress',
  'get_history': 'your history',
};

class CoachScreen extends ConsumerStatefulWidget {
  const CoachScreen({super.key});
  @override
  ConsumerState<CoachScreen> createState() => _CoachScreenState();
}

class _CoachScreenState extends ConsumerState<CoachScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback(
      (_) => ref.read(coachProvider.notifier).load(),
    );
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _send([String? text]) {
    final t = (text ?? _input.text).trim();
    if (t.isEmpty) return;
    _input.clear();
    setState(() {});
    ref.read(coachProvider.notifier).send(t);
  }

  void _toBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(
      coachProvider.select(
        (s) =>
            s.messages.length +
            (s.messages.isEmpty ? 0 : s.messages.last.content.length),
      ),
      (_, _) => _toBottom(),
    );
    final c = ref.watch(coachProvider);
    return SafeArea(
      bottom: false,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Semantics(
                        header: true,
                        child: Text('Coach', style: AppText.title),
                      ),
                      Text(
                        "Today's chat. Answers use your real numbers.",
                        style: AppText.caption,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: c.messages.isEmpty
                ? Center(
                    // Scrolls, so the message stays readable at the largest text sizes.
                    child: !c.loaded
                        ? const CircularProgressIndicator()
                        : SingleChildScrollView(
                            child: EmptyState(
                              icon: Icons.forum_outlined,
                              message: c.error ?? 'Ask anything about today, like "Can I have tea now?" or "What should I order at a biryani place?"',
                            ),
                          ),
                  )
                : ListView.separated(
                    controller: _scroll,
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                    itemCount: c.messages.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (_, i) => _Bubble(
                      message: c.messages[i],
                      typing:
                          c.sending &&
                          i == c.messages.length - 1 &&
                          c.messages[i].content.isEmpty,
                      status: c.status,
                    ),
                  ),
          ),
          if (c.error != null && c.messages.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
              child: InfoBanner(c.error!, kind: BannerKind.error),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  AppChip(
                    label: 'Can I have tea now?',
                    onTap: c.sending
                        ? null
                        : () => _send('Can I have tea now?'),
                  ),
                  const SizedBox(width: 8),
                  AppChip(
                    label: 'What should I eat next?',
                    icon: Icons.restaurant_menu,
                    onTap: () => showSuggestionsSheet(context),
                  ),
                  const SizedBox(width: 8),
                  AppChip(
                    label: "How's my week?",
                    onTap: c.sending
                        ? null
                        : () => _send("How's my week going?"),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 8, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    minLines: 1,
                    maxLines: 4,
                    maxLength: 2000,
                    buildCounter: (
                      _, {
                      required currentLength,
                      required isFocused,
                      maxLength,
                    }) => null,
                    textCapitalization: TextCapitalization.sentences,
                    onChanged: (_) => setState(() {}),
                    onSubmitted: (_) => _send(),
                    decoration: const InputDecoration(
                      hintText: 'Ask your coach',
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 14,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                IconButton.filled(
                  tooltip: 'Send',
                  onPressed: c.sending || _input.text.trim().isEmpty
                      ? null
                      : _send,
                  icon: const Icon(Icons.arrow_upward),
                  style: IconButton.styleFrom(
                    minimumSize: const Size(AppSpace.minTap, AppSpace.minTap),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message, required this.typing, this.status});
  final ChatMessage message;
  final bool typing;
  final String? status;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width * 0.85;
    if (message.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: width),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: const BoxDecoration(
              color: AppColors.primary,
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(4),
              ),
            ),
            child: Text(
              message.content,
              style: AppText.body.copyWith(color: AppColors.onPrimary),
            ),
          ),
        ),
      );
    }
    final safety = message.safety;
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: width),
        child: Semantics(
          liveRegion: typing,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: safety ? AppColors.infoBg : AppColors.surface,
              border: Border.all(
                color: safety ? AppColors.infoBg : AppColors.outline,
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
                bottomRight: Radius.circular(18),
                bottomLeft: Radius.circular(4),
              ),
            ),
            child: typing
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 10),
                      Flexible(
                        child: Text(
                          status == null
                              ? 'Thinking…'
                              : 'Checking ${_toolLabels[status] ?? 'your data'}…',
                          style: AppText.caption,
                        ),
                      ),
                    ],
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (safety) ...[
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(
                              Icons.favorite_border,
                              size: 16,
                              color: AppColors.info,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              'Please read this',
                              style: AppText.labelBold.copyWith(
                                color: AppColors.info,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                      ],
                      MarkdownText(
                        message.content,
                        style: AppText.body.copyWith(
                          color: safety ? AppColors.info : AppColors.text,
                        ),
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}
