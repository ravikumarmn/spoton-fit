# SpotOn — Technical PRD

*Architecture · stack · APIs · data · AI agents · security · CI/CD · phase-wise delivery · v1.0 · 18 Nov 2026*

## Document control

| Item | Detail |
| --- | --- |
| Product PRD | SpotOn — Product Requirements Document (requirement IDs referenced below) |
| Runtime | **Python 3.15.2**, managed with **uv** |
| API | **FastAPI**, fully **async**, **Pydantic v2**, **JWT** auth |
| Agents | **LangChain**, **LangGraph**, **Deep Agents**; model: **Gemini** |
| Observability | Structured logging, **LangSmith**, **MLflow** |
| Delivery | **GitHub** repo, **GitHub Actions** CI/CD: push to `main` → tested → deployed |
| Status | Stack verified: every dependency below installs and imports on Python 3.15.2 |

## 1. Architecture overview

*The diagram that was here showed the original plan (Streamlit first, Android later). The current architecture is in [`../ARCHITECTURE.md`](../ARCHITECTURE.md).*

**Design principles**

1. **API-first.** All logic lives behind a versioned REST API (`/v1`). Clients (Streamlit web now, Android later) are thin.
2. **LLMs perceive and talk; code calculates and decides.** Gemini identifies foods and writes answers. Calories, targets, rules and nudges are deterministic Python, unit-tested.
3. **Async end to end.** FastAPI async routes, SQLAlchemy async sessions, async LangGraph (`ainvoke`/`astream`), async Gemini calls. CPU-bound work (image resizing) runs in a thread pool.
4. **Stateless API containers.** State lives in Postgres (data + LangGraph checkpoints) and object storage (photos), so the API scales horizontally.
5. **Observable by default.** Every request has a request ID; every AI step is traced.

## 2. Technology stack (verified on Python 3.15.2)

| Layer | Package | Verified version | Purpose |
| --- | --- | --- | --- |
| Runtime | CPython | 3.15.2 | Language runtime (`.python-version`) |
| Packaging | uv | recent release (`uv self update`) | Dependencies, lockfile, virtualenv, Python install |
| Web framework | fastapi | 0.163.2 | Async REST API, OpenAPI docs |
| ASGI server | uvicorn[standard] | 0.54.0 | Production server (uvloop, httptools) |
| Validation | pydantic | 2.14.3 | Request/response models, LLM structured output |
| Settings | pydantic-settings | 2.16.3 | Typed config from env/secrets |
| ORM | sqlalchemy[asyncio] | 2.1.9 | Async ORM and queries |
| DB driver | asyncpg | 0.32.0 | Async Postgres driver |
| DB (tests/local) | aiosqlite | 0.22.1 | Async SQLite for fast tests |
| Migrations | alembic | 1.20.1 | Schema migrations |
| JWT | pyjwt | 2.15.1 | Access-token signing and verification |
| Passwords | pwdlib[argon2] | 0.4.2 | Argon2id password hashing |
| Uploads | python-multipart | 0.0.34 | Photo uploads (multipart/form-data) |
| HTTP client | httpx | 0.28.1 | Outbound calls; async test client |
| Agents | langchain | 1.5.0 | Models, tools, structured output |
| Orchestration | langgraph | 1.2.22 | Food-logging graph; durable state |
| Agent harness | deepagents | 0.7.39 | Coach agent (planning, tools, memory) |
| Checkpointing | langgraph-checkpoint-postgres | 3.2.1 | Coach conversation state in Postgres |
| Postgres (checkpointer) | psycopg[binary] | 3.3.9 | Driver used by the LangGraph checkpointer |
| Model provider | langchain-google-genai | 4.5.0 | Gemini (`gemini-3.8-flash`, `gemini-3.5-flash-lite`) |
| Tracing | langsmith | 0.15.0 | Traces, datasets, online evaluation |
| Images | pillow | 13.0.0 | Resize, EXIF strip, thumbnails |
| Eval tracking | mlflow | 3.18.0 (dev/CI) | Eval runs, metrics, artifacts; optional tracing |
| Tests | pytest 9.2.0, pytest-asyncio 1.5.0 | | Unit, integration, API tests |
| Quality | ruff 0.17.5, mypy 2.4.1 | | Lint/format, type checking |
| Web client (Ph 0–3) | streamlit | 1.67+ | Thin Python client calling the API |

