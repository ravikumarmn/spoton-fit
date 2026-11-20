# SpotOn: improvements backlog

*Review date: 20 Nov 2026 · Code reviewed: API v0.7.0, Streamlit web app, Flutter app in `mobile/`*

**Status 20 Nov 2026:** ticked items are done and tested; open items say why they're still open.

A to-do list from a full read of the repo: the FastAPI and LangGraph backend, the Streamlit web app, the Flutter app, the PRDs and [`REVIEW_AND_PLAN.md`](REVIEW_AND_PLAN.md). Tick items off as you go.

**Verdict.** The engineering is solid:
- The model estimates one unit of each food, and code does all the maths.
- Safety routing runs before the model.
- Targets are tested, and refresh tokens rotate.
- Evals run in CI.

The biggest gap is that the app has **never been deployed or used on a real phone**: the camera flow, secure storage and the iOS build are untested on a device, and there was no high-fidelity design pass. Use it yourself every day for two weeks before adding much.

---

## 1. Fix first (blockers)

- [x] **`uv.lock` is out of date.** *(done: regenerated; CI and Docker build green)*
  - `pyproject.toml` requires `langgraph-checkpoint-sqlite`, `langgraph-checkpoint-postgres` and `psycopg`, but none of them are in `uv.lock`.
  - `ci.yml` (line 33) and the `Dockerfile` (lines 12 and 14) run `uv sync --locked`, so **CI and the Docker build fail** as things stand.
  - Fix: `uv self update && uv lock`. uv 0.12.3 also can't install the pinned Python 3.15.2.
  - Evidence (20 Nov 2026): on Python 3.14 in a throwaway environment, 96 of 97 tests pass and ruff is clean. The one failure (`test_coach_memory_survives_a_restart`) is `ModuleNotFoundError: langgraph.checkpoint.sqlite`, the same lockfile problem.
