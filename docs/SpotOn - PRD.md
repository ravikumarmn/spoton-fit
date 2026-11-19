# SpotOn — Product Requirements Document (PRD)

*AI personal trainer for fat loss and muscle building · v1.0 · 18 Nov 2026*

## Document control

| Item | Detail |
| --- | --- |
| Product | SpotOn: AI personal trainer app |
| Owner | Product owner and lead engineer (you) |
| Status | Approved for build: Phase 0 starts now |
| Companion document | SpotOn — Technical PRD (architecture, APIs, data, CI/CD) |
| Supersedes | App plans v1, v2, v3 and the Final Implementation Plan |

## 1. Summary

SpotOn is an AI personal trainer you carry in your phone. You set your goal (lose fat, build muscle, or maintain), then log meals by **taking a photo, uploading a photo, or typing**. SpotOn works out calories and macros from a food database, shows what is left for the day, and suggests what to eat next from foods you can actually get. It answers questions like *"Can I have tea now?"* using your real numbers, and keeps your full history (day, week, month, year) from the day you start. Over time it learns your real maintenance calories from your weight trend and adjusts your targets.

## 2. Problem

| Problem | Evidence / impact |
| --- | --- |
| Logging food is slow, so people stop | Results depend on logging consistency; most people quit manual calorie apps within weeks |
| Photo-only calorie apps are inaccurate | A 2026 NIH study found photo apps underestimated calories by 250–345 kcal per meal, mostly fat |
| Targets from formulas are often wrong | Formula maintenance can be off by hundreds of kcal; only the weight trend reveals the truth |
| Advice ignores real life | Generic meal plans assume you can cook anything; bachelors, students and busy workers can't |
| Good coaching is expensive | Personal trainers and nutritionists cost thousands a month |

## 3. Goals and non-goals

### Goals

1. Log any meal in **≤ 10 seconds** (photo + one tap).
2. Give **accurate daily numbers**: calories from a database, never invented by the AI.
3. Tell the user **what to eat next**, using only foods they can get.
4. **Learn the user's real metabolism** and adjust targets automatically.
5. Keep a **complete history** from day one: day, week, month, year.
6. Be **safe**: no extreme diets, no shaming, sensible floors.

### Non-goals (for now)

- Medical diagnosis or treatment plans
- Full workout programming (logging workouts is in scope; a training programme is not)
- Social feeds, challenges, leaderboards
- Selling supplements, ads, or user data

## 4. Users

| Persona | Description | Key needs |
| --- | --- | --- |
| **Primary: "Desk-bound professional"** (the first user) | 26, male, Bengaluru, AI engineer, ~92 kg, 24% body fat, sedentary, trains 4–5×/week in the evening, bachelor with limited cooking | Fast logging of Indian food, protein tracking, realistic suggestions (oats, eggs, idli, curd, fruit, eating out) |
| Secondary: Student / hostel | Fixed mess food, tight budget | Mess-meal logging, cheap protein ideas |
| Secondary: Muscle gainer | Wants to gain lean mass | Surplus targets, high protein, training log |
| Later: Public users worldwide | Any cuisine, any language | Regional foods, multilingual, privacy |

## 5. Success metrics

| Metric | Target (Phase 1–3) |
| --- | --- |
| Time to log a meal (median) | ≤ 10 s |
| Days logged per week (median active user) | ≥ 5 |
| Photo calorie error on home meals (eval set) | ≤ 20% MAPE |
| Protein target hit rate | ≥ 5 of 7 days |
| Coach answers using correct live numbers (eval set) | ≥ 95% |
| User still logging at day 30 | ≥ 60% (for the first cohort) |
| Safety incidents (advice below floor) | 0 |

## 6. Phases at a glance

| Phase | Name | Duration | Outcome |
| --- | --- | --- | --- |
| **0** | Foundation | Week 1 | Secure API, sign-up/login, CI/CD that deploys on every push |
| **1** | Core tracking MVP | Weeks 2–4 | Profile → targets; photo/upload/text logging; Today; water, steps, weight; History |
| **2** | Coach and smart suggestions | Weeks 5–6 | Coach chat, two-mode suggestions, My Foods, food rules |
| **3** | Progress intelligence | Weeks 7–8 | Workouts, weight trend, learned maintenance, predictions, weekly review |
| **4** | Nudges and mobile | Weeks 9–12 | Reminders/push notifications; Android companion for steps and sitting detection |
| **5** | Public launch | Month 4+ | Multi-user hardening, Google sign-in, regional food packs, languages, open source |

