"""Phase C backend: idempotent save, edit, favourites, repeat, food memory, export."""

import io
import json
import zipfile

from spotonfit.agents.food_logger import build_prompt
from spotonfit.core.nutrition import food_key
from tests.conftest import bearer, register

DAL = {"name": "dal", "quantity": 1, "unit": "katori", "per_unit": {"kcal": 180, "protein": 9, "carbs": 22, "fat": 6}}


def save(client, auth, items=None, **extra):
    r = client.post("/v1/meals", headers=auth, json={"slot": "lunch", "items": items or [DAL], **extra})
    assert r.status_code in (200, 201), r.text
    return r


def test_idempotency_key_prevents_duplicate_meals(client, auth):
    key = {"Idempotency-Key": "save-123"}
    first = save(client, auth | key)
    again = save(client, auth | key)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
    assert len(client.get("/v1/meals", headers=auth).json()) == 1
    save(client, auth | {"Idempotency-Key": "save-456"})
    assert len(client.get("/v1/meals", headers=auth).json()) == 2


def test_edit_meal(client, auth):
    meal = save(client, auth, note="lunch at office").json()
    url = f"/v1/meals/{meal['id']}"
    r = client.patch(url, headers=auth, json={"items": [{**DAL, "quantity": 2}], "slot": "dinner", "note": None})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["slot"] == "dinner" and m["note"] is None and m["totals"]["kcal"] == 360
    assert client.patch(url, headers=auth, json={"is_favourite": None}).json()["is_favourite"] is False
    other = bearer(register(client, "other@example.com"))
    assert client.patch(url, headers=other, json={"slot": "lunch"}).status_code == 404
    assert client.get(url, headers=other).status_code == 404


def test_favourites_recent_and_one_tap_repeat(client, auth):
    meal = save(client, auth, is_favourite=True).json()
    save(client, auth)
    favs = client.get("/v1/meals/favourites", headers=auth).json()
    assert [f["id"] for f in favs] == [meal["id"]]
    assert len(client.get("/v1/meals/recent", headers=auth).json()) == 2
    rep = client.post(f"/v1/meals/{meal['id']}/repeat", headers=auth)
    assert rep.status_code == 201 and rep.json()["source"] == "repeat" and rep.json()["id"] != meal["id"]
    assert rep.json()["totals"] == meal["totals"]
    assert client.get("/v1/today", headers=auth).json()["eaten"]["kcal"] == 3 * 180
    snack = client.post(f"/v1/meals/{meal['id']}/repeat", headers=auth, json={"slot": "snack"}).json()
    assert snack["slot"] == "snack"


def test_corrections_are_remembered_and_reused(client, auth):
    draft = client.post("/v1/meals/analyze", headers=auth, data={"note": "6 eggs"}).json()
    eggs = draft["items"][0]
    assert eggs["source"] == "ai_estimate" and eggs["per_unit"]["kcal"] == 72

    # changing only the count is about this meal, so nothing is remembered
    save(client, auth, items=[{**eggs, "quantity": 4}])
    assert client.get("/v1/food-memory", headers=auth).json() == []

    # changing per-unit values is about the food, so it is remembered
    mine = {**eggs, "per_unit": {**eggs["per_unit"], "kcal": 78, "protein": 6.5}, "source": "edited"}
    save(client, auth, items=[mine])
    memory = client.get("/v1/food-memory", headers=auth).json()
    assert [(m["name"], m["kcal"]) for m in memory] == [("boiled egg", 78)]

    again = client.post("/v1/meals/analyze", headers=auth, data={"note": "6 eggs"}).json()
    eggs2 = again["items"][0]
    assert eggs2["source"] == "memory" and eggs2["per_unit"]["kcal"] == 78 and eggs2["kcal"] == 6 * 78
    assert again["items"][1]["source"] == "ai_estimate"  # other foods still estimated

    # other users never see my memory
    other = bearer(register(client, "other@example.com"))
    client.put(
        "/v1/profile",
        headers=other,
        json={"age": 30, "sex": "female", "height_cm": 160, "weight_kg": 60, "goal": "maintain"},
    )
    theirs = client.post("/v1/meals/analyze", headers=other, data={"note": "6 eggs"}).json()
    assert theirs["items"][0]["source"] == "ai_estimate"

    assert client.delete(f"/v1/food-memory/{memory[0]['id']}", headers=auth).status_code == 204
    assert client.post("/v1/meals/analyze", headers=auth, data={"note": "eggs"}).json()["items"][0]["source"] == (
        "ai_estimate"
    )


