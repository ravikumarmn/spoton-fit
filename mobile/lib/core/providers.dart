import 'dart:async';

import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart' show ThemeMode;
import 'package:shared_preferences/shared_preferences.dart';

import 'api/http_api.dart';
import 'api/spoton_api.dart';
import 'api_error.dart';
import 'models.dart';
import 'token_store.dart';

// --- Configuration ----------------------------------------------------------------------

/// Set in main(); tests override it with `SharedPreferences.setMockInitialValues`.
final prefsProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('prefsProvider not overridden'),
);

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());

/// Compile-time default; override with `--dart-define=SPOTON_API_URL=https://...`.
const _defaultServer = String.fromEnvironment(
  'SPOTON_API_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

/// The SpotOn server address. On the Android emulator, 10.0.2.2 is the host computer;
/// on a real phone use the computer's Wi-Fi address (e.g. http://192.168.1.20:8000).
/// Light, dark or follow the phone (Me › Appearance). Stored on the device.
class Appearance extends Notifier<ThemeMode> {
  static const _key = 'appearance';

  @override
  ThemeMode build() => switch (ref.watch(prefsProvider).getString(_key)) {
    'light' => ThemeMode.light,
    'dark' => ThemeMode.dark,
    _ => ThemeMode.system,
  };

  Future<void> set(ThemeMode mode) async {
    await ref.read(prefsProvider).setString(_key, mode.name);
    state = mode;
  }
}

final appearanceProvider = NotifierProvider<Appearance, ThemeMode>(
  Appearance.new,
);

/// Whether people can change the server address. Off in release builds (the app ships with
/// the cloud address built in); on in development builds for testing against a local API.
/// `--dart-define=SPOTON_SERVER_PICKER=true` turns it on in a release build.
final serverPickerProvider = Provider<bool>(
  (ref) => !kReleaseMode || const bool.fromEnvironment('SPOTON_SERVER_PICKER'),
);

class ServerUrl extends Notifier<String> {
  static const _key = 'server_url';

  @override
  String build() {
    // Without the picker, an address saved by an older version is ignored, so nobody is stuck
    // on a server they can no longer change.
    if (!ref.watch(serverPickerProvider)) return _defaultServer;
    return ref.watch(prefsProvider).getString(_key) ?? _defaultServer;
  }

  Future<void> set(String url) async {
    var v = url.trim();
    while (v.endsWith('/')) {
      v = v.substring(0, v.length - 1);
    }
    await ref.read(prefsProvider).setString(_key, v);
    state = v;
  }
}

final serverUrlProvider = NotifierProvider<ServerUrl, String>(ServerUrl.new);

final apiProvider = Provider<SpotOnApi>((ref) {
  final api = HttpSpotOnApi(
    baseUrl: ref.watch(serverUrlProvider),
    tokens: ref.watch(tokenStoreProvider),
    onSessionExpired: () => ref.read(sessionProvider.notifier).expired(),
  );
  ref.onDispose(api.close);
  return api;
});

// --- Session ------------------------------------------------------------------------------

enum AuthStatus { checking, signedOut, onboarding, ready, unreachable }

class SessionState {
  const SessionState(this.status, {this.profile, this.message, this.email});
  final AuthStatus status;
  final Profile? profile;
  final String? message;
  final String? email;
}

class SessionNotifier extends Notifier<SessionState> {
  @override
  SessionState build() {
    scheduleMicrotask(restore);
    return const SessionState(AuthStatus.checking);
  }

  SpotOnApi get _api => ref.read(apiProvider);

  /// On launch: if tokens are stored, go straight in (the 30-day session).
  Future<void> restore() async {
    state = const SessionState(AuthStatus.checking);
    try {
      if (!await _api.hasSession) {
        state = const SessionState(AuthStatus.signedOut);
        return;
      }
      await _enter();
    } on ApiException catch (e) {
      state = e.isSessionExpired
          ? const SessionState(
              AuthStatus.signedOut,
              message: 'Your session expired. Please sign in again.',
            )
          : SessionState(AuthStatus.unreachable, message: e.message);
    }
  }

  Future<void> _enter() async {
    final profile = await _api.profile();
    final me = await _api.me();
    state = profile == null
        ? SessionState(AuthStatus.onboarding, email: me.email)
        : SessionState(AuthStatus.ready, profile: profile, email: me.email);
  }

  Future<void> signIn(String email, String password) async {
    await _api.login(email, password);
    await _enter();
  }

  Future<void> signUp(String email, String password) async {
    await _api.register(email, password);
    await _enter();
  }

  /// Saves the profile. During onboarding the status stays `onboarding` until
  /// [finishOnboarding], so the "Your plan" screen can be shown first.
  Future<Profile> saveProfile(ProfileInput input) async {
    final profile = await _api.saveProfile(input);
    state = SessionState(
      state.status == AuthStatus.ready
          ? AuthStatus.ready
          : AuthStatus.onboarding,
      profile: profile,
      email: state.email,
    );
    ref.read(dataVersion.notifier).bump();
    return profile;
  }

  void finishOnboarding() {
    state = SessionState(
      AuthStatus.ready,
      profile: state.profile,
      email: state.email,
    );
  }

  Future<void> signOut() async {
    await _api.logout();
    state = const SessionState(AuthStatus.signedOut);
    ref.read(dataVersion.notifier).bump();
  }

  Future<void> deleteAccount(String password) async {
    await _api.deleteAccount(password);
    state = const SessionState(
      AuthStatus.signedOut,
      message: 'Your account and all its data were deleted.',
    );
    ref.read(dataVersion.notifier).bump();
  }

  void expired() {
    state = const SessionState(
      AuthStatus.signedOut,
      message: 'Your session expired. Please sign in again.',
    );
  }
}

final sessionProvider = NotifierProvider<SessionNotifier, SessionState>(
  SessionNotifier.new,
);

// --- Data ---------------------------------------------------------------------------------

/// Bumped after any change (save a meal, add water, ...) so every screen refetches.
class DataVersion extends Notifier<int> {
  @override
  int build() => 0;
  void bump() => state++;
}

final dataVersion = NotifierProvider<DataVersion, int>(DataVersion.new);

/// Which day Today shows (null = today).
class SelectedDay extends Notifier<DateTime?> {
  @override
  DateTime? build() => null;
  void set(DateTime? day) => state = day;
}

/// When to record something logged while viewing [day] (null means today: the server uses
/// now). A past day gets the current clock time on that date, so it counts on that day.
DateTime? loggedAtFor(DateTime? day) {
  if (day == null) return null;
  final now = DateTime.now();
  return DateTime(
    day.year,
    day.month,
    day.day,
    now.hour,
    now.minute,
    now.second,
  );
}

final selectedDayProvider = NotifierProvider<SelectedDay, DateTime?>(
  SelectedDay.new,
);

final todayProvider = FutureProvider.autoDispose<Today>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).today(day: ref.watch(selectedDayProvider));
});