**Note:** older uv releases can't download CPython 3.15.2. Run `uv self update`, and pin uv in `pyproject.toml` (`[tool.uv] required-version`) so local and CI use the same uv.

## 3. Repository structure

```
spotonfit/
├── pyproject.toml          # deps, tool config (ruff, mypy, pytest), [tool.uv]
├── uv.lock                 # locked, reproducible dependency set
├── .python-version         # 3.15.2
├── Dockerfile              # multi-stage, uv-based
├── alembic.ini
├── migrations/             # Alembic versions
├── src/spotonfit/
│   ├── main.py             # app factory, lifespan (DB pool, checkpointer, tracing)
│   ├── config.py           # pydantic-settings Settings
│   ├── api/
│   │   ├── deps.py         # get_session, get_current_user, rate limit
│   │   └── v1/             # auth, profile, meals, today, history, water, steps,
│   │                       # weights, workouts, coach, suggestions, foods, rules, export
│   ├── schemas/            # Pydantic request/response models (API contract)
│   ├── security/           # jwt.py, passwords.py, tokens.py
│   ├── db/                 # base.py, models.py, session.py, repositories/
│   ├── services/           # meal_service, coach_service, history_service, ...
│   ├── core/               # PURE domain logic: targets, foods, ledger, suggest, rules, tdee
│   ├── agents/             # food_graph.py (LangGraph), coach.py (Deep Agents),
│   │                       # parser.py, prompts/, schemas.py (LLM structured outputs)
│   ├── storage/            # photo storage (local disk / S3-compatible)
│   └── observability/      # logging.py, request_id middleware, tracing setup
├── clients/streamlit/      # thin web client (calls the API with JWT)
├── evals/                  # datasets + runner (logs to MLflow)
├── tests/
│   ├── unit/               # core/ and agents/ with fake models
│   ├── integration/        # repositories + Postgres (service container in CI)
│   └── api/                # httpx.AsyncClient against the ASGI app
└── .github/workflows/      # ci.yml, deploy.yml, evals.yml
```

**Layering rule:** `api → services → (core, agents, db)`. `core/` imports nothing from FastAPI, SQLAlchemy or LangChain, so it stays pure and easy to test.

## 4. Async request lifecycle

1. **Middleware** assigns `X-Request-ID`, starts a timer, and binds the request ID and user ID to logging via `contextvars`.
2. **Auth dependency** verifies the JWT (signature, `exp`, `iss`, `aud`) and loads the user.
3. **Session dependency** yields an `AsyncSession` (one per request, committed in the service layer).
4. **Service** runs domain logic. AI calls use `await graph.ainvoke(...)`; image resizing uses `await asyncio.to_thread(...)`.
5. **Response** is a Pydantic model, so OpenAPI docs stay accurate automatically.

**Lifespan (startup/shutdown):** create the SQLAlchemy async engine (pool size 5–10), open the `AsyncPostgresSaver` checkpointer, configure LangSmith/MLflow, warm the food index, and dispose of all of them on shutdown.

**Timeouts and retries:** Gemini calls 20 s timeout with 2 retries (exponential backoff); DB statement timeout 5 s; total photo-analysis budget 15 s, returning a friendly error if exceeded.

## 5. Authentication and security (JWT)

