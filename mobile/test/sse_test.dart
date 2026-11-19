import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:spoton/core/models.dart';
import 'package:spoton/core/sse.dart';

Stream<List<int>> chunks(List<int> bytes, int size) async* {
  for (var i = 0; i < bytes.length; i += size) {
    yield bytes.sublist(i, i + size > bytes.length ? bytes.length : i + size);
  }
}

void main() {
  final raw = File('test/fixtures/coach_stream.txt').readAsBytesSync();

  Future<(String, CoachDone?)> collect(Stream<List<int>> s) async {
    var text = '';
    CoachDone? done;
    await for (final e in coachEvents(s)) {
      if (e is CoachToken) text += e.text;
      if (e is CoachDone) done = e;
    }
    return (text, done);
  }

  test(
    'parses the real coach stream: tokens add up to the final reply',
    () async {
      final (text, done) = await collect(Stream.value(raw));
      expect(text, 'Yes, have tea. You have room today.');
      expect(done!.reply, text);
      expect(done.safety, isNull);
    },
  );

  test('gives the same result however the bytes are chunked', () async {
    for (final size in [1, 2, 3, 7, 64, raw.length]) {
      final (text, done) = await collect(chunks(raw, size));
      expect(
        text,
        'Yes, have tea. You have room today.',
        reason: 'chunk size $size',
      );
      expect(done, isNotNull, reason: 'chunk size $size');
    }
  });

  test('keeps multi-byte characters intact when a chunk splits them', () async {
    final sse = utf8.encode(
      'event: token\ndata: {"text": "₹50 🍛"}\n\nevent: done\ndata: {"reply": "₹50 🍛", "safety": null}\n\n',
    );
    for (final size in [1, 2, 5]) {
      final (text, done) = await collect(chunks(sse, size));
      expect(text, '₹50 🍛', reason: 'chunk size $size');
      expect(done!.reply, '₹50 🍛');
    }
  });

  test(
    'handles CRLF line endings, comments and a missing final blank line',
    () async {
      final sse = utf8.encode(
        ': keep-alive\r\nevent: status\r\ndata: {"tool": "get_today"}\r\n\r\nevent: token\r\ndata: {"text": "Hi"}',
      );
      final events = await coachEvents(Stream.value(sse)).toList();
      expect(
        events[0],
        isA<CoachStatus>().having((e) => e.tool, 'tool', 'get_today'),
      );
      expect(events[1], isA<CoachToken>().having((e) => e.text, 'text', 'Hi'));
    },
  );

  test('reads safety replies and errors', () async {
    final sse = utf8.encode(
      'event: token\ndata: {"text": "See a doctor."}\n\nevent: done\ndata: {"reply": "See a doctor.", "thread_id": "t", "safety": "red_flag"}\n\n'
      'event: error\ndata: {"code": "timeout", "message": "Too slow"}\n\n',
    );
    final events = await coachEvents(Stream.value(sse)).toList();
    expect((events[1] as CoachDone).safety, 'red_flag');
    expect((events[2] as CoachFailed).message, 'Too slow');
  });
}
