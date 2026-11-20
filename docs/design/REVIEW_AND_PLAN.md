# SpotOn: implementation review against the PRDs, and the fix plan

*Review date: 19 Nov 2026 · Code reviewed: `src/spotonfit` v0.2.0 (36 Python files, 23 tests)*

> **Update, 19 Nov 2026 (v0.3.0):**
> - Phase A and Phase B are implemented (40 tests).
> - Nutrition is now **estimated by the model per unit, and multiplied and summed by code**. The food table is gone, by product decision **D1** (section 7).
> - The B2/B7/B8 findings below referred to the old food table and no longer apply as written.
> - Deploy is prepared but has not been run (it needs your GCP and Neon setup).
> - **v0.6.0:** Phase E is done: learned maintenance, weekly reviews with accept/reject, predictions as ranges, measurements, and the weekly job (92 tests).
> - **v0.5.0:** Phase D is done: streaming coach, persistent memory, My Foods, food rules, safety routing and evals (73 tests).
> - **v0.4.0:** Phase C is mostly done. The Streamlit web app and meal editing, favourites, repeat, food memory and export work (52 tests). See the Phase C table for what's deferred.

How this was checked: every source file was read. The test suite and linter were run (23/23 pass and ruff is clean, on Python 3.14 with the exact locked dependency versions, because the installed uv 0.12.3 cannot download Python 3.15.2). Each bug listed under "Confirmed bugs" was reproduced with a script, not just inferred from reading. Gemini details were checked against Google's current docs (Nov 2026; links at the end).

---

## 1. Verdict

**The direction is right, but the code is only partly aligned.** The architecture follows the Technical PRD's core principles:

- FastAPI is async end to end.
- LLMs perceive and code calculates.
- Agents use LangGraph and Deep Agents.
- Model access goes through `init_chat_model`.
- `core/` holds the domain logic.

In PRD terms, the repo is a **Phase 1 prototype with Phase 2–3 pieces started**:

- **Phase 0 (Foundation)** is incomplete.
- **Phase 1** has 7 of 13 requirements met.

Several confirmed bugs give **wrong numbers to users**. That is the most important thing to fix, because accuracy is the product's core promise (PRD goal 2).