Each phase ends with a usable product and a short review before the next one starts.

## 7. Requirements by phase

Priority: **P0** = must ship in the phase · **P1** = should ship · **P2** = nice to have.

### Phase 0: Foundation (Week 1)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F-01 | Account sign-up and login with email + password | P0 | User can register, log in, stay logged in for 30 days, log out |
| F-02 | Secure sessions | P0 | Short-lived access token + rotating refresh token; logout revokes the session |
| F-03 | Health and version endpoint | P0 | Shows app version and status; used by deploy checks |
| F-04 | Automatic deploy on push | P0 | A push to `main` that passes all checks is live within ~10 minutes; a failing push never deploys |
| F-05 | Traces and logs for every request and AI call | P0 | Every request has a request ID; AI calls appear in LangSmith |

### Phase 1: Core tracking MVP (Weeks 2–4)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| T-01 | Profile: age, sex, height, weight, goal, activity, optional body fat % and goal weight, start date | P0 | Saved; editable any time |
| T-02 | Targets: BMI, BMR, maintenance, calories, protein, fat, carbs, fibre, water, steps | P0 | Matches the reference calculation (e.g. BMR 1,884 kcal for the primary user); never below the safety floor |
| T-03 | Log a meal by **taking a photo** in the app | P0 | Camera opens in one tap; result in ≤ 8 s (p95) |
| T-04 | Log a meal by **uploading a photo** from the gallery | P0 | JPG/PNG/WEBP/HEIC up to 10 MB |
| T-05 | Log a meal by **typing** ("2 boiled eggs and a banana") | P0 | Items and totals shown in ≤ 5 s |
| T-06 | Review before saving: items, grams, oil level, calories, protein, carbs, fat | P0 | User can edit grams/remove items; totals update; nothing saves without confirmation |
| T-07 | Calories come from the food database; AI only identifies foods and portions | P0 | Every item shows its source (database / AI estimate) |
| T-08 | One-tap repeat of a recent or favourite meal | P1 | Logged in ≤ 2 taps |
| T-09 | **Today** screen: eaten, burned (estimate), left for calories, protein, carbs, fat, water, steps | P0 | Updates immediately after any log |
| T-10 | Log water (+250 / +500 ml), steps (manual for now), weight | P0 | Each log ≤ 2 taps |
| T-11 | **History**: day, week, month, year views from the start date; charts for calories, protein, steps, weight | P0 | Every day since start is shown, including days with no logs |
| T-12 | Export all data (CSV/JSON) | P1 | One download with all logs |
| T-13 | Indian food database with household units (piece, katori, ladle, plate) | P0 | ≥ 500 foods at Phase 1 exit (INDB + IFCT import) |

### Phase 2: Coach and smart suggestions (Weeks 5–6)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| C-01 | **Coach chat**: "Can I have tea now?", "What should I eat for dinner?", "I'm at a biryani place" | P0 | Answers use live numbers (calories/protein left), give one practical next step, ≤ 3 s to first words |
| C-02 | **Two suggestions every time**, from **My Foods** (default) and an **Ideal** option | P0 | Options fit remaining calories and help close the protein gap |
| C-03 | **My Foods** list: foods the user can actually get, with effort level (no-cook, 5-min, buy nearby, order) | P0 | Editable; suggestions only use available foods in My Foods mode |
| C-04 | **Food rules** in plain English ("idli at most 3 days a week", "no tea after 4 PM") | P1 | Rule shown back for confirmation; violations produce a gentle nudge and change tomorrow's suggestions |
| C-05 | Coach remembers the conversation within a day and key preferences across days | P1 | Doesn't ask the same question twice in a day |
| C-06 | Safety: never advise below the calorie floor; red-flag symptoms → see a doctor; no shaming | P0 | 100% pass on the safety eval set |

### Phase 3: Progress intelligence (Weeks 7–8)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| P-01 | Log workouts in plain words ("15 min cycling, 15 min treadmill, 40 min weights") | P0 | Activities and minutes parsed; calories estimated (MET method) |
| P-02 | Weight trend line (smoothed) alongside daily weights | P0 | Water swings don't distort the trend |
| P-03 | **Learned maintenance** from intake vs weight trend | P0 | Activates after ≥ 14 logged days; changes gradually; shown with an explanation |
| P-04 | Predictions as ranges ("87 kg likely between mid-Jan and Feb") | P1 | Always a range, never a promise |
| P-05 | **Weekly review** (Sunday): averages, adherence, trend, waist, proposed target change | P0 | User can accept or reject the proposal |
| P-06 | Body measurements (waist, hip, body fat %) | P1 | Shown in History |

