import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../api_error.dart';
import '../models.dart';
import '../sse.dart';
import '../token_store.dart';
import 'spoton_api.dart';

/// [SpotOnApi] over HTTP (Dio).
///
/// Sessions: every request carries the 15-minute access token. On a 401 the client
/// rotates the refresh token once (concurrent requests share one refresh) and retries.
/// If the refresh is rejected the stored tokens are cleared and [onSessionExpired] runs;
/// a network failure during refresh keeps the session (the user is just offline).
class HttpSpotOnApi implements SpotOnApi {
  HttpSpotOnApi({
    required String baseUrl,
    required TokenStore tokens,
    Dio? dio,
    this.onSessionExpired,
  }) : _tokens = tokens, // ignore: prefer_initializing_formals
       _dio = dio ?? Dio() {
    _dio.options
      ..baseUrl = baseUrl
      ..connectTimeout = const Duration(seconds: 10)
      ..sendTimeout = const Duration(seconds: 60)
      ..receiveTimeout = const Duration(seconds: 60)
      ..validateStatus = (_) => true; // statuses are handled below
  }

  final Dio _dio;
  final TokenStore _tokens;
  final void Function()? onSessionExpired;
  Future<bool>? _refreshing;

  void close() => _dio.close();

  // --- plumbing -----------------------------------------------------------------------

