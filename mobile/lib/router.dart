import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import 'core/providers.dart';
import 'features/auth/auth_screens.dart';
import 'features/coach/coach_screen.dart';
import 'features/log/capture_screen.dart';
import 'features/log/review_screens.dart';
import 'features/me/me_screens.dart';
import 'features/onboarding/onboarding.dart';
import 'features/progress/progress_screen.dart';
import 'features/shell/app_shell.dart';
import 'features/today/today_screen.dart';

final _rootKey = GlobalKey<NavigatorState>(debugLabel: 'root');

/// Where each sign-in state is allowed to be. The router re-checks whenever the session changes.
String? redirectFor(AuthStatus status, String location) {
  final isAuth =
      location == '/welcome' ||
      location == '/sign-in' ||
      location == '/sign-up';
  final isOnboarding = location.startsWith('/onboarding');
  switch (status) {
    case AuthStatus.checking:
    case AuthStatus.unreachable:
      return location == '/splash' ? null : '/splash';
    case AuthStatus.signedOut:
      return isAuth ? null : '/welcome';
    case AuthStatus.onboarding:
      return isOnboarding ? null : '/onboarding/goal';
    case AuthStatus.ready:
      return (location == '/splash' || isAuth || isOnboarding)
          ? '/today'
          : null;
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(sessionProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);

  GoRoute full(
    String path,
    Widget Function(BuildContext, GoRouterState) builder,
  ) => GoRoute(path: path, parentNavigatorKey: _rootKey, builder: builder);

  return GoRouter(
    navigatorKey: _rootKey,
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) =>
        redirectFor(ref.read(sessionProvider).status, state.matchedLocation),
    routes: [
      GoRoute(path: '/splash', builder: (_, _) => const SplashScreen()),
      GoRoute(path: '/welcome', builder: (_, _) => const WelcomeScreen()),
      GoRoute(path: '/sign-in', builder: (_, _) => const SignInScreen()),
      GoRoute(path: '/sign-up', builder: (_, _) => const SignUpScreen()),
      GoRoute(path: '/onboarding/goal', builder: (_, _) => const GoalScreen()),
      GoRoute(
        path: '/onboarding/about',
        builder: (_, _) => const AboutScreen(),
      ),
      GoRoute(
        path: '/onboarding/activity',
        builder: (_, _) => const ActivityScreen(),
      ),
      GoRoute(path: '/onboarding/plan', builder: (_, _) => const PlanScreen()),
      StatefulShellRoute.indexedStack(
        builder: (_, _, shell) => AppShell(shell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(path: '/today', builder: (_, _) => const TodayScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/progress',
                builder: (_, _) => const ProgressScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(path: '/coach', builder: (_, _) => const CoachScreen()),
            ],
          ),
          StatefulShellBranch(
            routes: [GoRoute(path: '/me', builder: (_, _) => const MeScreen())],
          ),
        ],
      ),
      full(
        '/log',
        (_, state) => CaptureScreen(
          initialMode: state.uri.queryParameters['mode'] == 'type'
              ? CaptureMode.type
              : CaptureMode.photo,
        ),
      ),
      full('/log/analyzing', (_, _) => const AnalyzingScreen()),
      full('/log/review', (_, _) => const ReviewScreen()),
      full('/me/profile', (_, _) => const EditProfileScreen()),
      full('/me/foods', (_, _) => const MyFoodsScreen()),
      full('/me/rules', (_, _) => const RulesScreen()),
      full('/me/remembered', (_, _) => const RememberedScreen()),
      full('/me/data', (_, _) => const DataScreen()),
      full('/me/delete', (_, _) => const DeleteAccountScreen()),
    ],
  );
});
