"""Phase E end to end: 4 weeks of logging -> learned maintenance, weekly reviews,
accept/reject, predictions, measurements and the scheduled job."""

import datetime as dt

import pytest

from spotonfit.config import settings
from spotonfit.core.rules import week_start
from tests.conftest import PROFILE, bearer, register


def today() -> dt.date:
    return dt.datetime.now(settings.tz).date()


@pytest.fixture
def four_weeks(client):
    """Started 4 full weeks ago; weight flat at 92 kg (a stall); eats ~on target every day."""
    tokens = register(client, "progress@example.com")
    h = bearer(tokens)
    start = week_start(today()) - dt.timedelta(days=28)
    body = {**PROFILE, "weight_kg": 92.0, "start_date": start.isoformat(), "goal_weight_kg": 85.0}
    assert client.put("/v1/profile", headers=h, json=body).status_code == 200
    kcal = client.get("/v1/targets", headers=h).json()["kcal"]
    d = start
    while d < today():
        item = {
            "name": "home meals",
            "quantity": 1,
            "per_unit": {"kcal": kcal, "protein": 150, "carbs": 200, "fat": 60},
        }
        r = client.post("/v1/meals", headers=h, json={"slot": "lunch", "items": [item], "eaten_at": f"{d}T13:00:00"})
        assert r.status_code == 201, r.text
        client.post("/v1/weights", headers=h, json={"kg": 92.0, "day": d.isoformat()})
        client.put(f"/v1/steps/{d}", headers=h, json={"steps": 6000})
        d += dt.timedelta(days=1)
    return h


def test_weekly_review_is_generated_once_with_a_proposal(client, four_weeks):
    r = client.get("/v1/reviews/weekly", headers=four_weeks)
    assert r.status_code == 200, r.text
    body = r.json()
    review = body["review"]
    assert review["week_start"] == (week_start(today()) - dt.timedelta(days=7)).isoformat()
    s = review["summary"]
    assert s["days_logged"] == 7 and s["trend_change_kg"] == 0.0 and s["avg_steps"] == 6000
    # flat trend for 2 weeks + consistent logging -> one proposal: more steps
    assert review["proposal"]["kind"] == "steps" and review["proposal"]["delta"] == 1500
    assert body["pending_decision"] is True
    assert dt.date.fromisoformat(body["next_review_on"]).weekday() == 6  # Sunday

    all_reviews = client.get("/v1/reviews", headers=four_weeks).json()
    assert len(all_reviews) == 4  # one per completed week, generated automatically
    assert len(client.get("/v1/reviews", headers=four_weeks).json()) == 4  # idempotent


def test_learned_maintenance_activates_and_explains_itself(client, four_weeks):
    p = client.get("/v1/progress", headers=four_weeks).json()
    m = p["maintenance"]
    assert m["active"] is True and m["kcal"] < m["formula_kcal"]  # flat weight on fewer kcal -> lower maintenance
    assert "kcal a day on average" in m["explanation"] and "trend weight changed by +0.00 kg" in m["explanation"]
    steps = [m["history"][i]["kcal"] - m["history"][i - 1]["kcal"] for i in range(1, len(m["history"]))]
    assert all(abs(x) <= settings.energy.tdee_max_weekly_change_kcal for x in steps)  # changes gradually
    t = client.get("/v1/targets", headers=four_weeks).json()
    assert t["maintenance_source"] == "learned" and t["maintenance"] == m["kcal"]
    assert p["weight"]["trend_kg"] == 92.0 and p["in_weeks"]["low_kg"] <= p["in_weeks"]["high_kg"]
    assert p["prediction"]["goal_kg"] == 85.0 and "not a promise" in p["prediction"]["message"]


def test_accepting_a_proposal_changes_targets_once(client, four_weeks):
    review = client.get("/v1/reviews/weekly", headers=four_weeks).json()["review"]
    before = client.get("/v1/targets", headers=four_weeks).json()
    r = client.post(f"/v1/reviews/{review['id']}/decision", headers=four_weeks, json={"decision": "accept"})
    assert r.status_code == 200 and r.json()["decision"] == "accepted"
    after = client.get("/v1/targets", headers=four_weeks).json()
    assert after["steps_adjustment"] == 1500 and after["steps"] == min(before["steps"] + 1500, 10_000)
    again = client.post(f"/v1/reviews/{review['id']}/decision", headers=four_weeks, json={"decision": "reject"})
    assert again.status_code == 409
    assert client.get("/v1/reviews/weekly", headers=four_weeks).json()["pending_decision"] is False


def test_rejecting_keeps_targets(client, four_weeks):
    review = client.get("/v1/reviews/weekly", headers=four_weeks).json()["review"]
    before = client.get("/v1/targets", headers=four_weeks).json()
    client.post(f"/v1/reviews/{review['id']}/decision", headers=four_weeks, json={"decision": "reject"})
    assert client.get("/v1/targets", headers=four_weeks).json() == before


def test_new_user_has_no_review_yet(client, auth):
    body = client.get("/v1/reviews/weekly", headers=auth).json()
    assert body["review"] is None and body["pending_decision"] is False
    p = client.get("/v1/progress", headers=auth).json()
    assert p["maintenance"]["active"] is False and "more logged days" in p["maintenance"]["explanation"]


def test_measurements_and_body_fat_feed_bmr(client, auth):
    before = client.get("/v1/targets", headers=auth).json()["bmr"]  # Katch-McArdle with 24% body fat
    assert client.post("/v1/measurements", headers=auth, json={"waist_cm": 98.5}).status_code == 201
    r = client.post("/v1/measurements", headers=auth, json={"body_fat_pct": 20.0})  # same day: merged
    assert r.json()["waist_cm"] == 98.5 and r.json()["body_fat_pct"] == 20.0
    assert len(client.get("/v1/measurements", headers=auth).json()) == 1
    assert client.get("/v1/targets", headers=auth).json()["bmr"] > before  # more lean mass -> higher BMR
    assert client.post("/v1/measurements", headers=auth, json={}).status_code == 422


@pytest.mark.anyio
async def test_scheduled_job_generates_for_all_users(db, four_weeks):
    from spotonfit.db import WeeklyReview
    from spotonfit.jobs.weekly import run

    result = await run(db)  # the fixture already generated nothing yet: reviews are lazy
    assert result["users"] >= 1 and result["failed"] == 0
    from sqlalchemy import func, select

    async with db.sessionmaker() as s:
        assert await s.scalar(select(func.count()).select_from(WeeklyReview)) == 4
    assert (await run(db))["reviews_created"] == 0  # idempotent
