"""Phase D: My Foods, food rules, two-mode suggestions, coach streaming/history/safety,
and coach memory that survives a restart."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from spotonfit.agents.checkpoint import open_checkpointer
from spotonfit.agents.coach import build_coach, stream_reply, thread_config, thread_history
from spotonfit.agents.schemas import FoodItemEstimate, MealSuggestions, NutrientsPerUnit, SuggestionOption
from spotonfit.api.deps import get_coach_factory, get_suggester
from spotonfit.config import settings
from tests.conftest import egg, stub_suggester


class ToolFake(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def coach_with(client, replies: list[str]):
    """Install a coach whose model returns `replies` in order. Returns the reply iterator:
    if it still has items afterwards, the model was never asked."""
    from langgraph.checkpoint.memory import InMemorySaver

    saver = InMemorySaver()
    agents = {}
    scripted = iter([AIMessage(content=r) for r in replies])

    async def estimate(text):
        return {"items": [], "totals": {"kcal": 0, "protein": 0}, "warnings": []}

    def factory(user_id, sessionmaker):
        if user_id not in agents:
            model = ToolFake(messages=scripted)
            agents[user_id] = build_coach(user_id, sessionmaker, saver, estimate, stub_suggester, model=model)
        return agents[user_id]

    client.app.dependency_overrides[get_coach_factory] = lambda: factory
    return scripted


def sse_events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


# --- My Foods ---------------------------------------------------------------------------


def test_my_foods_replace_and_list(client, auth):
    body = [
        {"name": "Boiled eggs", "effort": "5_min", "slots": ["breakfast"]},
        {"name": "boiled egg", "effort": "no_cook"},  # same food: the last entry wins
        {"name": "Curd", "effort": "buy_nearby", "available": False},
    ]
    r = client.put("/v1/my-foods", headers=auth, json=body)
    assert r.status_code == 200, r.text
    assert sorted((f["name"], f["effort"]) for f in r.json()) == [("Curd", "buy_nearby"), ("boiled egg", "no_cook")]
    assert len(client.get("/v1/my-foods", headers=auth).json()) == 2
    bad = client.put("/v1/my-foods", headers=auth, json=[{"name": "x", "effort": "microwave"}])
    assert bad.status_code == 422


# --- Rules ------------------------------------------------------------------------------


def test_rule_parse_confirm_save_status_delete(client, auth):
    draft = client.post("/v1/rules/parse", headers=auth, json={"text": "idli at most 3 days a week"})
    assert draft.status_code == 200, draft.text
    d = draft.json()
    assert (d["kind"], d["food"], d["limit"], d["summary"]) == (
        "max_days_per_week",
        "idli",
        3,
        "Idli on at most 3 days a week.",
    )
    assert client.get("/v1/rules", headers=auth).json() == []  # parse never saves

    saved = client.post("/v1/rules", headers=auth, json=d)
    assert saved.status_code == 201 and saved.json()["state"] == "ok"
    rules = client.get("/v1/rules", headers=auth).json()
    assert len(rules) == 1 and rules[0]["status"].startswith("Idli: 0 of 3")

    bad = client.post("/v1/rules/parse", headers=auth, json={"text": "be healthy"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "rule_not_understood"
    invalid = client.post("/v1/rules", headers=auth, json={**d, "kind": "not_after", "time": None})
    assert invalid.status_code == 422
    assert client.delete(f"/v1/rules/{rules[0]['id']}", headers=auth).status_code == 204
    assert client.get("/v1/rules", headers=auth).json() == []


def test_broken_rule_shows_a_gentle_nudge_on_today(client, auth):
    rule = client.post("/v1/rules/parse", headers=auth, json={"text": "no eggs"}).json()
    client.post("/v1/rules", headers=auth, json=rule)
    assert client.get("/v1/today", headers=auth).json()["nudges"] == []
    item = {"name": "boiled egg", "quantity": 2, "per_unit": {"kcal": 72, "protein": 6, "carbs": 0, "fat": 5}}
    client.post("/v1/meals", headers=auth, json={"slot": "breakfast", "items": [item]})
    nudges = client.get("/v1/today", headers=auth).json()["nudges"]
    assert len(nudges) == 1 and "back on track" in nudges[0]


# --- Suggestions --------------------------------------------------------------------------


def option(title, *items):
    return SuggestionOption(title=title, items=list(items), why="fits")


def food(name, kcal=100, protein=5):
    per = NutrientsPerUnit(kcal=kcal, protein=protein, carbs=10, fat=3)
    return FoodItemEstimate(
        name=name, quantity=1, unit="piece", grams_per_unit=50, per_unit=per, oil_level="none", confidence=0.9
    )


def test_suggestions_modes_my_foods_and_rules(client, auth):
    seen = []

    async def suggester(context):
        seen.append(context)
        return MealSuggestions(options=[option("Eggs", egg(2)), option("Paneer wrap", food("paneer wrap", 350, 20))])

    client.app.dependency_overrides[get_suggester] = lambda: suggester

    # no My Foods yet: falls back to ideal and says so
    r = client.get("/v1/suggestions", headers=auth).json()
    assert r["mode"] == "ideal" and r["note"] and len(r["options"]) == 2

    client.put("/v1/my-foods", headers=auth, json=[{"name": "boiled egg", "effort": "5_min"}])
    r = client.get("/v1/suggestions", headers=auth).json()
    assert r["mode"] == "my_foods" and [o["title"] for o in r["options"]] == ["Eggs"]  # paneer isn't in My Foods
    assert r["options"][0]["only_my_foods"] is True
    assert "boiled egg (5-minute prep)" in seen[-1]["use ONLY these foods (the user can get them)"]

    ideal = client.get("/v1/suggestions", headers=auth, params={"mode": "ideal"}).json()
    assert ideal["mode"] == "ideal" and len(ideal["options"]) == 2

    # a rule blocks eggs: never suggested, and the model is told
    client.post(
        "/v1/rules", headers=auth, json=client.post("/v1/rules/parse", headers=auth, json={"text": "no eggs"}).json()
    )
    r = client.get("/v1/suggestions", headers=auth, params={"mode": "ideal"}).json()
    assert [o["title"] for o in r["options"]] == ["Paneer wrap"]
    assert seen[-1]["do NOT suggest (the user's own rules)"] == "egg"


# --- Coach ------------------------------------------------------------------------------------


def test_coach_streams_tokens_then_done_and_keeps_history(client, auth):
    coach_with(client, ["Yes, have tea. You have room today."])
    r = client.post(
        "/v1/coach/messages", headers=auth | {"Accept": "text/event-stream"}, json={"message": "Can I have tea now?"}
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = sse_events(r.text)
    tokens = "".join(d["text"] for e, d in events if e == "token")
    assert tokens == "Yes, have tea. You have room today."
    assert events[-1][0] == "done" and events[-1][1]["reply"] == tokens

    thread = events[-1][1]["thread_id"]
    hist = client.get(f"/v1/coach/threads/{thread}", headers=auth).json()["messages"]
    assert hist == [
        {"role": "user", "content": "Can I have tea now?"},  # the clock prefix is hidden
        {"role": "assistant", "content": "Yes, have tea. You have room today."},
    ]


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("I had chest pain on the treadmill, can I have a banana?", "red_flag"),
        ("I felt DIZZY after lunch", "red_flag"),
        ("how do I make myself vomit after dinner", "support"),
    ],
)
def test_safety_route_answers_without_asking_the_model(client, auth, message, kind):
    scripted = coach_with(client, ["This must not be used."])
    r = client.post("/v1/coach/messages", headers=auth, json={"message": message})
    assert r.status_code == 200 and r.json()["safety"] == kind
    expected = settings.safety.red_flag_reply if kind == "red_flag" else settings.safety.support_reply
    assert r.json()["reply"] == expected
    assert next(scripted, None) is not None  # the model was never called
    hist = client.get(f"/v1/coach/threads/{r.json()['thread_id']}", headers=auth).json()["messages"]
    assert hist[-1]["content"] == expected  # stored in the day's thread


def test_safety_route_streams_too(client, auth):
    coach_with(client, ["unused"])
    r = client.post(
        "/v1/coach/messages", headers=auth | {"Accept": "text/event-stream"}, json={"message": "I fainted at the gym"}
    )
    events = sse_events(r.text)
    assert events[-1][0] == "done" and events[-1][1]["safety"] == "red_flag"


@pytest.mark.anyio
async def test_coach_memory_survives_a_restart(tmp_path, monkeypatch):
    """SQLite checkpointer: a conversation is still there after closing and reopening."""
    monkeypatch.setattr(settings, "chat_db_path", str(tmp_path / "chat.db"))
    url = f"sqlite+aiosqlite:///{tmp_path / 'app.db'}"
    config = thread_config("u1", "2026-11-19", "ref")

    async def estimate(text):
        return {}

    async with open_checkpointer(url, "auto") as saver:
        agent = build_coach(
            "u1", None, saver, estimate, stub_suggester, model=ToolFake(messages=iter([AIMessage("Noted.")]))
        )
        events = [e async for e in stream_reply(agent, "I train in the evenings", config)]
        assert events[-1] == {"event": "done", "reply": "Noted."}

    async with open_checkpointer(url, "auto") as saver:  # a fresh process would do the same
        agent = build_coach("u1", None, saver, estimate, stub_suggester, model=ToolFake(messages=iter([])))
        history = await thread_history(agent, config)
    assert [m["content"] for m in history] == ["I train in the evenings", "Noted."]


# --- safety: the small model confirms red-flag matches (backlog: "no chest pain" false positive) ---


def _confirmer(client, answer):
    from spotonfit.api.deps import get_safety_confirmer

    calls = []

    async def confirm(message, term):
        calls.append(term)
        if isinstance(answer, Exception):
            raise answer
        return answer

    client.app.dependency_overrides[get_safety_confirmer] = lambda: confirm
    return calls


def test_negated_symptom_gets_a_normal_coach_reply(client, auth):
    calls = _confirmer(client, False)
    coach_with(client, ["Rest well and keep protein up today."])
    r = client.post("/v1/coach/messages", headers=auth, json={"message": "No chest pain today, just tired"})
    assert r.status_code == 200 and r.json()["safety"] is None
    assert r.json()["reply"] == "Rest well and keep protein up today."
    assert calls == ["chest pain"]


def test_confirmed_symptom_keeps_the_safety_reply(client, auth):
    _confirmer(client, True)
    left = coach_with(client, ["should not be used"])
    r = client.post("/v1/coach/messages", headers=auth, json={"message": "I had chest pain on the treadmill"})
    assert r.json()["safety"] == "red_flag" and r.json()["reply"] == settings.safety.red_flag_reply
    assert next(left, None) is not None  # the coach model was never asked


def test_a_failed_check_keeps_the_safety_reply(client, auth):
    _confirmer(client, RuntimeError("model down"))
    r = client.post("/v1/coach/messages", headers=auth, json={"message": "No chest pain today"})
    assert r.json()["safety"] == "red_flag"


def test_support_routes_are_never_second_guessed(client, auth):
    calls = _confirmer(client, False)
    r = client.post("/v1/coach/messages", headers=auth, json={"message": "I want to starve myself this week"})
    assert r.json()["safety"] == "support" and calls == []


# --- coach notes across days (backlog 3.4) ------------------------------------------


def test_coach_notes_are_saved_and_reach_suggestions(client, auth):
    from spotonfit.api.deps import get_suggester

    assert client.get("/v1/coach/notes", headers=auth).json() == {"notes": ""}
    r = client.put("/v1/coach/notes", headers=auth, json={"notes": "  Vegetarian on Tuesdays. No mushrooms.  "})
    assert r.status_code == 200 and r.json()["notes"] == "Vegetarian on Tuesdays. No mushrooms."
    assert client.get("/v1/coach/notes", headers=auth).json()["notes"] == "Vegetarian on Tuesdays. No mushrooms."

    seen = {}

    async def capture(context):
        seen.update(context)
        return await stub_suggester(context)

    client.app.dependency_overrides[get_suggester] = lambda: capture
    client.get("/v1/suggestions", headers=auth, params={"mode": "ideal"})
    assert seen["the user's standing notes (respect them)"] == "Vegetarian on Tuesdays. No mushrooms."

    assert client.put("/v1/coach/notes", headers=auth, json={"notes": ""}).json() == {"notes": ""}
    assert client.put("/v1/coach/notes", headers=auth, json={"notes": "x" * 1001}).status_code == 422


def test_coach_notes_need_a_profile(client):
    from tests.conftest import bearer, register

    fresh = bearer(register(client, "new@example.com"))
    r = client.put("/v1/coach/notes", headers=fresh, json={"notes": "no dairy"})
    assert r.status_code in (404, 409, 422) and r.json()["error"]["code"] == "profile_required"
