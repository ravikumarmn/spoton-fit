# SpotOn mobile app: plan summary (v1, 19 Nov 2026)

Full plan with wireframes and the visual system: https://claude.ai/artifact/TAVGLU3ZF5gCUB7iAyjqKs (private; share it from the page if others need it).

Status: **built (19 Nov 2026)**: the app in [`mobile/`](../mobile/README.md) implements the plan with the recommended choices
(Flutter, Sage accent, Android first, name "SpotOn", API on the Mac over Wi-Fi). See "Implementation status" at the end.

## Decisions (proposed)

1. **Framework: Flutter 3.50 / Dart 3.14**, one codebase for Android and iOS. Runner-up: Kotlin Multiplatform + Compose Multiplatform (stable on iOS since May 2025, but rougher iOS edges and a smaller plugin ecosystem). This replaces Technical PRD ADR #7 ("native Kotlin Android companion"): steps come from the `health` plugin, and sitting detection uses a platform channel.
2. **Navigation:** bottom bar with Today · Progress · **+ Log** (raised centre) · Coach · Me. History sits inside Progress; My foods, rules, remembered foods and data sit under Me.
3. **Screens:** 20 in total (7 first-run only + 13 everyday), plus 10 bottom sheets. One primary button per screen.
4. **Logging:** + opens the camera directly (modes Recent · Photo · Type). The review screen uses − / + steppers per item; tapping an item edits its per-unit values (which SpotOn remembers).
5. **Visual system:** light theme only; Inter with tabular figures; sage-teal accent `#2B7A68`; 4 dp grid; cards with radius 16; Material Symbols Rounded icons. All text pairs are WCAG AA (verified). Amber, never red, marks over-target or oily food.

## Design tokens (light)

| Token | Value | Check |
| --- | --- | --- |
| primary / on-primary | `#2B7A68` / `#FFFFFF` | 5.14:1 |
| primary container / on | `#D8EFE8` / `#0F3D33` | 10.04:1 |
| background / surface | `#F6F7F5` / `#FFFFFF` | — |
| text / secondary / tertiary | `#1C2925` / `#55635E` / `#6B7873` | 14.0 / 5.9 / 4.6:1 |
| outline (decorative) / input border | `#D3DBD7` / `#87948F` | — / 3.15:1 |
| track (bars, ring) | `#E7ECEA` | — |
| protein · carbs · fat · water | `#3672A3` · `#B07A1E` · `#82619F` · `#2F86BF` | ≥ 3:1 on track |
| heads-up (bg / text) | `#FFF4DC` / `#8A5A00` | 5.43:1 |
| info (bg / text) | `#E8F1FA` / `#245F94` | 5.86:1 |
| error (bg / text), real errors only | `#FCECEA` / `#A3271F` | 6.39:1 |

Alternative accents: Ocean `#2A6E96` (5.57:1), Plum `#6A5A9A` (5.93:1).

## Backend work the app needs

