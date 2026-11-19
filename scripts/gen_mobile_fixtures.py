"""Write real API responses to mobile/test/fixtures/*.json, so the Flutter app's models and
tests are checked against what the API actually returns (AI calls are stubbed, so it is
offline and deterministic in shape).

    PYTHONPATH=src:. uv run python scripts/gen_mobile_fixtures.py

Re-run it whenever an API response shape changes; the Dart contract tests will then fail
if the app no longer understands the new shape.
"""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from spotonfit.agents.food_logger import build_food_graph
from spotonfit.api.deps import get_coach_factory, get_food_graph, get_rule_parser, get_suggester, get_workout_parser
from spotonfit.api.main import create_app
from spotonfit.config import settings
from spotonfit.core.rules import week_start
from spotonfit.db import Database
from tests.conftest import stub_extractor, stub_parser, stub_rule_parser, stub_suggester
from tests.test_phase_d import coach_with

OUT = Path(__file__).resolve().parents[1] / "mobile" / "test" / "fixtures"
PASSWORD = "fixture-pass-1"


def save(name: str, data) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")


def main() -> None:
    # Offline fixture run: seeding weeks of data would otherwise trip the per-minute rate limits.
    settings.limits.general_per_minute = settings.limits.ai_per_minute = 100_000
    settings.limits.ai_per_day = 100_000
    app = create_app(Database(f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/fixtures.db"))
    graph = build_food_graph(stub_extractor)
    app.dependency_overrides[get_food_graph] = lambda: graph
    app.dependency_overrides[get_workout_parser] = lambda: stub_parser
    app.dependency_overrides[get_suggester] = lambda: stub_suggester
    app.dependency_overrides[get_rule_parser] = lambda: stub_rule_parser
    today = dt.datetime.now(settings.tz).date()
    start = week_start(today) - dt.timedelta(days=28)

    with TestClient(app) as c:
        tokens = c.post("/v1/auth/register", json={"email": "fixture@example.com", "password": PASSWORD}).json()
        save("auth_tokens", tokens)
        h = {"Authorization": f"Bearer {tokens['access_token']}"}
        save("me", c.get("/v1/me", headers=h).json())

        profile = {
            "age": 26, "sex": "male", "height_cm": 177.8, "weight_kg": 92.0, "goal": "lose_fat",
            "activity": "light", "body_fat_pct": 24.0, "goal_weight_kg": 85.0, "baseline_steps": 5000,
            "start_date": start.isoformat(),
        }  # fmt: skip
        save("profile", c.put("/v1/profile", headers=h, json=profile).json())
        kcal = c.get("/v1/targets", headers=h).json()["kcal"]
        save("targets", c.get("/v1/targets", headers=h).json())
        low = c.put("/v1/profile", headers=h, json={**profile, "body_fat_pct": 3.0}).json()
        save("profile_with_warning", low)
        c.put("/v1/profile", headers=h, json=profile)

        day = start
        while day < today:  # four weeks of steady logging, flat weight
            item = {
                "name": "home meals",
                "quantity": 1,
                "per_unit": {"kcal": kcal, "protein": 150, "carbs": 200, "fat": 60},
            }
            c.post("/v1/meals", headers=h, json={"slot": "lunch", "items": [item], "eaten_at": f"{day}T13:00:00"})
            c.post("/v1/weights", headers=h, json={"kg": 92.0, "day": day.isoformat()})
            c.put(f"/v1/steps/{day}", headers=h, json={"steps": 6000})
            day += dt.timedelta(days=1)

        draft = c.post("/v1/meals/analyze", headers=h, data={"note": "6 boiled eggs and 3 puris"}).json()
        save("draft", draft)
        meal = c.post(
            "/v1/meals",
            headers=h | {"Idempotency-Key": "fixture-1"},
            json={"slot": draft["meal_slot"], "items": draft["items"], "source": "text", "is_favourite": True},
        ).json()
        save("meal", meal)
        c.post("/v1/water", headers=h, json={"ml": 500})
        c.put(f"/v1/steps/{today}", headers=h, json={"steps": 3900})
        save("workouts", c.post("/v1/workouts", headers=h, json={"text": "15 min cycling, 15 min treadmill"}).json())
        c.put("/v1/my-foods", headers=h, json=[{"name": "boiled egg", "effort": "5_min", "slots": ["breakfast"]}])
        save("my_foods", c.get("/v1/my-foods", headers=h).json())
        edited = {**draft["items"][0], "per_unit": {**draft["items"][0]["per_unit"], "kcal": 78}, "source": "edited"}
        c.post("/v1/meals", headers=h, json={"slot": "snack", "items": [edited]})
        save("food_memory", c.get("/v1/food-memory", headers=h).json())
        rule = c.post("/v1/rules/parse", headers=h, json={"text": "no tea after 4 pm"}).json()
        save("rule_parse", rule)
        c.post("/v1/rules", headers=h, json=rule)
        save("rules", c.get("/v1/rules", headers=h).json())
        c.post("/v1/measurements", headers=h, json={"waist_cm": 98.5, "body_fat_pct": 24.0})
        save("measurements", c.get("/v1/measurements", headers=h).json())

        save("today", c.get("/v1/today", headers=h).json())
        save("meals_today", c.get("/v1/meals", headers=h).json())
        save("recent_meals", c.get("/v1/meals/recent", headers=h).json())
        save("favourite_meals", c.get("/v1/meals/favourites", headers=h).json())
        for period in ("day", "week", "month"):
            save(f"history_{period}", c.get("/v1/history", headers=h, params={"period": period}).json())
        save("suggestions", c.get("/v1/suggestions", headers=h).json())
        save("progress", c.get("/v1/progress", headers=h).json())
        save("weekly_review", c.get("/v1/reviews/weekly", headers=h).json())

        coach_with(c, ["Yes, have tea. You have room today."])
        with c.stream(
            "POST",
            "/v1/coach/messages",
            headers=h | {"Accept": "text/event-stream"},
            json={"message": "Can I have tea now?"},
        ) as r:
            (OUT / "coach_stream.txt").write_text("".join(r.iter_text()))
        save("coach_thread", c.get(f"/v1/coach/threads/{today.isoformat()}", headers=h).json())
        safety = c.post("/v1/coach/messages", headers=h, json={"message": "I fainted at the gym"}).json()
        save("coach_safety", safety)
        save(
            "error_envelope",
            c.post("/v1/auth/login", json={"email": "fixture@example.com", "password": "wrong-pass"}).json(),
        )

        app.dependency_overrides.pop(get_coach_factory, None)

    print(f"wrote {len(list(OUT.iterdir()))} fixtures to {OUT}")


if __name__ == "__main__":
    main()