| Element | Design |
| --- | --- |
| Password storage | Argon2id via `pwdlib`; never logged |
| Access token | JWT, **15 min** lifetime. Phase 0–4: HS256 with a 256-bit secret. Phase 5: EdDSA/RS256 with key rotation (`kid` header) |
| Claims | `sub` (user UUID), `iat`, `exp`, `iss` = spotonfit-api, `aud` = spotonfit-clients, `jti`, `scope` |
| Refresh token | Opaque 256-bit random string, **30-day** lifetime, stored **hashed** (SHA-256) in `refresh_tokens` |
| Rotation | Each refresh issues a new pair and revokes the old token; reuse of a revoked token revokes the whole token family |
| Transport | Mobile/Streamlit: `Authorization: Bearer`. Browser clients: refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie |
| Logout | Revokes the refresh-token family; access token expires within 15 min |
| Rate limits | Login 5/min/IP; AI endpoints 30/min/user and a daily cap; general 120/min/user |
| Uploads | ≤ 10 MB; type sniffed from magic bytes; EXIF (incl. GPS) stripped; resized to ≤ 1024 px before AI |
| CORS | Allow-list of client origins only |
| Secrets | GitHub Actions secrets → deployed as runtime secrets; never in the repo |
| Data rights | `GET /v1/export` and `DELETE /v1/account` (Phase 5 hard requirement) |
| Phase 5 | Google sign-in (OIDC): verify Google ID token, then issue SpotOn JWTs |

## 6. API specification (v1)

All endpoints return JSON. Errors follow `{"error": {"code", "message", "request_id"}}`. Auth: Bearer JWT unless marked public.

| Phase | Method & path | Purpose | Notes |
| --- | --- | --- | --- |
| 0 | `POST /v1/auth/register` | Create account | Public; returns tokens |
| 0 | `POST /v1/auth/login` | Log in | Public; rate-limited |
| 0 | `POST /v1/auth/refresh` | Rotate tokens | Public (refresh token) |
| 0 | `POST /v1/auth/logout` | Revoke session | |
| 0 | `GET /v1/me` | Current user | |
| 0 | `GET /healthz`, `GET /readyz` | Liveness / readiness (DB check) | Public |
| 1 | `GET / PUT /v1/profile` | Read / update profile | |
| 1 | `GET /v1/targets` | Today's targets | Uses learned TDEE in Phase 3 |
| 1 | `POST /v1/meals/analyze` | Photo (multipart) and/or text → **draft** | Not saved; returns `draft_id`, items, totals, `clarify` |
| 1 | `POST /v1/meals` | Save a confirmed meal (from draft, edited) | Idempotency-Key header |
| 1 | `GET /v1/meals?date=` · `PATCH / DELETE /v1/meals/{id}` | List / edit / delete | |
| 1 | `POST /v1/meals/{id}/repeat` · `GET /v1/meals/favourites` | Repeat / favourites | P1 |
| 1 | `POST /v1/water` · `PUT /v1/steps/{date}` · `POST /v1/weights` | Quick logs | |
| 1 | `GET /v1/today` | Eaten / burned / left + next best move | |
| 1 | `GET /v1/history?period=&from=&to=` (period: day, week, month, year) | Aggregates from start date | |
| 1 | `GET /v1/foods/search?q=` | Food database search | |
| 1 | `GET /v1/export` | CSV/JSON export | P1 |
| 2 | `POST /v1/coach/messages` | Ask the coach; **SSE streaming** | Thread per user per day |
| 2 | `GET /v1/coach/threads/{id}` | Conversation history | |
| 2 | `GET /v1/suggestions?mode=` (my_foods or ideal) | Two meal options | |
| 2 | `GET / PUT /v1/my-foods` | My Foods list | |
| 2 | `GET / POST / DELETE /v1/rules` | Food rules (NL → JSON, confirm) | |
| 3 | `POST /v1/workouts` | Text → parsed workouts → saved | |
| 3 | `GET /v1/progress` | Weight trend, learned TDEE, prediction range | |
| 3 | `GET /v1/reviews/weekly` · `POST /v1/reviews/{id}/decision` | Weekly review; accept/reject | |
| 3 | `POST /v1/measurements` | Waist, hip, body fat | |
| 4 | `POST /v1/devices` | Register push token (FCM) | |
| 4 | `POST /v1/activity/samples` | Step/activity samples from Android | Batched |
| 4 | `GET / PUT /v1/notification-settings` | Quiet hours, caps, strict mode | |
| 5 | `POST /v1/auth/google` · `DELETE /v1/account` | Google sign-in; account deletion | |

