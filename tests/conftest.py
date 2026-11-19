"""Shared fixtures. Every model call is replaced by a stub, so tests run offline
and deterministically; the stubs return the same shapes Gemini must return."""

import pytest
from fastapi.testclient import TestClient

from spotonfit.agents.food_logger import build_food_graph
from spotonfit.agents.schemas import (
    FoodItemEstimate,
    MealEstimate,
    MealSuggestions,
    NutrientsPerUnit,
    RuleSpec,
    SuggestionOption,
    WorkoutItem,
    WorkoutLog,
)
from spotonfit.api.deps import get_food_graph, get_rule_parser, get_suggester, get_workout_parser
from spotonfit.api.main import create_app
from spotonfit.db import Database

PASSWORD = "s3cret-pass"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_ai(monkeypatch):
    """Tests never call a real model, even if a GOOGLE_API_KEY is in .env or the environment."""
    from spotonfit.agents import models
    from spotonfit.config import settings

    monkeypatch.setattr(settings, "google_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    models.chat_model.cache_clear()
    yield
    models.chat_model.cache_clear()


def egg(quantity: float = 6) -> FoodItemEstimate:
    return FoodItemEstimate(
        name="boiled egg",
        quantity=quantity,
        unit="piece",
        grams_per_unit=50,
        per_unit=NutrientsPerUnit(kcal=72, protein=6.3, carbs=0.4, fat=4.8),
        oil_level="none",
        confidence=0.9,
    )


def puri() -> FoodItemEstimate:
    return FoodItemEstimate(
        name="puri",
        quantity=3,
        unit="piece",
        grams_per_unit=30,
        per_unit=NutrientsPerUnit(kcal=110, protein=2, carbs=12, fat=6, fibre=0.5),
        oil_level="heavy",
        remark="deep-fried, very oily",
        confidence=0.8,
    )


async def stub_extractor(state):
    return MealEstimate(meal_slot="breakfast", items=[egg(6), puri()])


async def stub_parser(text):
    return WorkoutLog(
        workouts=[
            WorkoutItem(activity="cycling", minutes=15, intensity="moderate", met=7.0),
            WorkoutItem(activity="treadmill walk", minutes=15, intensity="moderate", met=4.5),
        ]
    )


async def stub_suggester(context):
    return MealSuggestions(
        options=[
            SuggestionOption(title="Two boiled eggs", items=[egg(2)], why="High protein, low calories."),
            SuggestionOption(title="Six boiled eggs", items=[egg(6)], why="More protein."),
        ]
    )


RULES = {
    "idli at most 3 days a week": RuleSpec(
        understood=True, kind="max_days_per_week", food="idli", limit=3, summary="Idli on at most 3 days a week."
    ),
    "no tea after 4 pm": RuleSpec(
        understood=True, kind="not_after", food="tea", time="16:00", summary="No tea after 4 PM."
    ),
    "no eggs": RuleSpec(understood=True, kind="avoid", food="egg", summary="No eggs."),
    "be healthy": RuleSpec(understood=False, kind="avoid", food="?", summary="?"),
}


async def stub_rule_parser(text):
    return RULES[text.lower()]


@pytest.fixture
def db(tmp_path):
    return Database(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(db):
    app = create_app(db)
    graph = build_food_graph(stub_extractor)
    app.dependency_overrides[get_food_graph] = lambda: graph
    app.dependency_overrides[get_workout_parser] = lambda: stub_parser
    app.dependency_overrides[get_suggester] = lambda: stub_suggester
    app.dependency_overrides[get_rule_parser] = lambda: stub_rule_parser
    with TestClient(app) as c:
        yield c


def register(client, email: str = "me@example.com") -> dict:
    r = client.post("/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def bearer(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


PROFILE = {
    "age": 26,
    "sex": "male",
    "height_cm": 177.8,
    "weight_kg": 92.2,
    "goal": "lose_fat",
    "activity": "light",
    "body_fat_pct": 24.0,
    "baseline_steps": 5000,
}


@pytest.fixture
def tokens(client) -> dict:
    t = register(client)
    assert client.put("/v1/profile", headers=bearer(t), json=PROFILE).status_code == 200
    return t


@pytest.fixture
def auth(tokens) -> dict:
    return bearer(tokens)
