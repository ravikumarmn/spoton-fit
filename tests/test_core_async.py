import datetime as dt
import json

import pytest

from spotonfit.agents.coach import make_tools
from spotonfit.agents.food_logger import build_food_graph, estimate_text
from spotonfit.agents.schemas import FoodItemEstimate, MealEstimate, NutrientsPerUnit
from spotonfit.config import EnergyPolicy, settings
from spotonfit.core.trend import aggregate, estimate_tdee, learned_tdee_from_frame, predict_weight, weight_trend
from spotonfit.db import Meal, MealItem, ProfileRow, User, WeightLog
from spotonfit.services.ledger import daily_frame
from tests.conftest import egg, stub_extractor, stub_suggester

pytestmark = pytest.mark.anyio


async def test_food_graph_multiplies_counts_and_flags_oily_food():
    out = await build_food_graph(stub_extractor).ainvoke({"note": "6 boiled eggs and 3 puris"})
    eggs, puris = out["items"]
    assert eggs["quantity"] == 6 and eggs["kcal"] == 6 * 72 and eggs["protein"] == pytest.approx(37.8)
    assert eggs["per_unit"]["kcal"] == 72 and eggs["grams"] == 300
    assert out["totals"]["kcal"] == 6 * 72 + 3 * 110
    assert out["oily_items"] == ["puri"] and puris["remark"] == "deep-fried, very oily"
    assert out["warnings"] == []


async def test_food_graph_warns_when_estimate_is_inconsistent_or_unsure():
    async def odd(_state):
        bad = FoodItemEstimate(
            name="mystery sweet",
            quantity=1,
            unit="piece",
            grams_per_unit=40,
            per_unit=NutrientsPerUnit(kcal=400, protein=1, carbs=5, fat=1),  # 400 kcal from ~33 kcal of macros
            oil_level="light",
            confidence=0.3,
        )
        return MealEstimate(meal_slot="snack", items=[bad])

    out = await build_food_graph(odd).ainvoke({"note": "a sweet"})
    assert any("don't add up" in w for w in out["warnings"])
    assert any("not sure" in w for w in out["warnings"])


async def test_no_food_recognised_is_a_warning():
    async def empty(_state):
        return MealEstimate(meal_slot="snack", items=[])

    out = await build_food_graph(empty).ainvoke({"note": "?"})
    assert out["totals"]["kcal"] == 0 and out["warnings"]


async def _seed(db):
    await db.create_all()
    async with db.sessionmaker() as s:
        u = User(email="a@b.co", password_hash="x")
        s.add(u)
        await s.flush()
        today = dt.datetime.now(settings.tz).date()
        s.add(
            ProfileRow(
                user_id=u.id,
                age=26,
                sex="male",
                height_cm=177.8,
                weight_kg=92.2,
                goal="lose_fat",
                activity="sedentary",
                body_fat_pct=24.0,
                baseline_steps=5000,
                start_date=today,
            )
        )
        s.add(WeightLog(user_id=u.id, day=today, kg=92.2))
        for i in range(10):
            t = dt.datetime.combine(today - dt.timedelta(days=i), dt.time(13), tzinfo=settings.tz)
            item = MealItem(
                name="x", quantity=1, unit="plate", kcal=2000, protein=150, carbs=200, fat=60, fibre=30, source="manual"
            )
            s.add(Meal(user_id=u.id, eaten_at=t, slot="lunch", source="text", items=[item]))
        await s.commit()
        return u.id, today


async def test_history_and_coach_tools(db):
    uid, today = await _seed(db)
    async with db.sessionmaker() as s:
        df = await daily_frame(s, today - dt.timedelta(days=13), today, uid)
    assert len(df) == 14 and df["logged"].sum() == 10
    month = aggregate(df, "month")
    assert (month["kcal"] == 2000).all() and month["days_logged"].sum() == 10

    graph = build_food_graph(stub_extractor)

    async def estimate(text):
        return await estimate_text(graph, text)

    tools = {t.__name__: t for t in make_tools(uid, db.sessionmaker, estimate, stub_suggester)}
    assert json.loads(await tools["get_targets"]())["bmr"] == 1884
    est = json.loads(await tools["estimate_food"]("6 eggs and 3 puris"))
    assert est["totals"]["kcal"] == 762
    sim = json.loads(await tools["simulate_add"]("6 eggs and 3 puris"))
    assert sim["adds_kcal"] == 762 and sim["oily_items"] == ["puri"]
    assert json.loads(await tools["get_today"]())["eaten"]["kcal"] == 2000
    sug = json.loads(await tools["suggest_meal"]())
    assert len(sug["options"]) == 2 and sug["options"][0]["totals"]["kcal"] == 144
    assert "rows" in json.loads(await tools["get_history"]("week", 14))


def test_trend_tdee_prediction():
    days = [dt.date(2026, 11, 1) + dt.timedelta(days=i) for i in range(21)]
    trend = weight_trend([(d, 92.0 - 0.07 * i) for i, d in enumerate(days)])
    assert trend[0][1] == 92.0 and trend[-1][1] < 92.0
    assert estimate_tdee(2000, -1.0, 21) == pytest.approx(2000 + 7700 / 21)
    low, high = predict_weight(90.0, 2500, 2000, 28)
    assert low < high < 90.0
    assert egg(1).quantity == 1


def test_learned_tdee_needs_enough_data_and_blends_with_prior():
    import pandas as pd

    days = [dt.date(2026, 11, 1) + dt.timedelta(days=i) for i in range(21)]
    df = pd.DataFrame(
        {"day": days, "kcal": [2000.0] * 21, "logged": [True] * 21, "weight_kg": [92.0 - 0.05 * i for i in range(21)]}
    )
    learned = learned_tdee_from_frame(df, prior=2500)
    assert 2000 < learned < 2500  # pulled from the prior toward the observed value
    assert learned_tdee_from_frame(df.head(5), prior=2500) is None  # not enough logged days
    strict = EnergyPolicy(tdee_min_logged_days=30)
    assert learned_tdee_from_frame(df, prior=2500, policy=strict) is None
