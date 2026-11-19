import 'dart:async';
import 'dart:convert';

import 'models.dart';

/// One Server-Sent Event: `event: name` + `data: {...}` separated by a blank line.
class SseEvent {
  const SseEvent(this.name, this.data);
  final String name;
  final String data;
}

/// Parses a byte stream of Server-Sent Events. Handles chunks that split lines or
/// events anywhere, multi-byte characters across chunks, and `\r\n` line endings.
Stream<SseEvent> parseSse(Stream<List<int>> bytes) async* {
  String? event;
  final data = <String>[];
  await for (final line
      in bytes
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter())) {
    if (line.isEmpty) {
      if (event != null || data.isNotEmpty) {
        yield SseEvent(event ?? 'message', data.join('\n'));
      }
      event = null;
      data.clear();
    } else if (line.startsWith('event:')) {
      event = line.substring(6).trim();
    } else if (line.startsWith('data:')) {
      data.add(line.substring(5).trimLeft());
    } // comments (":") and unknown fields are ignored
  }
  if (event != null || data.isNotEmpty) {
    yield SseEvent(event ?? 'message', data.join('\n'));
  }
}

/// Turns the coach's SSE events into typed [CoachEvent]s.
Stream<CoachEvent> coachEvents(Stream<List<int>> bytes) async* {
  await for (final e in parseSse(bytes)) {
    final Map<String, dynamic> d = e.data.isEmpty
        ? const {}
        : (jsonDecode(e.data) as Map).cast<String, dynamic>();
    switch (e.name) {
      case 'status':
        yield CoachStatus((d['tool'] as String?) ?? '');
      case 'token':
        yield CoachToken((d['text'] as String?) ?? '');
      case 'done':
        yield CoachDone(
          (d['reply'] as String?) ?? '',
          safety: d['safety'] as String?,
        );
      case 'error':
        yield CoachFailed(
          (d['message'] as String?) ?? 'The coach is unavailable, try again.',
        );
    }
  }
}
