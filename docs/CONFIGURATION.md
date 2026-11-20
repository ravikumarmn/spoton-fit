# Configuration

**Location:** the repository root, next to `pyproject.toml`. Start from the template with `cp .env.example .env`. It is git-ignored, and real environment variables override it. Every setting is defined and documented in [`src/spotonfit/config.py`](../src/spotonfit/config.py).

| Variable | Needed? | What it does |
| --- | --- | --- |
| `GOOGLE_API_KEY` | **Yes, for AI features** | Gemini key from [Google AI Studio → API keys](https://aistudio.google.com/apikey) (`GEMINI_API_KEY` also works). Without it, AI endpoints return **503** `ai_not_configured`. |
| `JWT_SECRET` | Recommended (required in prod) | Signs access tokens. If unset in dev, a random key is used and everyone is logged out on restart. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `DATABASE_URL` | No | Default `sqlite+aiosqlite:///./spotonfit.db`. Postgres URLs (Neon/Supabase) are converted to `asyncpg`. |
| `AUTO_MIGRATE` | No | `true` (dev) applies migrations on startup; production sets `false` and migrates in the deploy pipeline. |
| `SPOTON_TZ` | No | Timezone for "today" and day boundaries (default `Asia/Kolkata`). |
| `SPOTON_*_MODEL`, `SPOTON_*_THINKING` | No | Models and reasoning depth (see [ARCHITECTURE.md](ARCHITECTURE.md)). |
| `TARGETS__*`, `ENERGY__*`, `ESTIMATES__*`, `LIMITS__*` | No | Policy overrides: deficit, protein per kg, floors, TDEE window, warning thresholds, rate limits. Examples are in `.env.example`. |
| `CORS_ORIGINS` | No | JSON list of browser origins allowed to call the API. |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | No | Trace every graph node, tool call and model call in LangSmith. |

> **Privacy:** for real meal photos, use a key from a **paid** (billing-enabled) Google Cloud project. Free-tier content may be used to improve Google's products.