- [x] **Run the Flutter tests** (`flutter test`, `flutter analyze`). Flutter wasn't installed on this machine, so they weren't checked in this review. *(done: 109 pass, analyze clean, run in CI)*
- [ ] **Install a debug build on your own Android phone** and log real meals for a week. Note every moment of friction. *(in progress: you're using the release build; keep a friction list)*

## 2. Code issues (smaller)

- [x] **Two clients to maintain.** Freeze the Streamlit app as a dev and admin tool; build new features only in Flutter. *(done: frozen, noted in README)*
- [x] **State that lives in one server process.** The rate limiter (`api/ratelimit.py`) and the per-user coach cache live inside one process. On Cloud Run, cap it at one instance (`--max-instances=1`) until they move to Postgres or Redis. *(done: 1 instance, 1 process)*
- [x] **Safety phrase matching gives false positives.** "No chest pain" still routes to the doctor reply (`agents/safety.py`). When a phrase matches, ask the small model (flash-lite) to confirm before routing. Keep the deterministic route as the fallback if the model call fails. *(done: checked with real Flash-Lite on 5 phrasings)*
- [x] **Food memory needs the exact same name.** *(done: word order and punctuation ignored; migration 0005)* If the model writes "egg, boiled" instead of "boiled egg", your saved values are skipped (`core/nutrition.food_key`). Options: pass memory items to the model with IDs and have it return the ID, or show "Use your saved values for *boiled egg*?" on the review screen.
- [x] **Today makes 3 calls** (today, meals, weekly review). Return the meals and the review status inside `GET /v1/today` (already listed in `MOBILE_PLAN.md`). *(done)*
- [ ] **Icons don't match the plan.** `MOBILE_PLAN.md` specifies Material Symbols Rounded; the code uses the default `Icons.*`. *(open: part of the UI pass (section 4))*

## 3. Features, by real-life impact

### 3.1 Faster logging (most important for retention)
- [x] **Instant save with Undo** when every item is remembered (`source == "memory"`) or the model's confidence is high. Today every meal must go through the review screen. *(done for remembered foods; high-confidence AI estimates still go to review on purpose)*
- [ ] **Voice logging:** speech-to-text, then the existing text endpoint. *(open: the phone keyboard's mic already dictates into Type; build only if testers ask)*
- [ ] **"Copy yesterday's breakfast"** and "log the same as last Monday". *(open: Recent + Log again covers most of it; wait for feedback)*
- [ ] **Home-screen widget:** +250 ml water, + meal, calories and protein left. *(open: native Android/iOS widget code, needs device testing)*
- [x] **Long-press to repeat** on the − / + steppers (open in `MOBILE_PLAN.md`). *(done)*

### 3.2 Automatic data
- [ ] **Steps from Health Connect / HealthKit** (PRD N-03). Typing steps in by hand is the weakest data, and learned maintenance depends on it. *(open: PRD Phase 4; needs permissions and device testing)*
- [ ] **Weight from smart scales** through the same Health Connect / HealthKit integration. *(open: with the item above)*

### 3.3 Nudges (PRD Phase 4)
- [ ] **Reminders** (N-01): missed meal log, protein behind by 6 PM, weekly weigh-in. Daily cap and quiet hours. *(open: PRD Phase 4; needs a notifications service and device testing)*
- [ ] **Notification actions** (N-02): +250 ml, Log food, Snooze. *(open: after reminders)*

### 3.4 Coach and planning
- [ ] **Restaurant and menu mode:** *(open: worth building after feedback; ~1 day)* photograph a menu and get the two best picks for the calories and protein left. Fits the PRD's "I'm at a biryani place" case.
- [x] **Cross-day coach memory:** free-form notes ("vegetarian on Tuesdays"). A known limit in the README. *(done: Me › Coach notes; coach tool + suggestions)*
- [ ] **Plan ahead:** log tomorrow's meals as planned, then confirm them with one tap. *(open: needs a 'planned' meal state; wait for feedback)*
- [ ] **Weekly protein shopping list** from My Foods. *(open: wait for feedback)*

### 3.5 Accuracy (see section 5)
- [ ] **Weighed eval set:** *(open: needs your weighed meals; how-to in evals/WEIGHED_MEALS.md)* 20+ real meals (weigh them, take nutrition from IFCT 2017 or the pack label). Publish the MAPE, which also counts as portfolio proof.
- [x] **"How this was estimated" line per item:** *(done)* e.g. "1 piece ≈ 45 g × ~4 kcal/g ≈ 180 kcal", so the user can sanity-check it.
- [x] **Ask one targeted question for high-impact unknowns:** *(done: prompt prioritises milk/water, ghee/oil, sugar, piece size)* "Oats made with water or milk?", "How big was the sweet: small, medium or large?". The `clarify` field already exists; the prompt could prioritise milk/water, ghee, sugar and piece size.
- [x] **Size picker on the review screen** *(done: Smaller / As estimated / Larger, this meal only)* (small / medium / large, about 0.75× / 1× / 1.3× grams) for sweets, rotis and bowls, next to the count stepper.

### 3.6 Later
- [ ] **Barcode scanning** with Open Food Facts for packaged Indian foods (PRD L-04). *(open: later)*
- [ ] **Meal photo timeline** (needs object storage; only thumbnails are kept today). *(open: later)*
- [ ] **Per-user timezone**, before public users. *(open: before users outside India)*
- [ ] **Offline queue** for logs made without a network connection. *(open: later)*
- [ ] **Google / Apple sign-in and password reset.** *(partly: Change password + admin reset script done; email reset and Google/Apple sign-in need an email service / OAuth setup)*
- [ ] **Store readiness:** privacy policy page, signing key, app icon and splash screen, crash reporting, a TalkBack / VoiceOver pass. *(partly: privacy page, signing key, icon, splash done; crash reporting needs a Sentry/Crashlytics account; TalkBack needs a device)*

---

## 4. UI: making it look premium

**Today:** clean and accessible (WCAG AA checked, works at 200% text size), but it looks generic. Every block is a white card with a border, Today is the standard ring plus bars, there's no motion, and there's no dark mode.

**Apps to study** (borrow patterns, not their look; browse real screens on [Mobbin](https://mobbin.com)):
- **MacroFactor:** the bold dashboard, and a timeline in place of fixed meal slots.
- **Cal AI, PlateLens:** photo-first logging.
- **Lifesum, Yazio:** polish among traditional trackers.
- **Oura, Whoop:** a premium dark, data-first look.

The "best UI" rankings online are affiliate-blog opinions with no shared method.

**Changes, most effective first:**
- [ ] **Dark mode.** You log dinner at night, and dark mode reads as premium. Add a second `AppColors` palette and re-run the contrast tests in `test/theme_test.dart`.
- [ ] **Fewer boxes.** Drop the card borders and separate sections with tonal surfaces (slightly different background shades). Give Today one focal point: **calories left** and **protein left** as the two big numbers, with water, steps and carbs/fat quieter below.
- [ ] **Motion and haptics.** Numbers count up, the ring fills, a haptic tap on save, smooth sheet transitions.
- [ ] **In-app camera** with the `camera` package instead of `image_picker`, so logging stays in the app. On the analysing screen, show the photo and let each item appear as it's recognised.
- [ ] **Material Symbols Rounded** icons (see section 2).
- [ ] **Hi-fi design pass before coding:** Today, Log / Review, Coach, in light and dark (Figma, or a clickable HTML mockup).
- [ ] **Skip Material 3 Expressive for now.** The Flutter team hasn't committed to it officially, and the community packages are young.

---

## 5. Are the calories right? (oily food vs healthy food)

**The adding is always exact. The estimate of each food is where errors come from.**

How a meal's number is made (`agents/food_logger.py`, `core/nutrition.py`):
1. The model looks at the photo or note and estimates, for **one unit** of each food: grams, calories, protein, carbs and fat. **Oil, ghee, sugar and milk are meant to be included in that per-unit value.**
2. Code multiplies by the count and adds the items up. This part is plain arithmetic and can't be wrong.
3. `oil_level` (none / light / medium / heavy) is **only a flag**. It adds no calories by itself; the oil should already be inside the per-unit calories.
4. A check compares calories with 4 × protein + 4 × carbs + 9 × fat and warns when they disagree.

**Why a sweet shows more than oats and banana:** calories follow energy density (calories per gram), not how "healthy" the food is. Indian sweets are mostly sugar plus ghee or khoya, so they are very energy-dense. Oats cooked in water are mostly water. The figures below are approximate typical values, not lab-measured; sweet figures vary a lot by piece size and recipe.

| Food | Typical estimate |
| --- | --- |
| Oats (about 40 g dry) cooked in water, plus a medium banana | about 250 kcal |
| The same oats cooked in about 200 ml toned milk | about 370–380 kcal |
| Gulab jamun, 1 piece (40–50 g) | about 145–200 kcal |
| Besan laddoo, 1 piece (about 40 g) | about 170–200 kcal |
| Kaju katli, 1 piece (10–30 g) | about 50–120 kcal |

So **239 kcal for oats + banana** is right if the oats were made with water; if you used milk it's probably 100–130 kcal too low. **360 kcal for "Indian sweets"** fits about two laddoos or gulab jamuns; it's too high for one small piece and too low for a plate.

**What to do when logging:**
- Write the details in the note: "oats in milk, 1 tsp sugar", "2 medium besan laddoos". The note overrides the photo.
- On the review screen, check the **count** and the **grams** first. Most errors are portion size, not the food.
- Fix the per-unit values once for foods you eat often. SpotOn remembers them (food memory) and uses your values next time.
- Over weeks, **learned maintenance** absorbs a consistent bias: if you always under-count by about 150 kcal, the learned maintenance also comes out about 150 kcal lower, so your weight trend stays on plan. It can't fix random errors, so consistent logging matters more than perfect numbers.

---

## Sources

- [Calorie Tracker with Best UI (2026), Calorie Tracker Lab](https://calorietrackerlab.com/bestof/calorie-tracker-with-best-ui-2026/)
- [Best UX Calorie Apps (2026), Calorie Tracker Lab](https://calorietrackerlab.com/bestof/best-ux-calorie-apps-2026/)
- [Best calorie tracking apps of 2026, The Review Bench](https://thereviewbench.com/reviews/best-calorie-tracking-apps-2026-roundup/)
- [Best calorie counter apps, Garage Gym Reviews](https://www.garagegymreviews.com/best-calorie-counter-apps)
- [MacroFactor: fastest food logger (2025 update)](https://macrofactorapp.com/fastest-food-logger-2025/)
- [MacroFactor vs Cal AI](https://macrofactor.com/macrofactor-vs-cal-ai/)
- [MacroFactor review (2026)](https://gainframe.app/blog/macrofactor-review/)
- [Very Good Ventures: Material 3 Expressive and Flutter](https://verygood.ventures/blog/a-new-era-for-app-design-and-what-it-means-for-flutter/)
- [material_3_expressive package](https://pub.dev/packages/material_3_expressive)
- [Calories in laddoos and kaju katli, Business Standard](https://www.business-standard.com/health/diwali-2025-calories-in-laddoos-kaju-katlis-samosas-gujiyas-125101700638_1.html)
- [Calories in gulab jamun, Tarla Dalal](https://tarladalal.com/calories-for-gulab-jamun-2854)
- [Calorie count of desi sweets, Netmeds](https://www.netmeds.com/c/health-library/post/diwali-2023-know-the-calorie-count-of-desi-sweets-for-guilt-free-celebrations)