## 7. Data model (PostgreSQL)

All tables have `id` (UUID), `created_at`, `updated_at`, and `user_id` (FK, indexed) where user-owned. Timestamps are `timestamptz`; the user's timezone is stored on the profile and all "day" logic uses it.

| Table | Key columns | Phase |
| --- | --- | --- |
| `users` | email (unique, citext), password_hash, is_active, created_at | 0 |
| `refresh_tokens` | user_id, token_hash, family_id, expires_at, revoked_at, user_agent | 0 |
| `profiles` | age, sex, height_cm, goal, activity, body_fat_pct, goal_weight_kg, timezone, start_date | 1 |
| `targets` | effective_from, kcal, protein_g, fat_g, carbs_g, fibre_g, water_ml, steps, source | 1 |
| `foods` | name, aliases[], source (INDB/IFCT/OFF/user/ai), per-100 g kcal/protein/carbs/fat/fibre | 1 |
| `portions` | food_id, unit, grams, user_id (null = global) | 1 |
| `meal_drafts` | items (JSONB), totals, image_key, model, expires_at | 1 |
| `meals` | eaten_at, slot, note, source, image_key, is_favourite | 1 |
| `meal_items` | meal_id, food_id, name, grams, kcal, protein, carbs, fat, fibre, origin (db/ai/edited) | 1 |
| `water_logs`, `step_logs`, `weight_logs` | at/day, ml / steps / kg | 1 |
| `daily_summaries` | day (unique per user), totals, targets snapshot, on_target | 1 |
| `my_foods` | food_id, effort, slots[], available | 2 |
| `rules` | rule JSONB, original_text, active | 2 |
| *(LangGraph tables)* | checkpoints, writes (managed by `AsyncPostgresSaver`) | 2 |
| `workouts` | at, activity, minutes, met, kcal, raw_text | 3 |
| `tdee_estimates` | week_start, tdee, uncertainty | 3 |
| `weekly_reviews` | week_start, summary JSONB, proposal JSONB, decision | 3 |
| `measurements` | day, waist_cm, hip_cm, body_fat_pct | 3 |
| `devices`, `activity_samples`, `notifications` | push tokens; 15-min step/activity buckets; sent nudges + outcome | 4 |

`daily_summaries` is updated on every write and makes week/month/year history a cheap `GROUP BY date_trunc(...)`. Migrations are managed by Alembic and run as a deploy step.

## 8. AI and agents

### 8.1 Models

| Use | Model (configurable) | Why |
| --- | --- | --- |
| Food photo/text understanding | `gemini-3.8-flash` | Strong vision; fast |
| Parsing (workouts, rules) | `gemini-3.5-flash-lite` | Cheap, simple extraction |
| Coach | `gemini-3.8-flash` | Tool use + reasoning |

All models load through `init_chat_model(..., model_provider="google_genai")`, so swapping provider is a config change. Use a **paid** Gemini project so user content isn't used for product improvement.

### 8.2 Food-logging graph (LangGraph)

```
START → preprocess (resize, strip EXIF; to_thread)
      → extract (Gemini, structured output: MealEstimate)
      → resolve (code: personal portions → food DB → nutrients; oil adjustment)
      → validate (sanity checks: grams range, totals, confidence → clarify?)
      → END  (draft saved to meal_drafts)
```

- `MealEstimate` (Pydantic): items[name, quantity, unit, est_grams, oil_level, confidence, fallback_per_100g?], meal_slot, clarify?
- The prompt includes known food names and household units; the user's note overrides the image.
- AI-estimated foods (not in DB) are flagged and stored as `origin = ai`.
- Saved only after user confirmation (`POST /v1/meals`), which protects data quality.

