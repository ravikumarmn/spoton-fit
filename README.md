# SpotOn 💪

An AI personal trainer API for fat loss and muscle building. Snap or type a meal: Gemini identifies each food, **counts** it, and estimates the nutrition of **one** unit (one egg, one idli, one katori of dal, oil included). Code then multiplies and adds, so "6 boiled eggs" becomes 6 × one egg. SpotOn tracks what's left today, suggests what to eat next, answers *"Can I have tea now?"* from your real numbers, and keeps day/week/month/year history.

- Product requirements: [`docs/SpotOn - PRD.md`](docs/SpotOn%20-%20PRD.md)
- Architecture: [`docs/SpotOn - Technical PRD.md`](docs/SpotOn%20-%20Technical%20PRD.md)
- **Status, review, decisions and phased plan: [`docs/REVIEW_AND_PLAN.md`](docs/REVIEW_AND_PLAN.md)**

> **Status (Nov 2026, v0.6.0):**
> - The API and the **Streamlit web app** work end to end locally.
> - Phases A–E of the plan are done, covering PRD Phases 0–3: tracking, coach, and progress intelligence with weekly reviews.
> - PRD Phase 4 (nudges and Android) is next.
> - The plan and what's left are in [`docs/REVIEW_AND_PLAN.md`](docs/REVIEW_AND_PLAN.md).

---

## 1. Run it locally

### Prerequisites

- **uv**, a recent version. The project pins **Python 3.15.2** (`.python-version`), and uv 0.12.x can't download it yet:
  ```bash
  uv self update          # or: brew upgrade uv  (if installed with Homebrew)
  uv lock                 # REQUIRED once after updating: v0.5 added packages the old uv couldn't lock
  ```
- A **Gemini API key** for the AI features (meal analysis, suggestions, coach, workout parsing). Auth, profile, targets, manual meals, water/steps/weight, Today and History work without one.

### Steps

Use two terminals, both in the repository root.

```bash
# one-time setup
cd fitcoach
uv sync --group web               # Python 3.15.2 + API deps + the Streamlit web client
cp .env.example .env              # then put your GOOGLE_API_KEY (and a JWT_SECRET) in .env

# terminal 1: the API (http://127.0.0.1:8000, docs at /docs)
uv run uvicorn spotonfit.api.main:app --reload

# terminal 2: the web app (opens http://localhost:8501)
uv run --group web streamlit run frontend/app.py
```

On startup the API creates or upgrades the local SQLite database (`spotonfit.db` in the current directory) with Alembic migrations, so always start it from the repository root. The web app talks only to the API. Set `SPOTON_API_URL` if the API runs somewhere other than `http://127.0.0.1:8000`.

Checks:
- http://127.0.0.1:8000/healthz shows `"llm_configured": true` once your key is picked up, plus the models in use.
- http://127.0.0.1:8000/readyz confirms the database is reachable.

### Using the web app (http://localhost:8501)

1. **Create account**. You land on **Profile**; fill it in once to get your calorie and protein targets.
2. **Log meal**:
   - Choose 📷 Camera, 🖼️ Upload or ⌨️ Type, add a note if you like, then **Analyze**.
   - Review the draft table: fix a **Count** (totals update live), correct a per-unit value, or add or delete rows. Oily and fried items are flagged, and any doubts appear as warnings.
   - Choose the meal, then **Save meal**.
   - Values you correct are **remembered** for that food next time.
3. **Today**:
   - What's left (calories, protein, carbs, fat, water, steps).
   - 💧 +250/+500 ml buttons; steps, weight and workouts.
   - Today's meals with ⭐ favourite, 🔁 log again, 🗑️ delete.
4. **Coach**:
   - Ask *"Can I have tea now?"*. The reply streams in word by word.
   - Today's conversation is kept: it's still there after a refresh or an API restart.
   - **What should I eat next?** gives two options from **My Foods** or **Any food**; **Review & log this** opens one as a draft.
   - Messages about worrying symptoms (chest pain, fainting, …) or disordered eating get a fixed safety reply, not diet advice.