| PRD phase | Status | Summary |
| --- | --- | --- |
| 0 Foundation | 🟡 ~45% | Register/login/JWT work. Missing: rotating refresh tokens, logout, `/v1`, `/healthz`+`/readyz`, rate limits, error envelope, Alembic, Dockerfile, deploy. **CI is broken** (references files that don't exist). |
| 1 Core MVP | 🟡 ~55% | Profile, targets, photo/text analyze, save, Today, water/steps/weight and History all exist. Missing: drafts and idempotency, edit/repeat/favourites, export, food search, a ≥500-food DB (only 55 now), and the **web client** (`frontend/` is empty). |
| 2 Coach | 🟠 ~25% | The Deep Agents coach exists with 6 read-only tools. Missing: SSE streaming, Postgres checkpointer, My Foods, two-mode suggestions, rules, safety evals. |
| 3 Progress | 🟠 ~30% | Workout parser, METs, EMA trend, learned TDEE and prediction maths exist. Missing: `/progress`, weekly review, measurements, persisted TDEE. |
| 4–5 | ⚪ 0% | Not started (expected). |

---

## 2. Confirmed bugs (reproduced)

| # | Severity | Bug | Evidence | Impact |
| --- | --- | --- | --- | --- |
| B1 | 🔴 High | **History puts evening meals on the wrong day.** SQLite drops the timezone: times are written in IST but `_to_local_day` reads them back as UTC and shifts them +5:30. | A 21:00 dinner on 18 Nov appears under 18 Nov in Today but under **19 Nov** in History. | Any meal after 18:30 IST lands on the next day. History, learned TDEE and adherence are all wrong locally. |
| B2 | 🔴 High | **Fuzzy food matching picks the wrong food.** `difflib` cutoff 0.72 on whole strings. | `"masala chai"` → masala dosa, `"brown rice"` → whole wheat bread, `"egg biryani"` → chicken biryani | Tea (~60 kcal) is logged as a 380 kcal dosa. This breaks PRD goal 2 ("accurate daily numbers"). |
| B3 | 🔴 High | **The offline eval runner crashes.** It calls sync `.invoke()` on an async graph with a sync stub. | `TypeError: No synchronous function provided to "extract"` | The CI "offline eval" gate can never pass. |
| B4 | 🔴 High | **CI is dead.** `ci.yml` and `evals.yml` install `requirements.txt`, boot `streamlit_app.py` and use Python 3.12. None of these exist. Eval path filters point at `spotonfit/…`, not `src/spotonfit/…`. | Files missing from the repo | Every push fails, so there is no automated safety net (PRD F-04). |
| B5 | 🟠 Med | **HEIC uploads return 500.** HEIC is allow-listed, but Pillow 13 can't decode it, and the decode runs outside the `try`. A corrupt JPEG also returns 500. | `Image.registered_extensions()` has no HEIF | PRD T-04 requires HEIC (the iPhone default). |
| B6 | 🟠 Med | **The coach's clock freezes.** The system prompt bakes in `now` when a user's agent is first built, and the agent is cached forever. | `build_coach()` is called once per user per process | "Can I have tea now?" uses the wrong time and day. |
| B7 | 🟠 Med | **The server trusts client-sent calories.** `POST /meals` stores whatever `kcal`/`protein` the client sends, and editing grams doesn't recompute. | `MealItem(**i.model_dump())` | Breaks T-06 and T-07 ("calories come from the database"). |
| B8 | 🟠 Med | **Unmatched foods disappear silently.** `resolve` drops items with no DB match and no AI fallback. | `continue` in `food_logger.resolve` | The user never sees that something was missed, so totals are under-counted. |
| B9 | 🟡 Low | **Profile weight edits are ignored on the same day.** `PUT /profile` only creates today's weight log if none exists, and targets use the latest log. | `profile.py:40-42` | Weight corrections don't take effect until tomorrow. |
| B10 | 🟡 Low | **Logs can become invalid JSON.** The log format string fakes JSON, so any message containing `"` breaks the line. | `observability.py:39` | Log parsing and alerts break. |
| B11 | 🟡 Low | **Uploads are read fully into memory before the size check.** | `meals.py:47` | A large upload can exhaust memory. |

## 3. Gemini usage review (checked against Google's Nov 2026 docs)

| Item | Current code | Google's guidance now | Action |
| --- | --- | --- | --- |
| Model IDs | `gemini-3.8-flash` (vision, coach), `gemini-3.5-flash-lite` (parser) | Both are **stable, current** models | ✅ Keep. `gemini-4-hydrogen` is Google's pick for *new* projects. Evaluate it with `evals/` before switching; don't switch blind. |
| Sampling | `temperature=0.0/0.1/0.3` | Gemini 3.6+ **deprecated** `temperature/top_p/top_k`. They are *ignored* today and will **error on future models**. Control behaviour with `thinking_level` instead. | Remove `temperature`. Add `thinking_level` per role. |
| Thinking | Not set | 3.8 Flash: `low`/`medium`(default)/`high`; `minimal` **returns an error**. 3.5 Flash-Lite: `minimal`(default)/`low`/`medium`/`high` | Vision `low` (8 s p95 target), parser `minimal`, coach `low` (3 s first-token target). All configurable. |
| Image input | `{"type":"image_url","image_url":{"url":"data:…"}}` | The standard LangChain block is `{"type":"image","base64":…,"mime_type":…}`. Google recommends text **before** the image. HEIC/HEIF are supported natively. | Switch to the standard block. Send HEIC as-is when Pillow can't decode it. |
| Timeouts/retries | None | Technical PRD §4: 20 s timeout and 2 retries; 15 s photo budget | `timeout` and `max_retries` on the model, plus an overall `asyncio.timeout` per request. |
| API key | `GOOGLE_API_KEY` | `GOOGLE_API_KEY` first, `GEMINI_API_KEY` as fallback | ✅ Keep. Document it. |
| Structured output | `with_structured_output(Model)` | Default method is `json_schema`, which is recommended | ✅ Correct as is. |

## 4. Code-quality review (what to tune)

**Good, keep it:**
- `core/` is pure and tested.
- The model never does arithmetic.
- Agents are injected as FastAPI dependencies, so tests run offline.
- Coach tools take the user ID by closure, never from model output.
- The safety floor is enforced in code.
- Targets match the reference (BMR 1,884).

**Tune:**

1. **Layering.** The Technical PRD says `api → services → core`, and that `core/` must not import SQLAlchemy. `core/ledger.py` runs DB queries and imports `db`. Split it into `services/` (I/O) and `core/` (maths) in Phase B.
2. **Query cost.** `/today` calls `day_summary` → `current_targets` → `learned_tdee` → a 21-day `daily_frame` plus `get_profile` twice: about 10 queries and a pandas frame per request. Coach tools repeat this per tool call. That's fine for one user. Add `daily_summaries` (Phase C) before many users.
3. **IDs.** These are integers; the Technical PRD specifies UUIDs. Switch **before** there's production data (Phase B, together with Alembic). Later the switch becomes a data migration.
4. **Timezone** is global (`SPOTON_TZ`); the PRD wants it per profile. Fixing B1 by storing UTC makes the later per-user switch easy.
5. **Food DB size** is 55 foods, against a PRD target of ≥500 (T-13). Matching quality (B2) matters more than size, so fix matching first.
6. **CORS** defaults to `*`. Use an allow-list.
7. **Middleware.** `BaseHTTPMiddleware` interferes with SSE streaming. Switch to pure ASGI middleware when adding coach streaming (Phase D).

---

## 5. Fix plan (phase by phase)

Each phase ends green: tests pass, ruff is clean, and the app runs locally. No phase starts until you've seen the previous one.

### Phase A: Stabilise and make it runnable ✅ *implemented in this pass*

| ID | Change | Fixes |
| --- | --- | --- |
| A1 | Gemini 3 config: no sampling params; `thinking_level` per role; `timeout` + `max_retries`; standard image block, text first | §3 |
| A2 | Store all timestamps as UTC (`UTCDateTime` column type); local-day logic converts explicitly | B1 |
| A3 | Token-aware food matching (each word must match), stricter cutoff, plus aliases for common misses | B2 |
| A4 | Draft returns `unresolved` items instead of dropping them | B8 |
| A5 | `POST /meals` recomputes nutrients server-side for database items (grams edits update totals) | B7 |
| A6 | Upload hardening: bounded read, magic-byte sniffing, HEIC pass-through, decode errors → 422 | B5, B11 |
| A7 | Coach: static prompt, current time sent with every message, bounded agent cache, request timeout | B6 |
| A8 | Photo-analysis budget (15 s) → friendly 504 | Technical PRD §4 |
| A9 | Eval runner fixed (async, `src/` layout); runs offline in CI | B3 |
| A10 | `ci.yml` and `evals.yml` rewritten for uv + Python 3.15.2 + current paths | B4 |
| A11 | `.env.example`, `.env` loaded from repo root, CORS allow-list, `LANGSMITH_PROJECT` | §4 |
| A12 | Real JSON log formatter | B10 |
| A13 | Profile weight edit updates today's weight log | B9 |
| A14 | README rewritten: local run, `.env`, models, API map, architecture; module docstrings | Docs |

### Phase B: Finish PRD Phase 0 (Foundation) ✅ *implemented (deploy prepared, not yet run)*

Done in v0.3.0:
- Opaque rotating refresh tokens with reuse detection, logout, 15-min JWT with iss/aud/jti.
- `/v1` paths, `/healthz` and `/readyz`, and the error envelope.
- Rate limits.
- UUID keys with `created_at`/`updated_at`, Alembic baseline, and `alembic check` in CI.
- `services/` split from `core/`.
- Pure-ASGI request middleware.
- Dockerfile, plus `deploy.yml` (off until `DEPLOY_ENABLED=true`).

Not yet: the first real deploy, which needs your GCP project and Neon database.

1. **Auth to spec (F-01, F-02).** Opaque 256-bit refresh tokens stored SHA-256-hashed in `refresh_tokens`, rotated on each refresh, with reuse detection that revokes the token family. Add `POST /v1/auth/logout`. Access JWT lasts 15 min and carries `iss`, `aud` and `jti`. `POST /v1/auth/login` takes JSON; keep the OAuth2 form for Swagger's "Authorize" button.
2. **API shape.** `/v1` prefix; PRD paths (`POST /v1/weights`, `PUT /v1/steps/{date}`, `GET /v1/me`, `GET /v1/targets`); `/healthz` and `/readyz` (DB check); error envelope `{"error":{"code","message","request_id"}}`.
3. **Rate limits.** In-process limiter: login 5/min/IP, AI 30/min/user plus a daily cap, everything else 120/min/user. This is enough for one container; move to Redis/Postgres only when scaling out.
4. **Persistence.** Alembic baseline migration; switch to UUID keys with `created_at`/`updated_at` on every table. Do this before any production data exists.
5. **Layering.** Split `core/ledger.py` into `services/` (DB) and `core/` (pure maths).
6. **Delivery.** Multi-stage uv `Dockerfile`; `deploy.yml` (GHCR → `alembic upgrade head` → Cloud Run → `/readyz` smoke test). This needs your GCP project and Neon DB, so I'll prepare everything and you run the first deploy.

### Phase C: Finish PRD Phase 1 (Core MVP) 🟢 *mostly implemented (v0.4.0)*

| # | Item | Status |
| --- | --- | --- |
| 1 | `Idempotency-Key` on `POST /v1/meals`, `PATCH`/`GET /v1/meals/{id}`, favourites, recent, one-tap repeat (T-06, T-08) | ✅ done |
| 1b | Server-side `meal_drafts` table + `draft_id` | ⏸ deferred: the client sends the reviewed items back and the server recomputes all totals, so a stored draft adds little for now. Revisit for the Android client. |
| 2 | Food graph `extract → compute → validate` (warnings, oily items, `clarify`) | ✅ done in Phase B. Image preprocessing stays in the API layer. |
| 3 | Personal food memory: corrected per-unit values reused next time (`/v1/food-memory`) | ✅ done |
| 3b | Weighed eval set (20+ meals) | ⛔ needs you: weigh real meals; the current truth values are approximate |
| 4 | `daily_summaries` table | ⏸ deferred: not needed at single-user scale; add before many users (NFR ≤ 300 ms) |
| 5 | Per-user timezone | ⏸ deferred to Phase 5 (public users); `/v1/me` exposes the API timezone for clients |
| 6 | `GET /v1/export` (JSON, or CSV as ZIP) (T-12) | ✅ done |
| 7 | **Streamlit client** in `frontend/`: sign in/up, Today, Log meal (camera/upload/text → editable draft), Coach + suggestions, History charts, Profile + food memory + export | ✅ done, with end-to-end tests (AppTest drives the real pages through the real API) |
| 8 | Live food evals gate (kcal MAPE ≤ 25%) | ⛔ needs a key and the weighed set (3b) |

Known limits: web sign-in lasts per browser tab; coach memory resets on API restart (Phase D); photos aren't stored (thumbnails only).

### Phase D: PRD Phase 2 (Coach and suggestions) ✅ *implemented (v0.5.0)*

| PRD | Item | Status |
| --- | --- | --- |
| C-01 | Coach streaming: `POST /v1/coach/messages` with `Accept: text/event-stream` (status → tokens → done); web client streams it | ✅ |
| C-02 | Two suggestions, `mode=my_foods` (default, only available My Foods; falls back to ideal and says so) or `ideal`; code checks totals, calorie fit, My-Foods-only and rules | ✅ |
| C-03 | My Foods with effort levels and meal slots (`GET/PUT /v1/my-foods`, web page) | ✅ |
| C-04 | Food rules: plain English → structured rule (model) → shown back → confirmed → checked in code (`core/rules.py`): nudges on Today, blocked foods never suggested (also tomorrow, for weekly limits) | ✅ |
| C-05 | Conversation memory within a day via LangGraph checkpointer (SQLite file locally, Postgres in production), survives restarts; `GET /v1/coach/threads/{date}`. Across days: My Foods, rules and profile | ✅ (free-form cross-day notes not done) |
| C-06 | Safety: deterministic routing for red-flag symptoms and disordered eating (no model call), calorie floor in code, safety + live-number eval set (`evals/run_coach_evals.py`; offline routing check in CI) | ✅ code; ⛔ the live 100% gate needs your key |

Open: run the live coach evals with your key and tighten the cases. Test the Postgres checkpointer once Neon is set up.

### Phase E: PRD Phase 3 (Progress intelligence) ✅ *implemented (v0.6.0)*

| PRD | Item | Status |
| --- | --- | --- |
| P-01 | Workouts in plain words → activities, minutes, model-estimated MET → kcal (MET equation) | ✅ (since Phase B) |
| P-02 | Smoothed weight trend (EMA) alongside weigh-ins; Progress chart | ✅ |
| P-03 | Learned maintenance: weekly `tdee_estimates`, active after 14 logged days + 6 weigh-ins in 21 days, blended 70/30, capped ±100 kcal/week, plain-language explanation; targets use it | ✅ (matches the hand calculation in `tests/test_progress_core.py`) |
| P-04 | Predictions as ranges: goal-weight date range ("85 kg likely between early-Feb and mid-Apr 2027") and a 4-week weight range | ✅ |
| P-05 | Weekly review every Sunday (Sun–Sat weeks): averages, adherence, trend, waist, at most one proposal; Accept / Keep as is; generated lazily and by `python -m spotonfit.jobs.weekly` (Cloud Run Job in `deploy.yml`) | ✅ (scheduler creation is a one-time manual step) |
| P-06 | Measurements (waist, hip, body fat %); body fat also feeds BMR | ✅ |

Fixed during the live check: the EMA trend was rebuilt inside each 21-day window, which under-stated weight change. On a steady 0.5 kg/week loss it estimated 2,277 instead of 2,489 kcal. It now uses the full-history trend (2,485).

Remaining: a new user's first estimates still lag (there's no history to warm up the trend). The blend and cap limit the effect.

