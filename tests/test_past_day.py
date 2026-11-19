"""Logging for an earlier day (bug: meals logged while viewing yesterday landed on today)."""

import datetime as dt

from spotonfit.config import settings
from spotonfit.services.ledger import day_bounds, logged_at

ITEM = {"name": "rice", "quantity": 1, "per_unit": {"kcal": 300, "protein": 6, "carbs": 65, "fat": 1}}


def _days():
    today = dt.datetime.now(settings.tz).date()
    return today, today - dt.timedelta(days=1)


def test_logged_at_lands_inside_the_chosen_day():
    today, yesterday = _days()
    for day in (yesterday, today - dt.timedelta(days=30)):
        start, end = day_bounds(day)
        assert start <= logged_at(day) < end
    start, end = day_bounds(today)
    assert start <= logged_at(None) < end


def test_meal_water_workout_weight_for_yesterday_count_on_yesterday(client, auth):
    today, yesterday = _days()
    # What the app sends: yesterday's date at the current clock time, as UTC.
    eaten = logged_at(yesterday).isoformat()
    r = client.post("/v1/meals", headers=auth, json={"slot": "lunch", "items": [ITEM], "eaten_at": eaten})
    assert r.status_code == 201, r.text
    assert client.post("/v1/water", headers=auth, json={"ml": 400, "day": yesterday.isoformat()}).status_code == 201
    w = client.post("/v1/workouts", headers=auth, json={"text": "15 min cycling", "day": yesterday.isoformat()})
    assert w.status_code == 201, w.text
    assert client.post("/v1/weights", headers=auth, json={"kg": 91.0, "day": yesterday.isoformat()}).status_code == 201

    y = client.get("/v1/today", headers=auth, params={"date": yesterday.isoformat()}).json()
    t = client.get("/v1/today", headers=auth).json()
    assert y["eaten"]["kcal"] == 300 and y["water_ml"] == 400 and y["workout_min"] > 0
    assert t["eaten"]["kcal"] == 0 and t["water_ml"] == 0 and t["workout_min"] == 0
    meals_y = client.get("/v1/meals", headers=auth, params={"date": yesterday.isoformat()}).json()
    assert [m["slot"] for m in meals_y] == ["lunch"]
    assert client.get("/v1/meals", headers=auth).json() == []


def test_without_a_day_everything_still_goes_to_today(client, auth):
    assert client.post("/v1/water", headers=auth, json={"ml": 250}).status_code == 201
    assert client.post("/v1/meals", headers=auth, json={"slot": "snack", "items": [ITEM]}).status_code == 201
    t = client.get("/v1/today", headers=auth).json()
    assert t["water_ml"] == 250 and t["eaten"]["kcal"] == 300


def test_future_days_are_refused(client, auth):
    today, _ = _days()
    tomorrow = (today + dt.timedelta(days=1)).isoformat()
    later = (dt.datetime.now(dt.UTC) + dt.timedelta(days=1)).isoformat()
    for r in (
        client.post("/v1/water", headers=auth, json={"ml": 250, "day": tomorrow}),
        client.post("/v1/weights", headers=auth, json={"kg": 90, "day": tomorrow}),
        client.put(f"/v1/steps/{tomorrow}", headers=auth, json={"steps": 1000}),
        client.post("/v1/workouts", headers=auth, json={"text": "15 min cycling", "day": tomorrow}),
        client.post("/v1/meals", headers=auth, json={"slot": "lunch", "items": [ITEM], "eaten_at": later}),
    ):
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "future_day"