### 8.3 Coach (Deep Agents)

- `create_deep_agent(model, tools, system_prompt, checkpointer=AsyncPostgresSaver)`; thread ID = `user_id:date`.
- **Tools (async, user-scoped, read-only unless stated):** `get_today`, `get_targets`, `lookup_food`, `simulate_add`, `suggest_meal(mode)`, `get_history(period)`, `get_progress`, `get_rules`; `log_food` *(write, requires explicit user confirmation)*.
- The user ID is injected server-side into each tool, never taken from model output, so one user can't read another's data.
- **Guardrails:** answer only from tool results; hard calorie floor enforced in `core/` (not just the prompt); red-flag symptoms → doctor; no shaming; supplements never mandatory.
- **Streaming:** `astream` → Server-Sent Events to the client.

### 8.4 Cost and latency controls

Images ≤ 1024 px JPEG · one model call per photo · small model for parsing · cached food index · per-user daily AI cap · prompt and response token logging for cost tracking.

## 9. Core algorithms (in `core/`, pure Python)

| Algorithm | Specification |
| --- | --- |
| BMI | kg ÷ m² |
| BMR | Katch-McArdle if body fat known (370 + 21.6 × lean kg), else Mifflin-St Jeor |
| Maintenance | BMR × activity factor (1.2 / 1.375 / 1.55 / 1.725); replaced by learned TDEE (Phase 3) |
| Calorie target | Lose fat: −20%; build muscle: +8%; maintain: 0. Rounded **up** to 10; floor = max(BMR, 1,500 men / 1,200 women) |
| Protein | 1.7 g/kg (fat loss), 2.0 (muscle), 1.6 (maintain) × reference weight (goal weight or lean-mass based when body fat is high) |
| Fat / carbs / fibre / water | Fat max(27% kcal, 0.6 g/kg); carbs = remainder; fibre 14 g/1,000 kcal; water 35 ml/kg |
| Steps target | Baseline + 500 per week, max 10,000 |
| Calories burned (est.) | BMR × fraction of day + steps × 0.5 kcal/kg/km + Σ MET × kg × h |
| Weight trend | EMA, α = 0.1 |
| Learned TDEE | 21-day window, ≥ 14 logged days: avg intake − Δtrend × 7,700 ÷ days; blended 70/30 with prior |
| Prediction | trend − (TDEE − planned) × days ÷ 7,700, ±150 kcal band |
| Suggestions | Combinations of 1–3 My Foods at usual portions; score = protein gap closed − calorie overshoot − repeats − complexity; top 2 disjoint |
| Nudges (Ph 4) | Priority rules: quiet hours → post-workout meal → sitting ≥ 45 min → water → missed meal → protein/steps behind curve; caps and cooldowns |

## 10. Observability

| Signal | Implementation |
| --- | --- |
| Logs | JSON lines to stdout: timestamp, level, request_id, user_id (hashed), route, status, latency_ms, event |
| Request IDs | Middleware sets/propagates `X-Request-ID`; returned on every response and error |
| AI traces | **LangSmith**: every graph node, tool call, model call; metadata = user (hashed), thread, model, version |
| Evals | **MLflow**: eval runs (food MAPE, coach correctness, safety), params (model, prompt version), artifacts |
| Optional | MLflow tracing via `mlflow.langchain.autolog()` when `MLFLOW_TRACKING_URI` is set |
| Metrics | Request count/latency by route, AI latency and tokens, error rate (from logs; OpenTelemetry in Phase 5) |
| Alerts (Ph 1+) | Error rate > 2% for 10 min; p95 photo analysis > 12 s; failed deploy |

## 11. Testing strategy