Phases 4–5 (nudges, Android, public launch) stay as written in the PRD.

---

## 7. Decisions

**D1 (19 Nov 2026): nutrition comes from the model, not a food table.**
- *Decision (product owner):* no hard-coded nutrition data. For each food the model estimates quantity, grams per unit, nutrients per unit (oil included), oil level and a remark. Code computes quantity × per-unit and the meal totals.
- *Why:* the 55-food seed table was hand-typed and unverified, covered few dishes, and silently mis-matched foods. Rough but sensible estimates for any dish are preferred.
- *Trade-off:* this reverses PRD goal 2 / T-07 ("calories from the database") and Technical PRD ADR #6. The PRD cites an NIH finding that photo apps under-count by 250–345 kcal per meal, mostly fat.
- *Mitigations in code:*
  - The prompt tells the model to include oil and not to under-count.
  - Calories are checked against macros (4/4/9).
  - Low-confidence items are flagged, and oily items are listed.
  - Every draft is reviewed before saving.
  - Counts are editable without a new model call.
  - The live eval gate (kcal MAPE ≤ 25%) tracks accuracy.
- *Follow-up:* update PRD T-07, T-13 and ADR #6 to match. Build a weighed eval set before trusting the numbers.

**D2:** policy numbers (targets, energy, warnings, rate limits) live in `config.py`, overridable from `.env`. Textbook equations and physical constants stay in code.

---

## 6. Open decisions for you

1. **Python 3.15.2.** It needs a newer uv than 0.12.3 (`uv self update`). The code also runs on 3.14, if you'd rather not move to 3.15 yet.
2. **Client before or after Phase B?** I recommend B first, because the client should be built against the final `/v1` auth contract, not the current one.
3. **`gemini-4-hydrogen`.** Run the eval set on it and on `gemini-3.8-flash` once you have about 20 weighed photo meals, then pick on measured MAPE and latency.

## Sources

- Gemini models list: https://aistudio.google.com/docs/models
- What's new in Gemini 3.8 Flash (thinking levels, deprecated sampling params, pricing): https://aistudio.google.com/docs/whats-new-gemini-3.8?generate-content=true
- Gemini 3.6 API changes (sampling params ignored now, errors in future models): https://ai.google.dev/gemini-api/docs/generate-content/whats-new-gemini-3.6
- Image understanding (formats incl. HEIC/HEIF, 20 MB inline limit, text before image): https://aistudio.google.com/docs/image-understanding
- LangChain Google GenAI integration (env vars, image blocks, `thinking_level`, structured output): https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai
