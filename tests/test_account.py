"""Account deletion removes everything, for that user only (PRD L-02)."""

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from sqlalchemy import func, select

from spotonfit import db as models
from tests.conftest import PASSWORD, PROFILE, bearer, register

ITEM = {"name": "dal", "quantity": 1, "per_unit": {"kcal": 180, "protein": 9, "carbs": 22, "fat": 6}}


def seed(client, headers):
    """Touch every kind of data the user can create."""
    client.put("/v1/profile", headers=headers, json=PROFILE)
    client.post("/v1/meals", headers=headers, json={"slot": "lunch", "items": [{**ITEM, "source": "manual"}]})
    client.post("/v1/water", headers=headers, json={"ml": 250})
    client.post("/v1/weights", headers=headers, json={"kg": 91.5})
    client.put("/v1/steps/2026-11-19", headers=headers, json={"steps": 5000})
    client.post("/v1/workouts", headers=headers, json={"text": "15 min cycling"})
    client.post("/v1/measurements", headers=headers, json={"waist_cm": 98})
    client.put("/v1/my-foods", headers=headers, json=[{"name": "curd", "effort": "no_cook"}])
    rule = client.post("/v1/rules/parse", headers=headers, json={"text": "no eggs"}).json()
    client.post("/v1/rules", headers=headers, json=rule)


async def count(db, model):
    async with db.sessionmaker() as s:
        return await s.scalar(select(func.count()).select_from(model))


TABLES = [
    models.User, models.ProfileRow, models.Meal, models.MealItem, models.WaterLog, models.WeightLog, models.StepLog,
    models.Workout, models.Measurement, models.FoodMemory, models.MyFood, models.FoodRule, models.RefreshToken,
]  # fmt: skip


def test_wrong_password_deletes_nothing(client):
    tokens = register(client)
    h = bearer(tokens)
    seed(client, h)
    r = client.request("DELETE", "/v1/account", headers=h, json={"password": "not-my-password"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"
    assert client.get("/v1/profile", headers=h).status_code == 200
    assert len(client.get("/v1/meals", headers=h).json()) == 1


@pytest.mark.anyio
async def test_delete_removes_every_row_and_session_for_that_user_only(client, db):
    mine, other = register(client, "me@example.com"), register(client, "other@example.com")
    for t in (mine, other):
        seed(client, bearer(t))
    # a coach conversation for each user
    saver = client.app.state.checkpointer
    uid = {e: client.get("/v1/me", headers=bearer(t)).json()["id"] for e, t in (("me", mine), ("other", other))}
    for who in ("me", "other"):
        cfg = {"configurable": {"thread_id": f"u{uid[who]}-2026-11-19", "checkpoint_ns": ""}}
        await saver.aput(cfg, empty_checkpoint(), {"source": "input", "step": 0, "parents": {}}, {})

    before = {m.__name__: await count(db, m) for m in TABLES}
    r = client.request("DELETE", "/v1/account", headers=bearer(mine), json={"password": PASSWORD})
    assert r.status_code == 204

    after = {m.__name__: await count(db, m) for m in TABLES}
    assert all(after[k] == before[k] // 2 for k in before), (before, after)  # exactly my half is gone
    # my sessions are dead; the other account is untouched
    assert client.get("/v1/me", headers=bearer(mine)).status_code == 401
    assert client.post("/v1/auth/refresh", json={"refresh_token": mine["refresh_token"]}).status_code == 401
    assert client.post("/v1/auth/login", json={"email": "me@example.com", "password": PASSWORD}).status_code == 401
    assert client.get("/v1/me", headers=bearer(other)).status_code == 200
    assert len(client.get("/v1/meals", headers=bearer(other)).json()) == 1
    threads = {t.config["configurable"]["thread_id"] async for t in saver.alist(None)}
    assert threads == {f"u{uid['other']}-2026-11-19"}  # my conversation is deleted, theirs is not

    # the address can be used again
    assert client.post("/v1/auth/register", json={"email": "me@example.com", "password": PASSWORD}).status_code == 201