final mealsProvider = FutureProvider.autoDispose<List<Meal>>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).meals(day: ref.watch(selectedDayProvider));
});

final recentMealsProvider = FutureProvider.autoDispose<List<Meal>>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).recentMeals();
});

final favouriteMealsProvider = FutureProvider.autoDispose<List<Meal>>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).favouriteMeals();
});

final progressProvider = FutureProvider.autoDispose<Progress>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).progress();
});

final weeklyReviewProvider = FutureProvider.autoDispose<WeeklyReview>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).weeklyReview();
});

final historyProvider = FutureProvider.autoDispose.family<History, String>((
  ref,
  period,
) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).history(period);
});

final myFoodsProvider = FutureProvider.autoDispose<List<MyFood>>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).myFoods();
});

final rulesProvider = FutureProvider.autoDispose<List<FoodRule>>((ref) {
  ref.watch(dataVersion);
  return ref.watch(apiProvider).rules();
});

final rememberedFoodsProvider =
    FutureProvider.autoDispose<List<RememberedFood>>((ref) {
      ref.watch(dataVersion);
      return ref.watch(apiProvider).rememberedFoods();
    });

/// Runs an action, then refreshes every screen's data.
extension RefreshData on WidgetRef {
  void refreshAll() => read(dataVersion.notifier).bump();
}