| Layer | Tooling | Scope | Gate |
| --- | --- | --- | --- |
| Unit | pytest | `core/` formulas, food matching, suggestions, rules, TDEE | ≥ 90% coverage of `core/` |
| Agents (offline) | pytest + fake chat models | Graph wiring, resolve logic, tool outputs, coach build | All pass |
| API | pytest-asyncio + `httpx.AsyncClient(ASGITransport)` + aiosqlite | Auth flows, every endpoint, auth isolation between users | All pass |
| Integration | Postgres service container in CI | Repositories, migrations, checkpointer | All pass |
| Evals (live) | `evals/` + Gemini + MLflow | Food MAPE, coach correctness, safety prompts | Food kcal MAPE ≤ 20–25%; safety 100% |
| Load (Phase 5) | Locust (Python) | 50 RPS non-AI, 5 RPS AI | p95 within NFRs |

## 12. CI/CD (GitHub Actions)

| Workflow | Trigger | Steps |
| --- | --- | --- |
| `ci.yml` | Every push and PR | `astral-sh/setup-uv` → `uv sync --locked` (Python 3.15.2) → `ruff check` + `ruff format --check` → `mypy` → `pytest` (unit + API) → integration tests with Postgres service → offline evals → build Docker image |
| `deploy.yml` | Push to `main` after CI passes | Build and push image to GHCR (tagged with git SHA) → run `alembic upgrade head` → deploy to Cloud Run → smoke test `/readyz` → promote the Streamlit client's `deploy` branch |
| `evals.yml` | Weekly, manual, and on changes to `agents/`, prompts or food data | Live Gemini evals → log to MLflow → upload MLflow store as artifact → job summary; fail if thresholds are breached |

**Branching:** `main` is protected (PR + green CI required). Tags `vX.Y.Z` create GitHub Releases. Dependabot keeps uv dependencies and Actions up to date.

**Dockerfile (uv, multi-stage):** builder stage runs `uv sync --locked --no-dev` into `/app/.venv`; runtime stage is a slim Python 3.15 image with a non-root user, copies the venv and `src/`, and runs `uvicorn spotonfit.main:app --host 0.0.0.0 --port 8080 --workers 2`.

### Environments

| Env | API | Database | Purpose |
| --- | --- | --- | --- |
| Local | `uv run fastapi dev` | SQLite (aiosqlite) or Docker Postgres | Development |
| CI | In-process ASGI | aiosqlite + Postgres service | Tests |
| Production | Google Cloud Run (scales to zero) | Neon serverless Postgres | Live app |

Photos are stored in S3-compatible object storage (e.g. Google Cloud Storage), private bucket, with signed URLs.

## 13. Non-functional requirements

| Category | Target |
| --- | --- |
| Latency (p95) | Non-AI ≤ 300 ms · photo analyze ≤ 8 s · text analyze ≤ 5 s · coach first token ≤ 3 s |
| Availability | 99.5% monthly (API) |
| Scalability | Stateless containers; horizontal scale; DB pool sized per instance; AI calls async and non-blocking |
| Durability | Daily Postgres backups (provider) + weekly logical export |
| Security | OWASP ASVS L1 basics; dependency scanning; secrets never in code; authz tests for every endpoint |
| Privacy | EXIF stripped; data export/delete; hashed user IDs in logs/traces |
| Cost | Single user within free tiers (Cloud Run, Neon, LangSmith Developer) + Gemini pay-as-you-go |

## 14. Phase-wise technical delivery

