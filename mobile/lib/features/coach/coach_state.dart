import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_error.dart';
import '../../core/models.dart';
import '../../core/providers.dart';

class CoachState {
  const CoachState({
    this.messages = const [],
    this.loaded = false,
    this.sending = false,
    this.status,
    this.error,
  });

  final List<ChatMessage> messages;
  final bool loaded, sending;

  /// "Checking get today..." while the coach looks something up.
  final String? status, error;

  CoachState copyWith({
    List<ChatMessage>? messages,
    bool? loaded,
    bool? sending,
    String? status,
    String? error,
    bool clearStatus = false,
    bool clearError = false,
  }) => CoachState(
    messages: messages ?? this.messages,
    loaded: loaded ?? this.loaded,
    sending: sending ?? this.sending,
    status: clearStatus ? null : (status ?? this.status),
    error: clearError ? null : (error ?? this.error),
  );
}

/// Today's coach conversation. One thread per day, kept on the server.
class CoachNotifier extends Notifier<CoachState> {
  @override
  CoachState build() => const CoachState();

  static String threadId([DateTime? now]) {
    final d = now ?? DateTime.now();
    return '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
  }

  Future<void> load() async {
    if (state.loaded || state.sending) return;
    try {
      final history = await ref.read(apiProvider).coachThread(threadId());
      state = state.copyWith(messages: history, loaded: true, clearError: true);
    } on ApiException catch (e) {
      // No history yet (or the AI isn't configured) is not an error for the user.
      state = state.copyWith(
        loaded: true,
        error: e.code == 'ai_not_configured' ? e.message : null,
      );
    }
  }

  Future<void> send(String text) async {
    final message = text.trim();
    if (message.isEmpty || state.sending) return;
    final base = [
      ...state.messages,
      ChatMessage(role: 'user', content: message),
    ];
    state = state.copyWith(
      messages: [
        ...base,
        const ChatMessage(role: 'assistant', content: ''),
      ],
      sending: true,
      clearError: true,
      clearStatus: true,
    );
    var reply = '';
    var failed = false;
    try {
      await for (final e
          in ref.read(apiProvider).coachStream(message, threadId())) {
        switch (e) {
          case CoachStatus(:final tool):
            state = state.copyWith(status: tool);
          case CoachToken(:final text):
            reply += text;
            state = state.copyWith(
              messages: [
                ...base,
                ChatMessage(role: 'assistant', content: reply),
              ],
              clearStatus: true,
            );
          case CoachDone(reply: final full, :final safety):
            reply = full.isNotEmpty ? full : reply;
            state = state.copyWith(
              messages: [
                ...base,
                ChatMessage(
                  role: 'assistant',
                  content: reply,
                  safety: safety != null,
                ),
              ],
            );
          case CoachFailed(:final message):
            failed = true;
            state = state.copyWith(error: message);
        }
      }
    } on ApiException catch (e) {
      failed = true;
      state = state.copyWith(error: e.message);
    } catch (_) {
      failed = true;
      state = state.copyWith(error: ApiException.network().message);
    }
    if (failed && reply.isEmpty) {
      state = state.copyWith(messages: base); // drop the empty reply bubble
    }
    state = state.copyWith(sending: false, clearStatus: true);
  }
}

final coachProvider = NotifierProvider<CoachNotifier, CoachState>(
  CoachNotifier.new,
);
