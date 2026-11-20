# Contributing to SpotOn

Thanks for your interest. Bug reports, fixes, docs and focused features are all welcome.

## Before you start

- For anything bigger than a small fix, open an issue first so we can agree on the approach.
- New features go into the **Flutter app** (`mobile/`) and the **API** (`src/`). The Streamlit app in `frontend/` is
  frozen as a developer and admin tool.
- SpotOn deals with health data. Changes to safety routing, calorie floors or targets need tests, and should not make
  the coach give medical advice.

## Set up

```bash
uv sync --group dev              # backend (Python 3.15.2, pinned in .python-version)
cp .env.example .env             # a Gemini key is only needed for live AI calls; tests stub the model
cd mobile && flutter pub get     # Flutter 3.50
```

## Checks (CI runs all of them)

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run alembic upgrade head && uv run alembic check      # after changing db.py: add a migration
cd mobile && dart format --output=none --set-exit-if-changed lib test && flutter analyze && flutter test
```

If you change an API response, regenerate the mobile fixtures:
`PYTHONPATH=src:. uv run python scripts/gen_mobile_fixtures.py`.

## Pull requests

- Keep them small and focused, with tests for new behaviour.
- Describe what changed and why, and how you checked it. Include a screenshot for UI changes.
- Don't commit secrets, `.env` files, keystores, databases or personal data.
- Don't state numbers (accuracy, speed) you haven't measured.

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
