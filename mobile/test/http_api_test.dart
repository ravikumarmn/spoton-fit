import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:spoton/core/api/http_api.dart';
import 'package:spoton/core/api/spoton_api.dart';
import 'package:spoton/core/api_error.dart';
import 'package:spoton/core/models.dart';
import 'package:spoton/core/token_store.dart';

import 'support.dart';

typedef Handler = FutureOr<ResponseBody> Function(RequestOptions o);

/// Answers requests from a script instead of the network, and records them.
class ScriptedAdapter implements HttpClientAdapter {
  ScriptedAdapter(this.handler);
  final Handler handler;
  final requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return handler(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody json(Object body, [int status = 200]) => ResponseBody.fromString(
  jsonEncode(body),
  status,
  headers: {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  },
);

Map<String, dynamic> tokens(String a, String r) => {
  'access_token': a,
  'refresh_token': r,
  'token_type': 'bearer',
  'expires_in': 900,
};

ResponseBody envelope(int status, String code, String message) => json({
  'error': {'code': code, 'message': message, 'request_id': 'rid1'},
}, status);

({
  HttpSpotOnApi api,
  ScriptedAdapter adapter,
  MemoryTokenStore store,
  List<String> expired,
})
make(Handler handler, {AuthTokens? start}) {
  final adapter = ScriptedAdapter(handler);
  final dio = Dio()..httpClientAdapter = adapter;
  final store = MemoryTokenStore();
  if (start != null) store.write(start);
  final expired = <String>[];
  final api = HttpSpotOnApi(
    baseUrl: 'http://test',
    tokens: store,
    dio: dio,
    onSessionExpired: () => expired.add('expired'),
  );
  return (api: api, adapter: adapter, store: store, expired: expired);
}

void main() {
  const old = AuthTokens(
    accessToken: 'old-access',
    refreshToken: 'old-refresh',
  );

  test(
    'login stores the tokens, then requests carry the bearer token',
    () async {
      final t = make(
        (o) => o.path == '/v1/auth/login'
            ? json(tokens('a1', 'r1'))
            : json(fixtureMap('me')),
      );
      await t.api.login('a@b.co', 'pass-1234');
      expect((await t.store.read())!.accessToken, 'a1');
      await t.api.me();
      expect(t.adapter.requests.last.headers['Authorization'], 'Bearer a1');
      expect(t.adapter.requests.first.data, {
        'email': 'a@b.co',
        'password': 'pass-1234',
      });
      expect(
        t.adapter.requests.first.headers.containsKey('Authorization'),
        isFalse,
      ); // login is public
    },
  );

  test(
    'an expired access token is refreshed once and the request retried',
    () async {
      var meCalls = 0;
      final t = make((o) {
        if (o.path == '/v1/auth/refresh') {
          return json(tokens('new-access', 'new-refresh'));
        }
        meCalls++;
        return o.headers['Authorization'] == 'Bearer new-access'
            ? json(fixtureMap('me'))
            : envelope(401, 'unauthorized', 'Invalid or expired token');
      }, start: old);
      final me = await t.api.me();
      expect(me.email, 'fixture@example.com');
      expect(meCalls, 2);
      final refresh = t.adapter.requests.singleWhere(
        (r) => r.path == '/v1/auth/refresh',
      );
      expect(refresh.data, {'refresh_token': 'old-refresh'});
      expect(
        (await t.store.read())!.refreshToken,
        'new-refresh',
      ); // rotated and saved
    },
  );

  test('simultaneous requests share ONE refresh (a rotated token can be used only once)', () async {
    final t = make((o) async {
      if (o.path == '/v1/auth/refresh') {
        await Future<void>.delayed(const Duration(milliseconds: 30));
        return json(tokens('new-access', 'new-refresh'));
      }
      return o.headers['Authorization'] == 'Bearer new-access'
          ? json(fixtureMap('me'))
          : envelope(401, 'unauthorized', 'expired');
    }, start: old);
    await Future.wait([t.api.me(), t.api.me(), t.api.me()]);
    expect(
      t.adapter.requests.where((r) => r.path == '/v1/auth/refresh'),
      hasLength(1),
    );
  });

  test(
    'a rejected refresh token ends the session: tokens cleared, callback fired',
    () async {
      final t = make(
        (o) => o.path == '/v1/auth/refresh'
            ? envelope(401, 'invalid_refresh_token', 'reused')
            : envelope(401, 'unauthorized', 'expired'),
        start: old,
      );
      await expectLater(
        t.api.me(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.isSessionExpired,
            'isSessionExpired',
            isTrue,
          ),
        ),
      );
      expect(await t.store.read(), isNull);
      expect(t.expired, ['expired']);
    },
  );

  test('a 401 that is not a token problem (wrong password) does not sign the user out', () async {
    final t = make(
      (o) => envelope(401, 'invalid_credentials', 'Incorrect password'),
      start: old,
    );
    await expectLater(
      t.api.deleteAccount('nope'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'invalid_credentials')
            .having((e) => e.isSessionExpired, 'expired', isFalse),
      ),
    );
    expect(
      t.adapter.requests.where((r) => r.path == '/v1/auth/refresh'),
      isEmpty,
      reason: 'no refresh attempt',
    );
    expect(await t.store.read(), isNotNull, reason: 'still signed in');
    expect(t.expired, isEmpty);
  });

