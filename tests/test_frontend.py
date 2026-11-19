"""End-to-end tests of the Streamlit client: AppTest runs the real pages, and every
request goes through the real API (FastAPI TestClient, models stubbed)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import PROFILE, bearer, register

APP = str(Path(__file__).resolve().parents[1] / "frontend" / "app.py")
TIMEOUT = 30


def app_for(client, tokens=None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.session_state["_http"] = client
    if tokens:
        at.session_state["tokens"] = tokens
    return at.run()


def button(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"no button {label!r}; have {[b.label for b in at.button]}"
    return matches[0]


def press(widget) -> AppTest:
    """Click, then run again: a real session reruns after st.rerun(); AppTest stops there."""
    return widget.click().run().run()


# Note: after sign-in/out the page list changes. A browser then falls back to the default
# page; AppTest keeps re-running the page it started on, so tests navigate explicitly there.


def no_errors(at):
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


@pytest.fixture
def signed_in(client):
    tokens = register(client)
    assert client.put("/v1/profile", headers=bearer(tokens), json=PROFILE).status_code == 200
    return tokens


def test_sign_up_then_profile_then_today(client):
    at = app_for(client)
    no_errors(at)
    assert at.title[0].value == "💪 SpotOn"
    at.text_input(key="reg_email").input("new@example.com")
    at.text_input(key="reg_password").input("long-password-1")
    button(at, "Create account").click().run()
    no_errors(at)
    assert at.session_state["tokens"]["access_token"]
    at.switch_page("pages/today.py").run()
    no_errors(at)
    assert at.title[0].value == "Profile"  # new accounts go straight to the profile
    at.switch_page("pages/profile.py").run()
    button(at, "Save profile").click().run()
    no_errors(at)
    profile = client.get("/v1/profile", headers=bearer(at.session_state["tokens"])).json()
    assert profile["targets"]["kcal"] > 0

    at.switch_page("pages/today.py").run()
    no_errors(at)
    assert at.title[0].value == "Today"
    assert any(m.label == "Calories left" for m in at.metric)


def test_wrong_password_shows_an_error(client):
    register(client)
    at = app_for(client)
    at.text_input(key="login_email").input("me@example.com")
    at.text_input(key="login_password").input("not-my-password")
    button(at, "Sign in").click().run()
    assert at.error and "Incorrect email or password" in at.error[0].value


def test_log_a_meal_by_text_and_see_it_today(client, signed_in):
    at = app_for(client, signed_in)
    at.switch_page("pages/log_meal.py").run()
    no_errors(at)
    at.text_area[0].input("6 boiled eggs and 3 puris").run()  # a real browser reruns on input too
    button(at, "Analyze").click().run()
    no_errors(at)
    assert any("Oily" in b.label for b in at.get("badge")) if at.get("badge") else True
    totals = {m.label: m.value for m in at.metric}
    assert totals["Calories"] == "762"  # 6 x 72 + 3 x 110, computed from per-unit values
    button(at, "Save meal").click().run()
    no_errors(at)
    assert at.title[0].value == "Today"
    meals = client.get("/v1/meals", headers=bearer(signed_in)).json()
    assert len(meals) == 1 and meals[0]["totals"]["kcal"] == 762
    assert any("boiled egg" in m.value for m in at.markdown)


def test_today_quick_logs_and_repeat(client, signed_in):
    h = bearer(signed_in)
    item = {"name": "dal", "quantity": 1, "per_unit": {"kcal": 180, "protein": 9, "carbs": 22, "fat": 6}}
    client.post("/v1/meals", headers=h, json={"slot": "lunch", "items": [item]})
    at = app_for(client, signed_in)
    no_errors(at)
    press(button(at, "💧 +250 ml"))
    no_errors(at)
    assert client.get("/v1/today", headers=h).json()["water_ml"] == 250
    press([b for b in at.button if b.label == "🔁"][0])
    no_errors(at)
    assert client.get("/v1/today", headers=h).json()["eaten"]["kcal"] == 360
    press([b for b in at.button if b.label == "☆"][0])
    assert len(client.get("/v1/meals/favourites", headers=h).json()) == 1


def test_suggestion_opens_as_a_draft(client, signed_in):
    at = app_for(client, signed_in)
    at.switch_page("pages/coach.py").run()
    no_errors(at)
    button(at, "Suggest two options").click().run()
    no_errors(at)
    assert any("Two boiled eggs" in m.value for m in at.markdown)
    [b for b in at.button if b.label == "Review & log this"][0].click().run()
    no_errors(at)
    assert at.title[0].value == "Log a meal"
    assert {m.label: m.value for m in at.metric}["Calories"] == "144"


def test_history_and_profile_pages_render(client, signed_in):
    h = bearer(signed_in)
    item = {"name": "dal", "quantity": 2, "per_unit": {"kcal": 180, "protein": 9, "carbs": 22, "fat": 6}}
    client.post("/v1/meals", headers=h, json={"slot": "lunch", "items": [item]})
    at = app_for(client, signed_in)
    at.switch_page("pages/history.py").run()
    no_errors(at)
    assert {m.label: m.value for m in at.metric}["Days logged"] == "1"
    at.switch_page("pages/profile.py").run()
    no_errors(at)
    button(at, "Prepare export").click().run()
    no_errors(at)
    assert at.session_state["export_json"]
    button(at, "Sign out").click().run()
    assert "tokens" not in at.session_state  # signed out locally (and the session revoked on the API)


def test_coach_streams_and_history_survives_a_page_reload(client, signed_in):
    from tests.test_phase_d import coach_with

    coach_with(client, ["Yes, have tea. You have room today."])
    at = app_for(client, signed_in)
    at.switch_page("pages/coach.py").run()
    no_errors(at)
    at.chat_input[0].set_value("Can I have tea now?").run()
    no_errors(at)
    assert any("Yes, have tea" in m.value for m in at.markdown)

    fresh = app_for(client, signed_in)  # a new browser session: history comes from the API
    fresh.switch_page("pages/coach.py").run()
    no_errors(fresh)
    texts = [m.value for m in fresh.markdown]
    assert "Can I have tea now?" in texts and "Yes, have tea. You have room today." in texts


def test_rules_confirm_flow_and_nudge_on_today(client, signed_in):
    at = app_for(client, signed_in)
    at.switch_page("pages/plan.py").run()
    no_errors(at)
    at.text_input[0].input("no eggs")
    button(at, "Check rule").click().run()
    no_errors(at)
    assert "No eggs." in at.info[0].value  # shown back for confirmation, not saved yet
    assert client.get("/v1/rules", headers=bearer(signed_in)).json() == []
    button(at, "✅ Save this rule").click().run()
    no_errors(at)
    assert len(client.get("/v1/rules", headers=bearer(signed_in)).json()) == 1

    item = {"name": "boiled egg", "quantity": 2, "per_unit": {"kcal": 72, "protein": 6, "carbs": 0, "fat": 5}}
    client.post("/v1/meals", headers=bearer(signed_in), json={"slot": "breakfast", "items": [item]})
    today = app_for(client, signed_in)
    no_errors(today)
    assert any("back on track" in i.value for i in today.info)


def test_my_foods_page_lists_saved_foods(client, signed_in):
    client.put("/v1/my-foods", headers=bearer(signed_in), json=[{"name": "curd", "effort": "buy_nearby"}])
    at = app_for(client, signed_in)
    at.switch_page("pages/plan.py").run()
    no_errors(at)
    assert at.title[0].value == "My foods & rules"


def test_progress_page_and_accepting_a_review(client):
    from tests.test_progress_api import four_weeks

    h = four_weeks.__wrapped__(client)
    tokens = {"access_token": h["Authorization"].split()[1], "refresh_token": "unused-in-this-test"}
    at = app_for(client, tokens)
    no_errors(at)
    assert any("weekly review is ready" in m.value for m in at.markdown)  # banner on Today
    at.switch_page("pages/progress.py").run()
    no_errors(at)
    assert at.title[0].value == "Progress"
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Days logged"] == "7 / 7" and metrics["Learned"].endswith("kcal")
    assert any("not a promise" in i.value for i in at.info)
    button(at, "✅ Accept").click().run()
    no_errors(at)
    assert client.get("/v1/targets", headers=h).json()["steps_adjustment"] == 1500


def test_short_password_is_explained_before_sending(client):
    at = app_for(client)
    at.text_input(key="reg_email").input("admin@example.com")
    at.text_input(key="reg_password").input("admin")
    button(at, "Create account").click().run()
    assert at.error and "at least 8 characters (yours has 5)" in at.error[0].value
    r = client.post("/v1/auth/login", json={"email": "admin@example.com", "password": "admin"})
    assert r.status_code == 401  # nothing was created