| Phase | Technical deliverables | Exit criteria |
| --- | --- | --- |
| **0: Foundation** (Wk 1) | uv project on 3.15.2; FastAPI app factory + lifespan; settings; async SQLAlchemy + Alembic; users + refresh tokens; JWT auth endpoints; request-ID logging; LangSmith setup; Dockerfile; `ci.yml` + `deploy.yml`; Cloud Run + Neon provisioned; Streamlit client login screen | Register/login/refresh/logout work in prod; push → deployed automatically; failing tests block deploy |
| **1: Core MVP** (Wk 2–4) | Profile/targets; food DB import (INDB + IFCT → `foods`); food graph (LangGraph) + `/meals/analyze` + `/meals`; photo storage; water/steps/weight; `/today`; `daily_summaries`; `/history`; export; Streamlit screens; offline + live food evals in MLflow | A full day logged by photo/text in prod; history correct for day/week/month/year; food kcal MAPE ≤ 25% on eval set |
| **2: Coach** (Wk 5–6) | Deep Agents coach + AsyncPostgresSaver; async tools with injected user ID; SSE streaming; suggestions engine; My Foods; rules (NL → JSON → confirm → engine); coach + safety eval sets | "Can I have tea now?" answered with correct live numbers; safety evals 100%; rule violations change suggestions |
| **3: Progress** (Wk 7–8) | Workout parser + METs; trend + learned TDEE + predictions; weekly review job (scheduled) with accept/reject; measurements | Weekly review generated automatically; learned TDEE matches hand calculation |
| **4: Nudges & mobile** (Wk 9–12) | Scheduler worker (Cloud Run job / Cloud Scheduler) for reminders; FCM push; notification rules engine with caps; Android companion (Kotlin) for steps + sitting → `/activity/samples` | Reminders arrive on time and respect quiet hours; steps sync automatically; ≤ 12 pushes/day |
| **5: Public** (Mo 4+) | Google OIDC; account deletion; EdDSA keys with rotation; per-user quotas; BYOK; Open Food Facts barcode; i18n; OpenTelemetry; load tests; AGPL release | Two-user isolation tests pass; load test meets NFRs; public repo with docs |

## 15. Migration from the v0.1 prototype

The current repo (Streamlit monolith) is reused, not thrown away:

| v0.1 module | Moves to | Change |
| --- | --- | --- |
| `spotonfit/core/*` (targets, foods, ledger, suggest) | `src/spotonfit/core/` | Keep logic and tests; make DB reads go through repositories |
| `spotonfit/agents/food_logger.py` | `src/spotonfit/agents/food_graph.py` | Add preprocess/validate nodes; use `ainvoke` |
| `spotonfit/agents/coach.py` | `src/spotonfit/agents/coach.py` | Async tools; user ID injection; Postgres checkpointer |
| `spotonfit/db.py` | `src/spotonfit/db/` | Async engine; UUID keys; `users` table; Alembic |
| `spotonfit/ui/*` | `clients/streamlit/` | Call the API with JWT instead of the DB directly |
| `requirements*.txt` | `pyproject.toml` + `uv.lock` | uv-managed; Python 3.15.2 |
| `.github/workflows/*` | `ci.yml`, `deploy.yml`, `evals.yml` | uv-based; Docker; Cloud Run |

## 16. Key decisions (ADR summary)

| # | Decision | Reason | Alternative considered |
| --- | --- | --- | --- |
| 1 | FastAPI + async SQLAlchemy | Async I/O for AI and DB calls; typed contracts; OpenAPI | Django (heavier), Flask (sync) |
| 2 | JWT access + rotating opaque refresh tokens | Stateless auth that scales, with revocable sessions | Server sessions (needs sticky state) |
| 3 | Agents in-process (LangGraph library) | Free, simple, scales with the API | LangSmith Deployment (paid Plus plan); revisit at scale |
| 4 | LangSmith for traces, MLflow for evals | Best tracing for LangGraph; free self-hosted experiment tracking | One tool for both |
| 5 | Postgres for data and checkpoints | One durable store; managed backups | Redis for checkpoints |
| 6 | Calories from DB, not LLM | Consistent, testable, auditable | LLM estimates (inconsistent) |
| 7 | Streamlit client first, Android in Phase 4 | Fastest route to daily use; sensors need native Android | React/Flutter now |

## 17. Additional libraries (outside FastAPI/LangChain)

SQLAlchemy, asyncpg, aiosqlite, Alembic, PyJWT, pwdlib (Argon2), python-multipart, httpx, Pillow, psycopg, uvicorn, Streamlit (client), MLflow, pytest/pytest-asyncio, ruff, mypy. Each one is a standard, actively maintained library chosen for a single clear job.
