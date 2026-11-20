# SpotOn mobile app (Flutter)

Android app for SpotOn (Flutter; the iOS project is generated but has never been built or tested): log a meal by photo or text, see what's left today, ask the
coach, follow your progress. A thin client over the SpotOn API (`/v1`): all nutrition maths,
rules and safety stay on the server. Plan and design decisions: [`docs/design/MOBILE_PLAN.md`](../docs/design/MOBILE_PLAN.md).

- Flutter **3.50.0** / Dart 3.14, Material via the standalone `material_ui` package (3.50 deprecated the bundled one).
- State: Riverpod · Navigation: go_router · HTTP: Dio · Charts: fl_chart · Font: Inter (bundled).
- Light theme, sage accent `#2B7A68`; every colour pair is tested against WCAG AA.

## Screens

Welcome, Sign up, Sign in · 3-step onboarding and **Your plan** · **Today** · **Log a meal** (Recent / Photo / Type) → Analyzing → **Review meal** ·
**Coach** (streaming, suggestions) · **Progress** (weekly review, weight trend, maintenance, measurements, History charts) ·
**Me** (Edit profile, My foods, Food rules, Remembered foods, Coach notes, Appearance, Change password, Privacy policy, Export, Delete account; Server address in debug builds).

## Run it

You need the SpotOn API running (see the repository README). Then, from `mobile/`:

```bash
export PATH="$HOME/development/flutter/bin:$PATH"     # wherever Flutter is installed
flutter pub get
flutter run                                           # an emulator or a connected phone
```

**Server address.** The app needs to know where the API is:

| Where the app runs | Address to use |
| --- | --- |
| Android emulator | `http://10.0.2.2:8000` (the default) |
| iOS simulator | `http://127.0.0.1:8000` |
| A real phone on the same Wi-Fi | `http://<your computer's Wi-Fi address>:8000`, with the API started as `uvicorn ... --host 0.0.0.0` |
| A hosted server | `https://...` |

In **debug builds**, set it in the app (Welcome screen → **Server address**, or Me → **Server address**; there is a
*Test connection* button), or at build time with `--dart-define=SPOTON_API_URL=https://your-server`.

**Release builds** use only the address built in with `SPOTON_API_URL` (the deploy sets the Cloud Run address). The
Server address option is hidden and any address saved by an older version is ignored, so testers can't point the app
at the wrong server. Add `--dart-define=SPOTON_SERVER_PICKER=true` to show it in a release build.

Plain `http://` works in **debug builds only** (`android/app/src/debug/AndroidManifest.xml`, iOS `NSAllowsLocalNetworking`).
Release builds need `https://`.

## Build an APK

```bash
flutter build apk --debug          # build/app/outputs/flutter-apk/app-debug.apk  (works with a local http:// server)
flutter build apk --release        # needs a real signing key first; see "Before a store release"
```

First time on a machine, you also need Java 17 and the Android SDK (platform 36, build-tools 36). Install them, then accept the licences once:
`sdkmanager --licenses`. `flutter doctor` shows what is missing.

## Tests

```bash
flutter analyze
flutter test                                          # 100+ tests, no server needed
SPOTON_E2E_URL=http://127.0.0.1:8000 SPOTON_E2E_AI=1 flutter test test/e2e_live_test.dart   # against a real API (and real Gemini)
```

- `test/contract_test.dart` checks the models against **real API responses** in `test/fixtures/`.
  Regenerate them whenever an API response changes (from the repository root):
  `PYTHONPATH=src:. uv run python scripts/gen_mobile_fixtures.py`. CI does this on every push.
- `test/app_test.dart` drives the real screens with a fake API (sign-up, onboarding, logging, editing, coach, review, delete account),
  and checks Android tap-target, label and contrast guidelines and 150% / 200% text size.
- `test/http_api_test.dart` covers sessions: token refresh (one at a time), expiry, errors, idempotency keys, uploads and streaming.
- `test/e2e_live_test.dart` is skipped unless `SPOTON_E2E_URL` is set. It creates a throwaway account and deletes it.

## Layout

```
lib/
  main.dart · app.dart · router.dart       app entry, theme, routes and sign-in guards
  core/                                    models, API client (http_api.dart), SSE parser, token storage, providers (state)
  ui/                                      theme tokens, shared components (buttons, chips, stepper, bars, ring), Markdown text
  features/
    auth/ onboarding/ today/ log/ coach/ progress/ me/ shell/
test/                                      unit, contract, widget and live end-to-end tests
```

## How it behaves

- **Sessions last 30 days.** Login tokens are kept in the iOS Keychain / Android Keystore. The 15-minute access token is refreshed
  automatically (one refresh at a time); if the refresh is rejected you are signed out.
- **Nothing is saved before you confirm.** The review screen edits counts (− / +) and per-unit values; the server recomputes all totals.
  Saving carries an `Idempotency-Key`, so a retried tap can never create a second meal.
- **Your corrections are remembered** (per-unit values for that food) and used next time.
- **Errors are explained**, in words, with a way forward. Over target is amber, never red.

## Before a store release (not done yet)

- A release signing key and your own `applicationId` (currently `dev.spoton.spoton`); a store listing.
- A public `https://` server (see [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)). A privacy policy page (`/privacy`),
  change password and delete account already exist.
- Password reset by email (needs an email service) or Sign in with Google / Apple.
- Camera and photo flows use `image_picker` and are untested on a real device so far.
- iOS: needs full Xcode, CocoaPods and an Apple Developer account. The iOS project is generated and configured, but
  not built.
- Automatic steps (Health Connect / HealthKit) and reminders are not built.