### Phase 4: Nudges and mobile (Weeks 9–12)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| N-01 | Reminders: water, missed meal log, protein behind schedule, weekly weigh-in | P0 | Delivered as push notifications; max ~12/day; quiet hours respected |
| N-02 | Notification actions: Done, Snooze, +250 ml, Log food | P1 | Act without opening the app |
| N-03 | Android companion: automatic steps (phone step sensor) | P0 | Steps sync at least every 15 min while the phone is on |
| N-04 | Sitting detection and "walk 3–5 min" nudge after ≥ 45 min sitting with the phone in use | P0 | No nudges while driving or during quiet hours; "I walked" resets |
| N-05 | Status notification: calories/protein/water/steps left | P1 | Refreshes every 15 min |

### Phase 5: Public launch (Month 4+)

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| L-01 | Google sign-in | P0 | One-tap sign-in alongside email |
| L-02 | Multi-user isolation and data deletion | P0 | Users only ever see their own data; "delete my account" removes everything |
| L-03 | Bring-your-own Gemini key or community-funded mode | P1 | App works without a central AI bill |
| L-04 | Regional food packs and barcode scan (Open Food Facts) | P1 | Packaged foods found by barcode |
| L-05 | Languages: Kannada, Hindi, Tamil, Telugu, English | P2 | UI and voice logging |
| L-06 | Open-source release (AGPL-3.0 code, ODbL food data) | P1 | Public repo with docs, safety notes, accuracy results |

## 8. Key user flows

### Log a meal (photo)

1. Tap **Log** → **Camera** (or **Upload**).
2. Take the photo; optionally add a note ("ate only 2 idlis").
3. SpotOn shows items, grams, oil level and totals within seconds.
4. Adjust grams if needed → **Save**.
5. Today updates: calories and protein left, plus the next best move.

### Ask the coach

1. Open **Coach** → type "Can I have tea now?"
2. Coach checks today's totals and the time, then answers: "Yes. Tea with milk and 1 tsp sugar is ~80 kcal; you'll have 430 kcal and 38 g protein left. Keep dinner as chicken + 2 chapatis. Make it your last caffeine today."

### Weekly review (Phase 3)

1. On Sunday, SpotOn shows trend weight, averages and adherence.
2. If progress stalled for 2–3 weeks with good adherence, it proposes "+1,500 steps" or "−100 kcal from carbs".
3. User taps **Accept** or **Keep as is**.

## 9. Product-level non-functional requirements

| Area | Requirement |
| --- | --- |
| Accuracy | Calories from database; photo results always reviewable; published eval results |
| Speed | Non-AI screens ≤ 300 ms; photo analysis ≤ 8 s p95; coach first words ≤ 3 s |
| Privacy | Data belongs to the user; export and delete any time; photos never used for anything else; no ads |
| Security | Encrypted in transit; passwords hashed; short-lived sessions |
| Availability | 99.5% monthly for the API (Phase 1–4) |
| Safety | Calorie floor, max loss ~1%/week, no shaming, doctor referral for red flags, 18+ |
| Cost | Runs on free/low-cost tiers for a single user; AI calls kept to ~20 per user per day |

## 10. Safety principles

- Targets never go below the floor (the higher of BMR and 1,500 kcal for men / 1,200 kcal for women).
- No "burn it off" messaging; exercise calories are not added back to the food budget.
- Gentle tone, no red failure screens, optional "hide numbers" mode in Phase 5.
- Very low intake or very fast loss → supportive message and a suggestion to talk to a professional.
- Not a medical device; clear disclaimer.

## 11. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Photo estimates miss oil and fat | Oil-level field, editable grams, personal food memory, learned maintenance corrects bias |
| Users stop logging | Repeat meals, one-tap photo, gentle reminders (Phase 4) |
| Notification fatigue | Smart rules, daily cap, quiet hours, snooze |
| AI gives unsafe advice | Tools-only answers, hard floors in code, safety eval set in CI |
| Costs grow with users | Small models for parsing, image resizing, caching, bring-your-own-key in Phase 5 |

## 12. Open questions

1. Phase 1 client: keep the Streamlit web client, or start the Android app earlier? (Recommended: Streamlit in Phases 0–3, Android companion in Phase 4.)
2. Hosting region and provider for the API (Technical PRD recommends Google Cloud Run + Neon Postgres).
3. Domain, store listing and trademark check for the chosen name SpotOn (a restaurant-payments company also uses it) and an icon, before the Phase 5 public launch.