def test_prompt_lists_remembered_foods_and_names_normalise():
    memory = {"boiled egg": {"name": "Boiled egg", "unit": "piece", "grams_per_unit": 50, "per_unit": {}}}
    text = build_prompt({"note": "eggs", "local_time": "08:00", "memory": memory})[1].content[0]["text"]
    assert "Boiled egg" in text
    assert food_key("  Boiled   Eggs ") == "boiled egg" and food_key("glass") == "glass"


def test_export_json_and_csv(client, auth):
    save(client, auth)
    client.post("/v1/water", headers=auth, json={"ml": 250})
    r = client.get("/v1/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = json.loads(r.content)
    assert data["account"][0]["email"] == "me@example.com"
    assert data["meal_items"][0]["food"] == "dal" and data["water"][0]["ml"] == 250 and data["profile"]
    z = client.get("/v1/export", headers=auth, params={"format": "csv"})
    names = set(zipfile.ZipFile(io.BytesIO(z.content)).namelist())
    assert {"meal_items.csv", "water.csv", "weights.csv", "profile.csv", "food_memory.csv"} <= names


def test_food_names_match_regardless_of_word_order_and_punctuation():
    same = ["egg, boiled", "Boiled  Eggs", "boiled egg", "EGGS (boiled)"]
    assert {food_key(n) for n in same} == {"boiled egg"}
    assert food_key("dal-rice") == food_key("Rice & Dal")
    assert food_key("boiled egg") != food_key("fried egg")  # different foods stay different


def test_migration_0005_rekeys_and_merges_food_memory(tmp_path):
    import sqlalchemy as sa
    from alembic import command

    from spotonfit.migrations.runner import alembic_config

    url = f"sqlite+aiosqlite:///{tmp_path / 'm.db'}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0004")
    sync = sa.create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    uid = "0" * 32
    with sync.begin() as c:
        c.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, is_active, created_at, updated_at) "
                "VALUES (:id, 'm@example.com', 'x', 1, '2026-11-01', '2026-11-01')"
            ),
            {"id": uid},
        )
        for i, (name, used) in enumerate([("Boiled Eggs", 5), ("egg, boiled", 2), ("Masala Dosa", 1)]):
            c.execute(
                sa.text(
                    "INSERT INTO food_memory (id, user_id, name_key, name, unit, kcal, protein, carbs, fat, fibre, "
                    "times_used, created_at, updated_at) VALUES (:id, :u, :k, :n, 'piece', 70, 6, 0, 5, 0, :t, "
                    "'2026-11-01', '2026-11-01')"
                ),
                {"id": f"{i:032d}", "u": uid, "k": name.lower(), "n": name, "t": used},
            )
    command.upgrade(cfg, "0005")
    with sync.connect() as c:
        rows = c.execute(sa.text("SELECT name, name_key, times_used FROM food_memory ORDER BY name")).fetchall()
    assert [tuple(r) for r in rows] == [("Boiled Eggs", "boiled egg", 7), ("Masala Dosa", "dosa masala", 1)]


def test_a_correction_saved_under_one_wording_is_used_for_another(client, auth):
    # The user corrected "egg, boiled"; the model later says "boiled egg" (the stub's name).
    draft = client.post("/v1/meals/analyze", headers=auth, data={"note": "eggs"}).json()
    eggs = draft["items"][0]
    mine = {**eggs, "name": "egg, boiled", "per_unit": {**eggs["per_unit"], "kcal": 80}, "source": "edited"}
    save(client, auth, items=[mine])
    again = client.post("/v1/meals/analyze", headers=auth, data={"note": "6 eggs"}).json()["items"][0]
    assert again["source"] == "memory" and again["per_unit"]["kcal"] == 80