  Future<bool> _refresh() =>
      _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);

  Future<bool> _doRefresh() async {
    final t = await _tokens.read();
    if (t == null) return false;
    final Response<dynamic> r;
    try {
      r = await _dio.post<dynamic>(
        '/v1/auth/refresh',
        data: {'refresh_token': t.refreshToken},
      );
    } on DioException {
      throw ApiException.network();
    }
    if (r.statusCode != 200) return false;
    await _tokens.write(
      AuthTokens.fromJson((r.data as Map).cast<String, dynamic>()),
    );
    return true;
  }

  Future<void> _expire() async {
    await _tokens.clear();
    onSessionExpired?.call();
  }

  Future<Response<dynamic>> _once(
    String method,
    String path, {
    Object? data,
    Map<String, dynamic>? query,
    Map<String, String>? headers,
    bool auth = true,
    ResponseType? responseType,
  }) async {
    final h = <String, String>{...?headers};
    if (auth) {
      final t = await _tokens.read();
      if (t != null) h['Authorization'] = 'Bearer ${t.accessToken}';
    }
    try {
      return await _dio.request<dynamic>(
        path,
        data: data,
        queryParameters: query,
        options: Options(
          method: method,
          headers: h,
          responseType: responseType,
        ),
      );
    } on DioException {
      throw ApiException.network();
    }
  }

  ApiException _toException(int status, Object? body) {
    try {
      final map = body is String ? jsonDecode(body) : body;
      final err = (map as Map)['error'] as Map;
      return ApiException(
        status: status,
        code: (err['code'] as String?) ?? 'error',
        message: (err['message'] as String?) ?? 'Something went wrong.',
        requestId: err['request_id'] as String?,
      );
    } catch (_) {
      return ApiException(
        status: status,
        code: 'error',
        message: 'Something went wrong (HTTP $status).',
      );
    }
  }

  /// The error body as JSON text, whether the request asked for JSON, bytes or a stream.
  Future<Object?> _errorBody(Object? data) async {
    if (data is ResponseBody) {
      final bytes = <int>[];
      await for (final chunk in data.stream) {
        bytes.addAll(chunk);
      }
      return utf8.decode(bytes, allowMalformed: true);
    }
    if (data is Uint8List) return utf8.decode(data, allowMalformed: true);
    return data;
  }

  Future<Response<dynamic>> _send(
    String method,
    String path, {
    Object? data,
    Map<String, dynamic>? query,
    Map<String, String>? headers,
    bool auth = true,
    ResponseType? responseType,
  }) async {
    Future<Response<dynamic>> go() => _once(
      method,
      path,
      data: data,
      query: query,
      headers: headers,
      auth: auth,
      responseType: responseType,
    );

    var r = await go();
    var body = (r.statusCode ?? 0) >= 400 ? await _errorBody(r.data) : null;
    // Only the API's token-problem answer means "session expired". Other 401s on a signed-in
    // request (like "Incorrect password" when deleting the account) are ordinary errors and
    // must not sign the user out.
    if (r.statusCode == 401 && auth && _isTokenProblem(body)) {
      if (await _refresh()) {
        r = await go();
        body = (r.statusCode ?? 0) >= 400 ? await _errorBody(r.data) : null;
      }
      if (r.statusCode == 401 && _isTokenProblem(body)) {
        await _expire();
        throw ApiException.sessionExpired();
      }
    }
    final status = r.statusCode ?? 0;
    if (status >= 400) throw _toException(status, body);
    return r;
  }

  /// The error code in the API's envelope, or null if the body isn't one.
  static String? _errorCode(Object? body) {
    try {
      final map = body is String ? jsonDecode(body) : body;
      return ((map as Map)['error'] as Map)['code'] as String?;
    } catch (_) {
      return null;
    }
  }

  /// `unauthorized` is what the API says for a bad, expired or missing access token. An
  /// answer that isn't an envelope at all (a proxy, say) is treated the same way.
  static bool _isTokenProblem(Object? body) {
    final code = _errorCode(body);
    return code == null || code == 'unauthorized';
  }

  Future<dynamic> _json(
    String method,
    String path, {
    Object? data,
    Map<String, dynamic>? query,
    Map<String, String>? headers,
    bool auth = true,
  }) async {
    final r = await _send(
      method,
      path,
      data: data,
      query: query,
      headers: headers,
      auth: auth,
    );
    return r.data;
  }

  List<Map<String, dynamic>> _list(dynamic data) =>
      (data as List).map((e) => (e as Map).cast<String, dynamic>()).toList();

  static String _date(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  // --- session ----------------------------------------------------------------------

  @override
  Future<void> ping() async {
    await _json('GET', '/healthz', auth: false);
  }

  @override
  Future<bool> get hasSession async => (await _tokens.read()) != null;

  Future<void> _storeTokens(dynamic data) =>
      _tokens.write(AuthTokens.fromJson((data as Map).cast<String, dynamic>()));

  @override
  Future<void> register(String email, String password) async => _storeTokens(
    await _json(
      'POST',
      '/v1/auth/register',
      data: {'email': email, 'password': password},
      auth: false,
    ),
  );

  @override
  Future<void> login(String email, String password) async => _storeTokens(
    await _json(
      'POST',
      '/v1/auth/login',
      data: {'email': email, 'password': password},
      auth: false,
    ),
  );

  @override
  Future<void> logout() async {
    final t = await _tokens.read();
    try {
      if (t != null) {
        await _json(
          'POST',
          '/v1/auth/logout',
          data: {'refresh_token': t.refreshToken},
        );
      }
    } on ApiException {
      // Signing out on this phone is what matters; the server session expires on its own.
    } finally {
      await _tokens.clear();
    }
  }

  @override
  Future<void> deleteAccount(String password) async {
    await _json('DELETE', '/v1/account', data: {'password': password});
    await _tokens.clear();
  }

  @override
  Future<UserInfo> me() async =>
      UserInfo.fromJson((await _json('GET', '/v1/me') as Map).cast());

  // --- profile ------------------------------------------------------------------------

  @override
  Future<Profile?> profile() async {
    try {
      return Profile.fromJson(
        (await _json('GET', '/v1/profile') as Map).cast(),
      );
    } on ApiException catch (e) {
      if (e.code == 'profile_not_found') return null;
      rethrow;
    }
  }

  @override
  Future<Profile> saveProfile(ProfileInput input) async => Profile.fromJson(
    (await _json('PUT', '/v1/profile', data: input.toJson()) as Map).cast(),
  );

  // --- today and tracking -------------------------------------------------------------

  @override
  Future<Today> today({DateTime? day}) async => Today.fromJson(
    (await _json(
      'GET',
      '/v1/today',
      query: day == null ? null : {'date': _date(day)},
    ) as Map).cast(),
  );

  @override
  Future<void> addWater(int ml, {DateTime? day}) => _json(
    'POST',
    '/v1/water',
    data: {'ml': ml, if (day != null) 'day': _date(day)},
  );

  @override
  Future<void> setSteps(DateTime day, int steps) =>
      _json('PUT', '/v1/steps/${_date(day)}', data: {'steps': steps});

  @override
  Future<void> logWeight(double kg, {DateTime? day}) => _json(
    'POST',
    '/v1/weights',
    data: {'kg': kg, if (day != null) 'day': _date(day)},
  );

  @override
  Future<List<WorkoutResult>> logWorkout(String text, {DateTime? day}) async =>
      _list(
        await _json(
          'POST',
          '/v1/workouts',
          data: {'text': text, if (day != null) 'day': _date(day)},
        ),
      ).map(WorkoutResult.fromJson).toList();

  @override
  Future<History> history(String period) async => History.fromJson(
    (await _json('GET', '/v1/history', query: {'period': period}) as Map)
        .cast(),
  );

  // --- meals --------------------------------------------------------------------------

  @override
  Future<Draft> analyze({String? note, UploadImage? image}) async {
    final form = FormData();
    if (note != null && note.trim().isNotEmpty) {
      form.fields.add(MapEntry('note', note.trim()));
    }
    if (image != null) {
      form.files.add(
        MapEntry(
          'image',
          MultipartFile.fromBytes(
            image.bytes,
            filename: image.name,
            contentType: DioMediaType.parse(image.mimeType),
          ),
        ),
      );
    }
    return Draft.fromJson(
      (await _json('POST', '/v1/meals/analyze', data: form) as Map).cast(),
    );
  }

  @override
  Future<Meal> saveMeal({
    required String slot,
    required List<FoodItem> items,
    required String source,
    required String idempotencyKey,
    String? note,
    bool isFavourite = false,
    DateTime? eatenAt,
  }) async {
    final body = {
      'slot': slot,
      'items': items.map((i) => i.toSaveJson()).toList(),
      'source': source,
      'is_favourite': isFavourite,
      if (note != null && note.trim().isNotEmpty) 'note': note.trim(),
      if (eatenAt != null) 'eaten_at': eatenAt.toUtc().toIso8601String(),
    };
    final data = await _json(
      'POST',
      '/v1/meals',
      data: body,
      headers: {'Idempotency-Key': idempotencyKey},
    );
    return Meal.fromJson((data as Map).cast());
  }

  @override
  Future<List<Meal>> meals({DateTime? day}) async => _list(
    await _json(
      'GET',
      '/v1/meals',
      query: day == null ? null : {'date': _date(day)},
    ),
  ).map(Meal.fromJson).toList();

  @override
  Future<List<Meal>> recentMeals() async =>
      _list(await _json('GET', '/v1/meals/recent')).map(Meal.fromJson).toList();

  @override
  Future<List<Meal>> favouriteMeals() async =>
      _list(await _json('GET', '/v1/meals/favourites'))
          .map(Meal.fromJson)
          .toList();

  @override
  Future<Meal> setFavourite(String mealId, bool value) async => Meal.fromJson(
    (await _json(
      'PATCH',
      '/v1/meals/$mealId',
      data: {'is_favourite': value},
    ) as Map).cast(),
  );

  @override
  Future<Meal> updateMeal(
    String mealId, {
    required String slot,
    required List<FoodItem> items,
  }) async => Meal.fromJson(
    (await _json(
      'PATCH',
      '/v1/meals/$mealId',
      data: {'slot': slot, 'items': items.map((i) => i.toSaveJson()).toList()},
    ) as Map).cast(),
  );

  @override
  Future<Meal> repeatMeal(String mealId) async => Meal.fromJson(
    (await _json('POST', '/v1/meals/$mealId/repeat') as Map).cast(),
  );

  @override
  Future<void> deleteMeal(String mealId) =>
      _json('DELETE', '/v1/meals/$mealId');

  // --- coach --------------------------------------------------------------------------

  @override
  Future<Suggestions> suggestions(String mode) async => Suggestions.fromJson(
    (await _json('GET', '/v1/suggestions', query: {'mode': mode}) as Map)
        .cast(),
  );

  @override
  Stream<CoachEvent> coachStream(String message, String threadId) async* {
    final r =
        await _send(
          'POST',
          '/v1/coach/messages',
          data: {'message': message, 'thread_id': threadId},
          headers: {'Accept': 'text/event-stream'},
          responseType: ResponseType.stream,
        ).catchError(
          (Object e) => throw e is ApiException ? e : ApiException.network(),
        );
    final body = r.data as ResponseBody;
    yield* coachEvents(body.stream);
  }

  @override
  Future<List<ChatMessage>> coachThread(String threadId) async {
    final data = (await _json('GET', '/v1/coach/threads/$threadId') as Map)
        .cast<String, dynamic>();
    return _list(data['messages'])
        .map(
          (m) => ChatMessage(
            role: m['role'] as String,
            content: m['content'] as String,
          ),
        )
        .toList();
  }

  // --- my foods, rules, remembered foods ------------------------------------------------

  @override
  Future<List<MyFood>> myFoods() async =>
      _list(await _json('GET', '/v1/my-foods')).map(MyFood.fromJson).toList();

  @override
  Future<List<MyFood>> saveMyFoods(List<MyFood> foods) async => _list(
    await _json(
      'PUT',
      '/v1/my-foods',
      data: foods.map((f) => f.toJson()).toList(),
    ),
  ).map(MyFood.fromJson).toList();

  @override
  Future<List<FoodRule>> rules() async =>
      _list(await _json('GET', '/v1/rules')).map(FoodRule.fromJson).toList();

  @override
  Future<FoodRule> parseRule(String text) async => FoodRule.fromJson(
    (await _json('POST', '/v1/rules/parse', data: {'text': text}) as Map)
        .cast(),
  );

  @override
  Future<FoodRule> saveRule(FoodRule rule) async => FoodRule.fromJson(
    (await _json('POST', '/v1/rules', data: rule.toJson()) as Map).cast(),
  );

  @override
  Future<void> deleteRule(String id) => _json('DELETE', '/v1/rules/$id');

  @override
  Future<List<RememberedFood>> rememberedFoods() async =>
      _list(await _json('GET', '/v1/food-memory'))
          .map(RememberedFood.fromJson)
          .toList();

  @override
  Future<void> forgetFood(String id) => _json('DELETE', '/v1/food-memory/$id');

  // --- progress -----------------------------------------------------------------------

  @override
  Future<Progress> progress() async =>
      Progress.fromJson((await _json('GET', '/v1/progress') as Map).cast());

  @override
  Future<WeeklyReview> weeklyReview() async => WeeklyReview.fromJson(
    (await _json('GET', '/v1/reviews/weekly') as Map).cast(),
  );

  @override
  Future<void> decideReview(String id, {required bool accept}) => _json(
    'POST',
    '/v1/reviews/$id/decision',
    data: {'decision': accept ? 'accept' : 'reject'},
  );

  @override
  Future<void> logMeasurement({
    double? waistCm,
    double? hipCm,
    double? bodyFatPct,
  }) => _json(
    'POST',
    '/v1/measurements',
    data: {'waist_cm': ?waistCm, 'hip_cm': ?hipCm, 'body_fat_pct': ?bodyFatPct},
  );

  // --- data ---------------------------------------------------------------------------

  @override
  Future<Uint8List> export(String format) async {
    final r = await _send(
      'GET',
      '/v1/export',
      query: {'format': format},
      responseType: ResponseType.bytes,
    );
    return Uint8List.fromList((r.data as List).cast<int>());
  }
}