5. **My foods**:
   - List the foods you can actually get (effort: no cooking / 5-minute / buy nearby / order in).
   - Add food rules in plain words ("idli at most 3 days a week", "no tea after 4 PM"). SpotOn shows how it understood each rule; you confirm it. Rules are then checked against what you log: gentle nudges appear on Today, and blocked foods are never suggested.
6. **Progress**:
   - **Weekly review**, ready every Sunday for the week just finished:
     - days logged, average calories and protein days, and the trend change;
     - at most one suggested change, which you **Accept** or **Keep as is**.
   - Weight with its smoothed **trend**, and a 4-week range.
   - **Learned maintenance** with a plain-language explanation of how it was worked out.
   - "85 kg likely between early-Feb and mid-Apr": always a range.
   - Waist, hip and body-fat measurements.
   - Today shows a banner when a review is waiting.
7. **History**: day/week/month/year charts for calories and protein vs target, steps, and weight with its trend.
8. **Profile**: targets, remembered foods (forget any), **export** your data (JSON or CSV), and sign out.

You can also log a favourite or recent meal again from the ⭐ section on **Log meal**. Sign-in lasts for the browser tab: a refresh or new tab asks you to sign in again (see "Known limits").

### Try it in the browser (Swagger UI at `/docs`)

1. **`POST /v1/auth/register`**: `{"email": "me@example.com", "password": "at-least-8-chars"}` returns tokens.
2. Click **Authorize** (top right) and enter the email as *username* plus the password. Swagger calls `POST /v1/auth/token` and sends the access token on every request. Access tokens last 15 minutes; click Authorize again when one expires.
3. **`PUT /v1/profile`**: for example `{"age": 26, "sex": "male", "height_cm": 177.8, "weight_kg": 92.2, "goal": "lose_fat", "activity": "light", "body_fat_pct": 24}`. The response includes your targets.
4. **`POST /v1/meals/analyze`**: a `note` ("6 boiled eggs and 3 puris") and/or a photo. You get a **draft** and nothing is saved yet. Each item shows `quantity`, `per_unit`, totals, `oil_level` and a `remark`; the draft also lists `oily_items` and `warnings`.
5. **`POST /v1/meals`**: send `slot` (the draft's `meal_slot`) and the `items`, after changing any `quantity` if needed. The server recomputes totals as quantity × per_unit.
6. **`GET /v1/today`**, **`GET /v1/suggestions`** (two meal ideas that fit what's left), **`POST /v1/coach/messages`** (`{"message": "Can I have tea now?"}`).
7. **`POST /v1/water`**, **`PUT /v1/steps/{date}`**, **`POST /v1/weights`**, **`POST /v1/workouts`** (`{"text": "15 min cycling, 40 min weights"}`), then **`GET /v1/history?period=week`**.

### Same thing from Python

```python
import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000")
t = c.post("/v1/auth/register", json={"email": "me@example.com", "password": "demo-pass-123"}).json()
h = {"Authorization": f"Bearer {t['access_token']}"}
c.put(
    "/v1/profile",
    headers=h,
    json={
        "age": 26,
        "sex": "male",
        "height_cm": 177.8,
        "weight_kg": 92.2,
        "goal": "lose_fat",
        "activity": "light",
        "body_fat_pct": 24,
    },
)
draft = c.post("/v1/meals/analyze", headers=h, data={"note": "6 boiled eggs"}, timeout=30).json()
# with a photo: files={"image": open("meal.jpg", "rb")}
c.post("/v1/meals", headers=h, json={"slot": draft["meal_slot"], "items": draft["items"]})
print(c.get("/v1/today", headers=h).json()["left"])
```

---

## 2. The `.env` file

**Location:** the repository root, next to `pyproject.toml` (`fitcoach/.env`). Start from the template with `cp .env.example .env`. It is git-ignored, and real environment variables override it. Every setting is defined and documented in [`src/spotonfit/config.py`](src/spotonfit/config.py).

| Variable | Needed? | What it does |
| --- | --- | --- |
| `GOOGLE_API_KEY` | **Yes, for AI features** | Gemini key from [Google AI Studio → API keys](https://aistudio.google.com/apikey) (`GEMINI_API_KEY` also works). Without it, AI endpoints return **503** `ai_not_configured`. |
| `JWT_SECRET` | Recommended (required in prod) | Signs access tokens. If unset in dev, a random key is used and everyone is logged out on restart. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `DATABASE_URL` | No | Default `sqlite+aiosqlite:///./spotonfit.db`. Postgres URLs (Neon/Supabase) are converted to `asyncpg`. |
| `AUTO_MIGRATE` | No | `true` (dev) applies migrations on startup; production sets `false` and migrates in the deploy pipeline. |
| `SPOTON_TZ` | No | Timezone for "today" and day boundaries (default `Asia/Kolkata`). |
| `SPOTON_*_MODEL`, `SPOTON_*_THINKING` | No | Models and reasoning depth (section 3). |
| `TARGETS__*`, `ENERGY__*`, `ESTIMATES__*`, `LIMITS__*` | No | Policy overrides: deficit, protein per kg, floors, TDEE window, warning thresholds, rate limits. Examples are in `.env.example`. |
| `CORS_ORIGINS` | No | JSON list of browser origins allowed to call the API. |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | No | Trace every graph node, tool call and model call in LangSmith. |

> **Privacy:** for real meal photos, use a key from a **paid** (billing-enabled) Google Cloud project. Free-tier content may be used to improve Google's products.

---

## 3. Models, and how nutrition is estimated

All models load through LangChain's `init_chat_model(..., model_provider="google_genai")` ([`agents/models.py`](src/spotonfit/agents/models.py)), backed by `langchain-google-genai` 4.5 on the official `google-genai` SDK.

| Role | Default model | Thinking level |
| --- | --- | --- |
| Meal photo/text → foods, counts, nutrition per unit, oiliness | `gemini-3.8-flash` | `low` |
| Coach (tool calling) | `gemini-3.8-flash` | `low` |
| Workouts (activity, minutes, MET) and meal suggestions | `gemini-3.5-flash-lite` | `minimal` |

Both IDs were checked against Google's model list (Nov 2026) and are stable. Rules this code follows:

- **No `temperature`/`top_p`/`top_k`.** These are deprecated from Gemini 3.6 on: ignored today, and an error on future models. Use `thinking_level`: `gemini-3.8-flash` accepts `low|medium|high` (**`minimal` is an error**), and `gemini-3.5-flash-lite` accepts `minimal|low|medium|high`.
- **Structured output.** `with_structured_output(...)` uses the recommended `json_schema` method. The field descriptions in [`agents/schemas.py`](src/spotonfit/agents/schemas.py) are part of the instructions.
- **Images** are sent as `{"type": "image", "base64": ..., "mime_type": ...}` with the text **before** the image. Photos are resized to ≤ 1024 px and stripped of EXIF/GPS. HEIC is sent to Gemini as-is.
- Each call has a **20 s timeout and 2 retries**. Photo analysis has a 15 s budget (then a 504).

### What the model does vs what code does

```
photo / note ──► Gemini (structured output, per food):
                   name, quantity (count), unit, grams_per_unit,
                   per_unit {kcal, protein, carbs, fat, fibre}  ← ONE unit, oil included
                   oil_level (none/light/medium/heavy), remark ("deep-fried, very oily"), confidence
             ──► code:  totals = quantity × per_unit;  meal totals = Σ items
             ──► code:  checks → warnings
                   • calories vs 4·protein + 4·carbs + 9·fat (flags inconsistent estimates)
                   • low confidence → "check this item"
                   • oil_level medium/heavy → listed in oily_items
             ──► draft (nothing saved) ──► you edit counts ──► POST /v1/meals (server recomputes)
```

Example: a photo of 6 boiled eggs. Gemini returns `quantity: 6`, and `per_unit` of about 72 kcal and 6.3 g protein. Code shows **432 kcal and 37.8 g protein**. Change the count to 4 and it becomes 288 kcal, with no second model call.

**There is no food table and no hard-coded nutrition data.** Per-unit values are the model's estimates: right ballpark, not lab values. They're always shown for review before saving, and accuracy is tracked with evals (section 5). Workouts work the same way: the model estimates the MET (intensity) for each activity, and code applies `kcal = MET × your weight × hours`.

**What stays in code:**
- Textbook equations: Mifflin-St Jeor and Katch-McArdle for BMR, the MET equation.
- Physical constants: 4/4/9 kcal per gram of protein, carbs and fat.

Every tunable number (deficit %, protein g/kg, floors, step ramp, TDEE window, warning thresholds, rate limits, image sizes) is in `config.py` and can be overridden from `.env`.

---

## 4. API overview (`/v1`)

All errors use one envelope: `{"error": {"code", "message", "request_id"}}`. Every response carries an `X-Request-ID` header.

| Area | Endpoints |
| --- | --- |
| Ops (public) | `GET /healthz` · `GET /readyz` |
| Auth | `POST /v1/auth/register` · `/login` (JSON) · `/token` (form, Swagger) · `/refresh` · `/logout` · `GET /v1/me` |
| Profile | `GET/PUT /v1/profile` · `GET /v1/targets` |
| Meals | `POST /v1/meals/analyze` · `POST /v1/meals` (`Idempotency-Key` header) · `GET /v1/meals?date=` · `GET /v1/meals/recent` · `GET /v1/meals/favourites` · `GET/PATCH/DELETE /v1/meals/{id}` · `POST /v1/meals/{id}/repeat` · `POST /v1/meals/{id}/photo` |
| Food memory | `GET /v1/food-memory` · `DELETE /v1/food-memory/{id}` (your corrected per-unit values, reused next time) |
| Data | `GET /v1/export?format=json\|csv` (everything you logged; CSV comes as a ZIP) |
| Tracking | `POST /v1/water` · `PUT /v1/steps/{date}` · `POST /v1/weights` · `POST /v1/workouts` · `GET /v1/today?date=` · `GET /v1/history?period=&from=&to=` |
| My Foods & rules | `GET/PUT /v1/my-foods` · `POST /v1/rules/parse` (plain English → rule, not saved) · `POST /v1/rules` · `GET /v1/rules` (with today's status) · `DELETE /v1/rules/{id}` |
| Progress | `GET /v1/progress` · `GET /v1/reviews/weekly` · `GET /v1/reviews` · `POST /v1/reviews/{id}/decision` (`accept`\|`reject`) · `POST/GET /v1/measurements` |
| AI | `GET /v1/suggestions?mode=my_foods\|ideal` · `POST /v1/coach/messages` (JSON, or SSE with `Accept: text/event-stream`) · `GET /v1/coach/threads/{date}` |

**Progress (how the numbers are made).** Weeks run Sunday to Saturday (`WEEK_STARTS_ON`). For every finished week, `services/progress.py` does two things.

- **Learned maintenance.** It estimates maintenance as average intake minus trend change × 7,700 ÷ days, over the 21 days to the week's end. This needs at least 14 logged days and 6 weigh-ins. The trend is the smoothed weight over **all** weigh-ins, so it isn't lagging. The result is blended 70/30 with the previous estimate, moves at most 100 kcal a week, and is saved with an explanation. Targets then use it.
- **Weekly review.** It writes a review with at most one proposal:
  - losing faster than 1% of body weight a week → **+100 kcal** (safety);
  - trend flat for 2 weeks while logging consistently → **+1,500 steps**, or **−100 kcal** if steps are at the cap (never below the floor);
  - inconsistent logging → no change.

  Accepting a proposal adjusts your targets. All thresholds are in `config.py` (`REVIEWS__*`, `ENERGY__*`).

Reviews are generated when you open the app (idempotent) and by the weekly job `python -m spotonfit.jobs.weekly`, which `deploy.yml` deploys as a Cloud Run Job. Schedule it with Cloud Scheduler; the command is at the top of `deploy.yml`.

**Coach streaming (SSE).** With `Accept: text/event-stream`, the coach sends `event: status` (it's checking something, e.g. `get_today`), then `event: token` chunks, then `event: done` with the full reply. Errors arrive as `event: error`.

**Safety.** Before the model sees a message, `agents/safety.py` checks it against configured phrases (`config.SafetyPolicy`): red-flag symptoms get a "see a doctor / call 112" reply, and signs of disordered eating or self-harm get a supportive reply with the Tele-MANAS helpline (14416). The model is never asked for diet advice in those cases. The calorie floor is enforced in code (`core/targets.py`).

**Sessions.** The access token is a 15-minute JWT (`iss`, `aud` and `jti` are checked). The refresh token is opaque, stored only as a SHA-256 hash, and **rotates on every refresh**. Replaying an old refresh token revokes that whole login session. Logout revokes the session.

**Rate limits** (per process, configurable):
- Login/token/register: 5 per minute per IP.
- AI endpoints: 30 per minute and 100 per day per user.
- Everything else: 120 per minute per user.

The API returns `429` with a `Retry-After` header when a limit is hit.

---

## 5. Tests, migrations, evals

```bash
uv run pytest -q                                  # all tests; no API key needed (models are stubbed)
uv run ruff check . && uv run ruff format --check .
uv run alembic upgrade head                       # apply migrations to DATABASE_URL
uv run alembic revision --autogenerate -m "..."   # after changing db.py; review the file
uv run alembic check                              # fails if models and migrations differ (CI runs this)
uv run python evals/run_evals.py --stub           # offline pipeline check (CI)
uv run python evals/run_evals.py                  # live Gemini; fails if calorie MAPE > 25%
uv run python evals/run_coach_evals.py --stub     # safety routing, offline (CI; gate 100%)
uv run python evals/run_coach_evals.py            # live coach: safety 100% + live numbers >= 95%
```

Coach evals (`evals/data/coach_cases.jsonl`) cover five kinds of case:
- red-flag symptoms,
- disordered eating,
- unsafe restriction ("800 kcal today?"),
- shaming bait,
- whether answers quote your **real** numbers.

They run against a seeded user with a known day. The graders are simple substring checks, so read `coach_eval_results.json` after a live run and tighten the cases.

The eval ground truth in `evals/data/text_meals.jsonl` is **approximate**: it was computed from the old seed table, not weighed. To get a real accuracy number, replace it with meals you weigh yourself, with nutrition from IFCT or the package label.

## 6. Deploy (Cloud Run + Neon, on every push to `main`)

Push to `main` → **CI** (tests, lint, mobile tests) → **Deploy** (`.github/workflows/deploy.yml`):
build the image → Artifact Registry → migrations on Neon → Cloud Run → `/readyz` smoke test →
signed Android APK pointing at the new server, published as a GitHub Release (`app-v1.0.<run>`) and at the
public download link **https://storage.googleapis.com/spoton-fit-app-downloads/SpotOn.apk** (always the newest).

| Piece | Where |
| --- | --- |
| API | Cloud Run service `spotonfit-api`, project `spoton-fit-app`, region `asia-southeast1` (Singapore). Scales to zero, max 2 instances. |
| Database | Neon project `spoton-fit`, `aws-ap-southeast-1`, branch `main` (direct connection; see below). |
| Secrets | Secret Manager: `spotonfit-jwt-secret`, `spotonfit-google-api-key`, `spotonfit-database-url`. Cloud Run reads them at runtime; they are not in GitHub. |
| GitHub → Google | Workload Identity Federation (pool `github`, only this repo), service account `spoton-deployer`. No JSON keys. |
| Runtime identity | Service account `spoton-runtime` (can read the three secrets, nothing else). |
| App signing key | `~/development/keys/spoton-release.jks` (+ `.properties`), backed up in Secret Manager as `spoton-android-keystore-b64` / `-password`, and in GitHub secrets for CI. **Never lose it**: Android refuses updates signed with a different key. |

Notes:
- **Direct, not pooled, Neon URL.** asyncpg and psycopg use prepared statements, which PgBouncer's
  transaction pooling can break. Max 2 instances × small pools stays far below Neon's connection limit.
- **Change a secret:** `printf '%s' "$NEW" | gcloud secrets versions add spotonfit-google-api-key --data-file=- --project spoton-fit-app`, then redeploy (re-run the Deploy workflow).
- **Weekly review job:** deployed as Cloud Run Job `spotonfit-weekly` but not scheduled; reviews are also
  created when a user opens Progress. To schedule it, see the comment at the top of `deploy.yml`.
- **Local release APK** (same key): `flutter build apk --release --dart-define=SPOTON_API_URL=<Cloud Run URL>`
  in `mobile/` (reads `mobile/android/key.properties`, git-ignored).

## 7. Project layout

```
src/spotonfit/
  config.py            all settings and tuning policies (env / .env)
  db.py                SQLAlchemy models (UUID ids, UTC timestamps, refresh tokens)
  observability.py     JSON logs, request ids, hashed user ids, LangSmith/MLflow
  core/                pure maths: nutrition (count × per-unit), targets, trend/TDEE
  services/            DB-facing logic: ledger (today/history), auth (tokens), suggestions
  agents/              food_logger (LangGraph), suggester, activity parser, coach (Deep Agents), models
  api/                 app factory, routers (/v1), schemas, errors, rate limits, security
  migrations/          Alembic (python -m spotonfit.migrations)
frontend/              Streamlit web client: app.py (navigation), client.py (API + token refresh),
                       components.py, pages/ (login, today, log_meal, coach, plan, progress, history, profile)
evals/ · tests/ · docs/ · Dockerfile · alembic.ini · .github/workflows/{ci,evals,deploy}.yml
```

## 8. Mobile app (Android and iOS)

A Flutter app in [`mobile/`](mobile/README.md) covers everything the web app does, designed for one hand: Today, a camera-first **+ Log**, the coach, progress and a weekly review.
See [`mobile/README.md`](mobile/README.md) to run it and build an APK, and [`docs/MOBILE_PLAN.md`](docs/MOBILE_PLAN.md) for the design and what's left.
For a phone on your Wi-Fi, start the API with `--host 0.0.0.0` and enter your computer's address in the app.
The API also gained `DELETE /v1/account` (needs the password; removes everything, including the coach's saved conversations), which the stores require.

## 9. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `uv sync` says no Python 3.15.2 download is available | `uv self update` (or `brew upgrade uv`), then `uv sync` |
| `uv sync --locked` reports the lockfile is out of date | Run `uv lock` once (needs the updated uv). v0.5 added `langgraph-checkpoint-postgres`, `langgraph-checkpoint-sqlite` and `psycopg`, which the old uv couldn't lock. Plain `uv sync` updates the lock automatically. |
| 503 `ai_not_configured` | Put `GOOGLE_API_KEY=...` in `.env` at the repo root and restart uvicorn |
| 502 mentioning `thinking_level` | `minimal` isn't valid for `gemini-3.8-flash`; use `low`, `medium` or `high` |
| 401 in Swagger after a while | Access tokens last 15 minutes; click **Authorize** again |
| 409 `profile_required` | `PUT /v1/profile` first |
| Web app says "Can't reach the SpotOn API" | Start the API (terminal 1), or set `SPOTON_API_URL` |
| Web app asks to sign in after a page refresh | Expected for now: the session lives in the browser tab (see Known limits) |

### Known limits (v0.6.0)

- **Web sign-in lasts for the browser tab.** It doesn't persist across refreshes, because Streamlit can't set secure cookies. A persistent login comes with the Android/web client work.
- **Coach memory** lasts within a day (one thread per day). Across days, the coach knows your preferences through My Foods, rules and your profile; free-form notes ("remember I'm vegetarian on Tuesdays") aren't stored yet.
- **Safety routing** uses phrase matching. It's cautious (it may also trigger on "no chest pain"), and it can miss phrasings it doesn't know; extend `SAFETY__*_TERMS`.
- **The Postgres checkpointer** is wired and configured but has only been tested against SQLite here (no local Postgres).
- **Learned maintenance needs history.** A new user's first estimates lag the real weight trend, because there are no earlier weigh-ins to warm the trend up. The 70/30 blend and the 100 kcal weekly cap keep this from swinging targets.
- **Weekly reviews** use your current profile for past weeks. If you changed your goal mid-way, older reviews are recomputed against the new goal only for weeks not yet reviewed.
- **Meal photos are not stored**; only an optional thumbnail is. Object storage is planned.
- **"Today" uses one timezone** (`SPOTON_TZ`) for all users; per-user timezones are planned.
| Startup error about tables/migrations on an old `spotonfit.db` | The schema changed in v0.3 (UUID ids). Delete the old local `spotonfit.db`; it will be recreated |

*AI nutrition values are estimates. Not medical advice.*
