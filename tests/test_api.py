"""API tests against the ASGI app with stubbed models (no network)."""

import datetime as dt

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from spotonfit.agents.coach import build_coach, with_clock
from spotonfit.api.deps import get_coach_factory
from spotonfit.config import settings
from tests.conftest import PASSWORD, bearer, register, stub_suggester

# --- ops, errors, request ids ------------------------------------------------


def test_health_and_readiness(client):
    h = client.get("/healthz").json()
    assert h["status"] == "ok" and h["models"]["vision"] == settings.vision_model
    assert client.get("/readyz").json()["database"] == "ok"


def test_errors_use_the_envelope_and_echo_request_id(client, auth):
    r = client.get("/v1/meals/not-a-uuid", headers=auth | {"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    r = client.delete("/v1/meals/00000000-0000-0000-0000-000000000000", headers=auth | {"X-Request-ID": "abc123"})
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "meal_not_found", "message": "Meal not found", "request_id": "abc123"}}
    bad = client.post("/v1/water", headers=auth, json={"ml": -5})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    assert bad.json()["error"]["details"]


# --- auth (PRD F-01, F-02) ----------------------------------------------------


def test_register_login_me(client, monkeypatch):
    monkeypatch.setattr(settings.limits, "login_per_minute", 50)  # this test makes many login calls
    t = register(client)
    assert t["token_type"] == "bearer" and t["expires_in"] == settings.access_token_minutes * 60
    assert client.get("/v1/me", headers=bearer(t)).json()["email"] == "me@example.com"
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    # the opaque refresh token is not an access token
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {t['refresh_token']}"}).status_code == 401
    dup = client.post("/v1/auth/register", json={"email": "ME@example.com", "password": "another-pass"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "email_taken"
    ok = client.post("/v1/auth/login", json={"email": "me@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    form = client.post("/v1/auth/token", data={"username": "me@example.com", "password": PASSWORD})
    assert form.status_code == 200
    bad = client.post("/v1/auth/login", json={"email": "me@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"
    nobody = client.post("/v1/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert nobody.status_code == 401


def test_refresh_rotates_and_reuse_revokes_the_family(client):
    t1 = register(client)
    t2 = client.post("/v1/auth/refresh", json={"refresh_token": t1["refresh_token"]}).json()
    assert t2["refresh_token"] != t1["refresh_token"]
    # reusing the old (rotated) token is treated as theft: the whole session dies
    reuse = client.post("/v1/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "invalid_refresh_token"
    assert client.post("/v1/auth/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 401
    assert client.post("/v1/auth/refresh", json={"refresh_token": "x" * 43}).status_code == 401


def test_logout_revokes_the_session(client):
    t = register(client)
    other = client.post("/v1/auth/login", json={"email": "me@example.com", "password": PASSWORD}).json()
    r = client.post("/v1/auth/logout", headers=bearer(t), json={"refresh_token": t["refresh_token"]})
    assert r.status_code == 204
    assert client.post("/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401
    # a separate login (another device) is a different session and keeps working
    assert client.post("/v1/auth/refresh", json={"refresh_token": other["refresh_token"]}).status_code == 200


def test_login_is_rate_limited_per_ip(client):
    register(client)
    codes = [
        client.post("/v1/auth/login", json={"email": "me@example.com", "password": "wrong"}).status_code
        for _ in range(settings.limits.login_per_minute + 1)
    ]
    assert codes[-1] == 429 and 429 not in codes[:-2]


def test_ai_daily_cap(client, auth, monkeypatch):
    monkeypatch.setattr(settings.limits, "ai_per_day", 2)
    codes = [client.post("/v1/meals/analyze", headers=auth, data={"note": "eggs"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# --- profile and targets --------------------------------------------------------


def test_profile_targets(client, auth):
    p = client.get("/v1/profile", headers=auth).json()
    assert p["targets"]["bmr"] == 1884 and 2000 <= p["targets"]["kcal"] <= 2100
    assert client.get("/v1/targets", headers=auth).json() == p["targets"]


def test_profile_weight_edit_applies_today(client, auth):
    body = {"age": 26, "sex": "male", "height_cm": 177.8, "weight_kg": 80.0, "goal": "lose_fat", "activity": "light"}
    assert client.put("/v1/profile", headers=auth, json=body).status_code == 200
    hist = client.get("/v1/history", headers=auth, params={"period": "day"}).json()
    assert hist["rows"][-1]["weight_kg"] == 80.0


def test_endpoints_need_a_profile(client):
    t = register(client, "new@example.com")
    r = client.get("/v1/today", headers=bearer(t))
    assert r.status_code == 409 and r.json()["error"]["code"] == "profile_required"


# --- meals ------------------------------------------------------------------------


def test_analyze_then_save_meal_updates_today(client, auth):
    draft = client.post("/v1/meals/analyze", headers=auth, data={"note": "6 boiled eggs and 3 puris"})
    assert draft.status_code == 200, draft.text
    d = draft.json()
    assert [(i["name"], i["quantity"]) for i in d["items"]] == [("boiled egg", 6), ("puri", 3)]
    assert d["totals"]["kcal"] == 762 and d["oily_items"] == ["puri"]
    assert d["items"][1]["remark"] == "deep-fried, very oily"

    saved = client.post("/v1/meals", headers=auth, json={"slot": d["meal_slot"], "source": "text", "items": d["items"]})
    assert saved.status_code == 201, saved.text
    today = client.get("/v1/today", headers=auth).json()
    assert today["eaten"]["kcal"] == 762
    assert today["left"]["protein_g"] == today["targets"]["protein_g"] - round(today["eaten"]["protein_g"])
    assert len(client.get("/v1/meals", headers=auth).json()) == 1


def test_editing_the_count_rescales_on_the_server(client, auth):
    """6 eggs -> 4 eggs: totals come from quantity x per_unit; client totals are ignored."""
    d = client.post("/v1/meals/analyze", headers=auth, data={"note": "6 eggs"}).json()
    eggs = {**d["items"][0], "quantity": 4, "kcal": 1, "protein": 999, "source": "edited"}
    saved = client.post("/v1/meals", headers=auth, json={"slot": "breakfast", "items": [eggs]}).json()
    item = saved["items"][0]
    assert item["kcal"] == 288 and item["protein"] == 25.2 and item["grams"] == 200
    assert item["per_unit"]["kcal"] == 72
    manual = {"name": "home laddoo", "quantity": 2, "per_unit": {"kcal": 150, "protein": 3, "carbs": 18, "fat": 7}}
    r = client.post("/v1/meals", headers=auth, json={"slot": "snack", "items": [{**manual, "source": "manual"}]})
    assert r.status_code == 201 and r.json()["items"][0]["kcal"] == 300


def test_evening_meal_stays_on_its_day_in_history(client, auth):
    """A 21:00 local meal counts on the same day in Today and History (UTC storage)."""
    day = dt.datetime.now(settings.tz).date() - dt.timedelta(days=1)
    item = {
        "name": "dal",
        "quantity": 1,
        "unit": "katori",
        "per_unit": {"kcal": 180, "protein": 9, "carbs": 22, "fat": 6},
    }
    r = client.post(
        "/v1/meals", headers=auth, json={"slot": "dinner", "items": [item], "eaten_at": f"{day.isoformat()}T21:00:00"}
    )
    assert r.status_code == 201, r.text
    today_view = client.get("/v1/today", headers=auth, params={"date": day.isoformat()}).json()
    hist = client.get(
        "/v1/history", headers=auth, params={"period": "day", "from": day.isoformat(), "to": day.isoformat()}
    ).json()
    assert today_view["eaten"]["kcal"] == 180 and hist["rows"][0]["kcal"] == 180
    assert len(client.get("/v1/meals", headers=auth, params={"date": day.isoformat()}).json()) == 1


def test_photo_upload(client, auth):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1600, 1200), "white").save(buf, format="JPEG")
    r = client.post("/v1/meals/analyze", headers=auth, files={"image": ("meal.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200 and r.json()["items"]


def test_upload_type_is_sniffed_and_bad_images_are_rejected(client, auth):
    heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00" + b"\x00" * 64
    r = client.post("/v1/meals/analyze", headers=auth, files={"image": ("a.heic", heic, "image/heic")})
    assert r.status_code == 200, r.text  # Pillow can't decode HEIC; it is sent to Gemini as-is
    broken = b"\xff\xd8\xff\xe0" + b"garbage" * 10
    r = client.post("/v1/meals/analyze", headers=auth, files={"image": ("a.jpg", broken, "image/jpeg")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unreadable_image"
    r = client.post("/v1/meals/analyze", headers=auth, files={"image": ("a.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 415
    assert client.post("/v1/meals/analyze", headers=auth).status_code == 422


def test_users_cannot_see_each_others_data(client, auth):
    item = {"name": "dal", "quantity": 1, "per_unit": {"kcal": 180, "protein": 9, "carbs": 22, "fat": 6}}
    client.post("/v1/meals", headers=auth, json={"slot": "lunch", "items": [item]})
    other = bearer(register(client, "other@example.com"))
    assert client.get("/v1/meals", headers=other).json() == []
    meal_id = client.get("/v1/meals", headers=auth).json()[0]["id"]
    assert client.delete(f"/v1/meals/{meal_id}", headers=other).status_code == 404
    assert client.delete(f"/v1/meals/{meal_id}", headers=auth).status_code == 204


# --- tracking ----------------------------------------------------------------------


def test_water_weight_steps_workouts_history(client, auth):
    today = dt.datetime.now(settings.tz).date().isoformat()
    assert client.post("/v1/water", headers=auth, json={"ml": 500}).status_code == 201
    assert client.post("/v1/weights", headers=auth, json={"kg": 91.8}).status_code == 201
    assert client.put(f"/v1/steps/{today}", headers=auth, json={"steps": 6200}).status_code == 200
    w = client.post("/v1/workouts", headers=auth, json={"text": "15 min cycling, 15 min treadmill"})
    assert w.status_code == 201, w.text
    # kcal = model-estimated MET x latest weight (91.8 kg) x hours
    assert [(r["met"], r["kcal"]) for r in w.json()] == [(7.0, 161), (4.5, 103)]
    t = client.get("/v1/today", headers=auth).json()
    assert t["water_ml"] == 500 and t["steps"] == 6200 and t["workout_min"] == 30
    for period in ["day", "week", "month", "year"]:
        hist = client.get("/v1/history", headers=auth, params={"period": period})
        assert hist.status_code == 200, hist.text
    assert hist.json()["weight_trend"][-1]["trend_kg"] == 91.8


def test_workout_without_duration_asks_instead_of_guessing(client, auth):
    from spotonfit.agents.schemas import WorkoutItem, WorkoutLog
    from spotonfit.api.deps import get_workout_parser

    async def vague(_text):
        return WorkoutLog(workouts=[WorkoutItem(activity="gym", minutes=None, intensity="moderate", met=5)])

    client.app.dependency_overrides[get_workout_parser] = lambda: vague
    r = client.post("/v1/workouts", headers=auth, json={"text": "went to the gym"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "needs_duration"


# --- suggestions and coach ---------------------------------------------------------


def test_suggestions(client, auth):
    r = client.get("/v1/suggestions", headers=auth)
    assert r.status_code == 200, r.text
    opts = r.json()["options"]
    assert [o["totals"]["kcal"] for o in opts] == [144, 432] and all(o["fits"] for o in opts)


class ToolFake(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_coach_messages(client, auth):
    from langgraph.checkpoint.memory import InMemorySaver

    saver = InMemorySaver()

    async def estimate(text):
        return {"items": [], "totals": {"kcal": 0, "protein": 0}, "warnings": []}

    def factory(user_id, sessionmaker):
        model = ToolFake(messages=iter([AIMessage(content="Yes, have tea. You still have room today.")]))
        return build_coach(user_id, sessionmaker, saver, estimate, stub_suggester, model=model)

    client.app.dependency_overrides[get_coach_factory] = lambda: factory
    r = client.post("/v1/coach/messages", headers=auth, json={"message": "Can I have tea now?"})
    assert r.status_code == 200, r.text
    assert "tea" in r.json()["reply"].lower()


def test_coach_messages_carry_the_current_time():
    now = dt.datetime(2026, 11, 19, 16, 5, tzinfo=settings.tz)
    assert with_clock("Can I have tea now?", now) == "[Thursday 19 Nov 2026, 16:05] Can I have tea now?"


# --- model configuration ------------------------------------------------------------


def test_gemini_models_use_thinking_level_not_temperature(monkeypatch):
    from spotonfit.agents import models

    monkeypatch.setattr(settings, "google_api_key", SecretStr("test-key-not-real"))
    models.chat_model.cache_clear()
    try:
        m = models.vision_model()
        assert m.model.endswith("gemini-3.8-flash")
        assert m.thinking_level == "low"
        assert m.temperature in (None, 1.0)  # never overridden
        assert m.max_retries == 2 and m.timeout == 20
        assert models.parser_model().thinking_level == "minimal"
    finally:
        models.chat_model.cache_clear()


def test_ai_endpoints_say_when_no_key_is_configured(client, auth, monkeypatch):
    from spotonfit.agents import models
    from spotonfit.agents.food_logger import build_food_graph
    from spotonfit.api.deps import get_food_graph

    monkeypatch.setattr(settings, "google_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    models.chat_model.cache_clear()
    real_graph = build_food_graph()  # the Gemini-backed graph, not the test stub
    client.app.dependency_overrides[get_food_graph] = lambda: real_graph
    r = client.post("/v1/meals/analyze", headers=auth, data={"note": "2 eggs"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_not_configured"
    assert "GOOGLE_API_KEY" in r.json()["error"]["message"]


def test_validation_message_says_what_is_wrong(client):
    r = client.post("/v1/auth/register", json={"email": "a@example.com", "password": "admin"})
    assert r.status_code == 422
    assert r.json()["error"]["message"] == "password: String should have at least 8 characters"


def test_profile_warns_about_implausible_body_fat(client, auth):
    body = {
        **{k: v for k, v in client.get("/v1/profile", headers=auth).json().items() if k not in ("targets", "warnings")}
    }
    ok = client.put("/v1/profile", headers=auth, json={**body, "body_fat_pct": 24.0}).json()
    assert ok["warnings"] == []
    low = client.put("/v1/profile", headers=auth, json={**body, "body_fat_pct": 3.0}).json()
    assert len(low["warnings"]) == 1 and "unusually low" in low["warnings"][0]
    assert low["targets"]["bmr"] > ok["targets"]["bmr"]  # why it matters: 3% inflates BMR
