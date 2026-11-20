# Development

## Tests, migrations, evals

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

The eval ground truth in `evals/data/text_meals.jsonl` is **approximate**: it was computed from the old seed table, not weighed. To get a real accuracy number, build a weighed set: [`evals/WEIGHED_MEALS.md`](../evals/WEIGHED_MEALS.md) explains how to weigh, look up IFCT 2017 values and run it.

## Demo data and screenshots

`scripts/seed_demo.py` fills a **local** API with a demo account and four weeks of made-up data (no AI calls), which
is handy for trying the app with realistic history:

```bash
uv run uvicorn spotonfit.api.main:app            # terminal 1
uv run python scripts/seed_demo.py               # terminal 2: prints the demo login
```

The screenshots in `docs/screenshots` were taken from the Flutter debug app running on an Android emulator against a
local API seeded this way (real AI calls for the review, suggestion and coach screens).

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md#code-layout). CI is in `.github/workflows` (`ci.yml`: lint, tests, migrations,
evals, mobile tests; `evals.yml`; `deploy.yml`: optional, see [DEPLOYMENT.md](DEPLOYMENT.md)).