  test('a 401 with no API envelope (a proxy) is still treated as an expired session', () async {
    final t = make(
      (o) => o.path == '/v1/auth/refresh'
          ? envelope(401, 'invalid_refresh_token', 'x')
          : ResponseBody.fromString('Unauthorized', 401),
      start: old,
    );
    await expectLater(
      t.api.me(),
      throwsA(
        isA<ApiException>().having(
          (e) => e.isSessionExpired,
          'expired',
          isTrue,
        ),
      ),
    );
  });

  test('being offline during refresh keeps the session', () async {
    final t = make((o) {
      if (o.path == '/v1/auth/refresh') {
        throw DioException.connectionError(
          requestOptions: o,
          reason: 'offline',
        );
      }
      return envelope(401, 'unauthorized', 'expired');
    }, start: old);
    await expectLater(
      t.api.me(),
      throwsA(
        isA<ApiException>().having((e) => e.isNetwork, 'isNetwork', isTrue),
      ),
    );
    expect(await t.store.read(), isNotNull);
    expect(t.expired, isEmpty);
  });

  test('API errors keep their code, message and request id', () async {
    final t = make((o) => json(fixtureMap('error_envelope'), 401));
    await expectLater(
      t.api.login('a@b.co', 'wrong'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'invalid_credentials')
            .having((e) => e.message, 'message', 'Incorrect email or password')
            .having((e) => e.requestId, 'requestId', isNotEmpty),
      ),
    );
  });

  test('no connection becomes a friendly network error', () async {
    final t = make(
      (o) => throw DioException.connectionTimeout(
        timeout: const Duration(seconds: 1),
        requestOptions: o,
      ),
    );
    await expectLater(
      t.api.ping(),
      throwsA(
        isA<ApiException>().having(
          (e) => e.message,
          'message',
          contains("Couldn't reach SpotOn"),
        ),
      ),
    );
  });

  test('a missing profile is null, not an error', () async {
    final t = make(
      (o) => envelope(404, 'profile_not_found', 'Profile not set up'),
      start: old,
    );
    expect(await t.api.profile(), isNull);
  });

  test(
    'saving a meal sends the Idempotency-Key and the per-unit payload',
    () async {
      final t = make((o) => json(fixtureMap('meal'), 201), start: old);
      final items = Draft.fromJson(fixtureMap('draft')).items
        ..[0].source = 'edited';
      await t.api.saveMeal(
        slot: 'breakfast',
        items: items,
        source: 'photo',
        idempotencyKey: 'key-123',
        note: ' my note ',
        isFavourite: true,
      );
      final r = t.adapter.requests.single;
      expect(r.method, 'POST');
      expect(r.path, '/v1/meals');
      expect(r.headers['Idempotency-Key'], 'key-123');
      final body = r.data as Map;
      expect(body['slot'], 'breakfast');
      expect(body['source'], 'photo');
      expect(body['is_favourite'], isTrue);
      expect(body['note'], 'my note');
      final first = (body['items'] as List).first as Map;
      expect(first['quantity'], 6);
      expect(first['per_unit'], containsPair('kcal', 72));
      expect(first['source'], 'edited');
      expect(
        first.containsKey('kcal'),
        isFalse,
      ); // totals are never sent: the server computes them
    },
  );

  test('analyze uploads the photo and note as multipart', () async {
    final t = make((o) => json(fixtureMap('draft')), start: old);
    final draft = await t.api.analyze(
      note: 'ate only 2',
      image: UploadImage(
        name: 'meal.jpg',
        bytes: Uint8List.fromList([1, 2, 3]),
      ),
    );
    expect(draft.items, hasLength(2));
    final form = t.adapter.requests.single.data as FormData;
    expect(form.fields.map((e) => '${e.key}=${e.value}'), ['note=ate only 2']);
    expect(form.files.single.key, 'image');
    expect(form.files.single.value.filename, 'meal.jpg');
    expect(form.files.single.value.length, 3);
  });

  test('the coach stream is parsed from Server-Sent Events', () async {
    final raw = File('test/fixtures/coach_stream.txt').readAsBytesSync();
    final t = make((o) {
      expect(o.headers['Accept'], 'text/event-stream');
      return ResponseBody(
        Stream.value(Uint8List.fromList(raw)),
        200,
        headers: {
          Headers.contentTypeHeader: ['text/event-stream'],
        },
      );
    }, start: old);
    final events = await t.api
        .coachStream('Can I have tea now?', '2026-11-19')
        .toList();
    expect(
      events.whereType<CoachToken>().map((e) => e.text).join(),
      'Yes, have tea. You have room today.',
    );
    expect(events.last, isA<CoachDone>());
    expect((t.adapter.requests.single.data as Map)['thread_id'], '2026-11-19');
  });

  test(
    'a failed coach request throws the API error, not a broken stream',
    () async {
      final t = make(
        (o) => ResponseBody.fromString(
          jsonEncode({
            'error': {
              'code': 'ai_not_configured',
              'message': 'AI is not configured',
              'request_id': 'x',
            },
          }),
          503,
          headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          },
        ),
        start: old,
      );
      await expectLater(
        t.api.coachStream('hi', 't').toList(),
        throwsA(
          isA<ApiException>().having(
            (e) => e.code,
            'code',
            'ai_not_configured',
          ),
        ),
      );
    },
  );

  test('delete account sends the password and clears the tokens', () async {
    final t = make((o) => ResponseBody.fromString('', 204), start: old);
    await t.api.deleteAccount('right-pass');
    final r = t.adapter.requests.single;
    expect(r.method, 'DELETE');
    expect(r.path, '/v1/account');
    expect(r.data, {'password': 'right-pass'});
    expect(await t.store.read(), isNull);
  });

  test('logout clears the tokens even if the server is unreachable', () async {
    final t = make(
      (o) => throw DioException.connectionError(
        requestOptions: o,
        reason: 'offline',
      ),
      start: old,
    );
    await t.api.logout();
    expect(await t.store.read(), isNull);
  });

  test('history, today and date query parameters', () async {
    final t = make(
      (o) => o.path == '/v1/today'
          ? json(fixtureMap('today'))
          : json(fixtureMap('history_week')),
      start: old,
    );
    await t.api.today(day: DateTime(2026, 11, 5));
    expect(t.adapter.requests.last.queryParameters, {'date': '2026-11-05'});
    final h = await t.api.history('week');
    expect(h.period, 'week');
    expect(t.adapter.requests.last.queryParameters, {'period': 'week'});
  });

  test(
    'logging for a past day sends that day (and nothing for today)',
    () async {
      final t = make(
        (o) =>
            o.path == '/v1/workouts' ? json(fixtureList('workouts')) : json({}),
        start: old,
      );
      await t.api.addWater(250, day: DateTime(2026, 11, 18));
      expect(t.adapter.requests.last.data, {'ml': 250, 'day': '2026-11-18'});
      await t.api.addWater(250);
      expect(t.adapter.requests.last.data, {'ml': 250});
      await t.api.logWeight(91.5, day: DateTime(2026, 11, 18));
      expect(t.adapter.requests.last.data, {'kg': 91.5, 'day': '2026-11-18'});
      await t.api.logWorkout('15 min cycling', day: DateTime(2026, 11, 18));
      expect(t.adapter.requests.last.data, {
        'text': '15 min cycling',
        'day': '2026-11-18',
      });
    },
  );
}
