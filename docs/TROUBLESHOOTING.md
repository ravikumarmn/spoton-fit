# Troubleshooting and known limits

| Symptom | Fix |
| --- | --- |
| `uv sync` says no Python 3.15.2 download is available | `uv self update` (or `brew upgrade uv`), then `uv sync` |
| `uv sync --locked` reports the lockfile is out of date | Run `uv lock` once (needs the updated uv). v0.5 added `langgraph-checkpoint-postgres`, `langgraph-checkpoint-sqlite` and `psycopg`, which the old uv couldn't lock. Plain `uv sync` updates the lock automatically. |
| 503 `ai_not_configured` | Put `GOOGLE_API_KEY=...` in `.env` at the repo root and restart uvicorn |
| 502 mentioning `thinking_level` | `minimal` isn't valid for `gemini-3.8-flash`; use `low`, `medium` or `high` |
| 401 in Swagger after a while | Access tokens last 15 minutes; click **Authorize** again |
| 409 `profile_required` | `PUT /v1/profile` first |
| Streamlit app says "Can't reach the SpotOn API" | Start the API (terminal 1), or set `SPOTON_API_URL` |
| Streamlit app asks to sign in after a page refresh | Expected for now: the session lives in the browser tab (see Known limits) |
| Startup error about tables/migrations on an old `spotonfit.db` | The schema changed in v0.3 (UUID ids). Delete the old local `spotonfit.db`; it will be recreated |

## Known limits (v0.7.0)

- **Streamlit sign-in lasts for the browser tab.** It doesn't persist across refreshes, because Streamlit can't set secure cookies. The Flutter app keeps you signed in for 30 days.
- **Coach memory** lasts within a day (one thread per day). Across days, the coach uses My Foods, rules, your profile and your **coach notes** (Me › Coach notes, e.g. "vegetarian on Tuesdays").
- **Safety routing** starts from phrase matching, so it can miss phrasings it doesn't know; extend `SAFETY__*_TERMS`. Negated mentions are handled by the model check (see [ARCHITECTURE.md](ARCHITECTURE.md#safety)).
- **The Postgres checkpointer** is wired and configured but has only been tested against SQLite here (no local Postgres).
- **Learned maintenance needs history.** A new user's first estimates lag the real weight trend, because there are no earlier weigh-ins to warm the trend up. The 70/30 blend and the 100 kcal weekly cap keep this from swinging targets.
- **Weekly reviews** use your current profile for past weeks. If you changed your goal mid-way, older reviews are recomputed against the new goal only for weeks not yet reviewed.
- **Meal photos are not stored**; only an optional thumbnail is. Object storage is planned.
- **"Today" uses one timezone** (`SPOTON_TZ`) for all users; per-user timezones are planned.
