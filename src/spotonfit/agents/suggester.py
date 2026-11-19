"""Meal suggestions (PRD C-02): the model proposes realistic meals for what is left
today; code totals each option and checks whether it fits the calorie budget.

Replaces the old fixed food list and hand-tuned scoring weights.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from spotonfit.agents.food_logger import item_row
from spotonfit.agents.schemas import MealSuggestions
from spotonfit.config import settings
from spotonfit.core.nutrition import Nutrients, food_key, meal_totals

SYSTEM = """You suggest practical meals for a calorie-tracking app used mainly in India.
The user may be a busy professional, student or bachelor with limited cooking.
If the situation lists foods to use ONLY, build every option from those foods only.
Never include foods listed under "do NOT suggest".
Give exactly two different options that:
- fit within the calories left (never exceed them),
- close as much of the protein gap as possible,
- suit the time of day and the meal slot,
- use common, easy-to-get foods (no-cook, 5-minute, buy nearby or order in).
For each food, estimate quantity, grams per unit and the nutrients of ONE unit as served
(oil included). Do not pre-multiply by quantity. Keep supplements optional, never required."""

Suggester = Callable[[dict], Awaitable[MealSuggestions]]


def gemini_suggester(model=None) -> Suggester:
    async def _suggest(context: dict) -> MealSuggestions:
        from spotonfit.agents.models import parser_model

        llm = (model or parser_model()).with_structured_output(MealSuggestions)
        lines = "\n".join(f"- {k}: {v}" for k, v in context.items())
        return await llm.ainvoke([SystemMessage(SYSTEM), HumanMessage(f"Situation:\n{lines}")])

    return _suggest


def finalize(suggestions: MealSuggestions, kcal_left: float, memory: dict | None = None) -> list[dict]:
    """Add code-computed totals and a `fits` flag to each option. The user's remembered
    per-unit values (food memory) replace the model's estimates where names match."""
    slack = 1 + settings.estimates.suggestion_kcal_slack
    memory = memory or {}
    out = []
    for opt in suggestions.options:
        items = [item_row(it, memory.get(food_key(it.name))) for it in opt.items]
        totals = meal_totals([Nutrients(*(i[k] for k in ("kcal", "protein", "carbs", "fat", "fibre"))) for i in items])
        out.append(
            {
                "title": opt.title,
                "why": opt.why,
                "items": items,
                "totals": totals.as_dict(),
                "fits": totals.kcal <= max(kcal_left, 0) * slack,
            }
        )
    return out