- A public HTTPS API (Mac's Wi-Fi address or a tunnel for testing; the Cloud Run + Neon deploy for real use).
- `DELETE /v1/account` plus a web deletion page (Google Play and Apple requirements), and a privacy policy page.
- Password reset (needs an email service) or Sign in with Google / Apple.
- Optional: return meals and review status inside `/v1/today` to cut round trips.
- PRD Phase 4: devices, activity samples, notification settings.

## Milestones (each ends with an installable APK)

| Milestone | Scope | Exit |
| --- | --- | --- |
| M0 Foundations & design | Hi-fi designs of 7 key screens; Flutter project in `mobile/`; tokens; core components + golden tests; OpenAPI-generated client; CI APK | Component gallery on device; contrast and touch-target tests pass |
| M1 Account & Today | Welcome, sign up/in, persistent session; 3-step onboarding + Your plan; Today with quick adds | Install → plan in about 1 min; still signed in after restart |
| M2 Logging | Capture modes, gallery, analyzing, review with steppers and edit item, idempotent save, favourites/log again, edit/delete with Undo | Photo meal logged in < 10 s |
| M3 Coach & planning | Streaming coach, suggestions sheet → review, My foods, food rules with confirm | First words < 3 s; safety replies shown correctly |
| M4 Progress | Weekly review accept/keep, trend chart, maintenance explanation, goal range, measurements, History | Numbers match the API; readable at 200% text |
| M5 Release readiness | Me/settings, export, delete account, privacy, accessibility pass, crash reporting, Play internal testing, TestFlight | Store checklists pass |
| PRD Phase 4 | Health Connect / HealthKit steps, reminders with actions, sitting detection | As in the PRD |

## Open decisions

1. Flutter, or Kotlin Multiplatform?
2. Accent: Sage (recommended), Ocean or Plum?
3. iOS now or from M5? (Needs Xcode and a paid Apple Developer account.)
4. Keep the "SpotOn" name for testing? (Trademark check needed before store listing.)
5. API for phone testing: the Mac on Wi-Fi, or deploy to Cloud Run first?

## Implementation status (19 Nov 2026)

Built and tested: all 20 screens and the sheets in the plan, on Flutter 3.50.0. 101 Flutter tests pass, and the API's 97 Python tests pass.
An end-to-end test drives the real client against a real server with real Gemini (estimate, rule parsing, streaming coach, delete account).

| Milestone | Status |
| --- | --- |
| M0 Foundations (theme tokens, components, API client, CI) | ✅ Palette checked against WCAG AA in tests. CI job added. |
| M1 Account and Today | ✅ Sign up/in, persistent session, 3-step onboarding, Your plan, Today with quick adds |
| M2 Logging | ✅ Capture (Recent / Photo / Type), analyzing, review with − / + and item editing, idempotent save, favourites, log again, edit, delete with Undo |
| M3 Coach and planning | ✅ Streaming coach, suggestions sheet, My foods, Food rules with confirm step |
| M4 Progress | ✅ Weekly review (Accept / Keep), weight trend chart, maintenance explanation, goal range, measurements, History charts |
| M5 Release readiness | 🟡 Export and **Delete account** done (backend `DELETE /v1/account` added). Still open: privacy policy page, signing key, icon, store listing, TalkBack/VoiceOver pass on a device, crash reporting |

### Where the build differs from the plan

- **Camera:** uses the phone's own camera and gallery through `image_picker` (one tap to open, then the review), not a custom live viewfinder inside the app. Lower risk; a custom camera screen can replace it later.
- **API client:** models are hand-written and checked against real API responses (`mobile/test/fixtures`, regenerated by `scripts/gen_mobile_fixtures.py`, also in CI), not generated from OpenAPI.
- **Tests:** accessibility is checked with Flutter's tap-target, label and contrast guidelines and at 150% / 200% text size. Golden (screenshot) tests were not added.
- **Not done:** past-reviews list, long-press to repeat on − / +, "Today in one call", password reset, Sign in with Google/Apple, the privacy policy page, app icon and splash.
- **Design:** built directly from the approved wireframes. No separate high-fidelity design pass was done; judge the look on a device and tell me what to adjust.
- **Untested on a device:** the camera/gallery flow, the share sheet for export, and the Keychain/Keystore storage (all covered by fakes in tests). iOS is configured but not built (needs full Xcode).

### Bugs the testing found (all fixed)

- Streaming the coach would have crashed on a real device (the byte stream's runtime type), found by a test using Dio's real stream type.
- Errors on streaming requests (such as "AI is not configured") lost their message.
- A wrong password on Delete account (the API answers 401) would have **signed the user out** instead of saying "Incorrect password". Found only by the live end-to-end test.
- Coach and Review screens overflowed at 150–200% text size; the Review's pinned panel is now only the total and the Save button.
- After saving the profile, the confirmation was off-screen at the top of a long form; it now scrolls into view and shows a toast.
- The coach's Markdown (`**bold**`) showed as asterisks; a small renderer now formats bold, italics and lists.

### Known test gap (20 Nov 2026)

The widget test "editing a saved meal saves changes to that meal" fails when the test machine's time zone is
not the server's (e.g. UTC at 03:00 IST, when the server's "today" is a day ahead). CI runs the mobile job in
`Asia/Kolkata`. The other two tests that failed under UTC were fixed (the test helper scrolled a sideways chip
row instead of the page). The app behaviour behind it: a phone whose date differs from the server's shows the
date ("Fri, 20 Nov") instead of "Today".
