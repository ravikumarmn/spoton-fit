"""Personal food memory: the user's own per-unit values, learned from corrections.

When a saved item has source "edited" (the user changed its per-unit values) or
"manual" (the user added it), those per-unit values are remembered under the food's
normalised name. Items whose count alone changed are not remembered: a count is
about this meal, per-unit values are about the food.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.core.nutrition import food_key
from spotonfit.db import FoodMemory

LEARN_FROM = {"edited", "manual"}
NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fibre")


async def load(session: AsyncSession, user_id: uuid.UUID) -> dict[str, dict]:
    """food_key -> remembered values, most-used first (the shape the food graph expects)."""
    rows = await session.scalars(
        select(FoodMemory)
        .where(FoodMemory.user_id == user_id)
        .order_by(FoodMemory.times_used.desc(), FoodMemory.updated_at.desc())
    )
    return {
        r.name_key: {
            "name": r.name,
            "unit": r.unit,
            "grams_per_unit": r.grams_per_unit,
            "per_unit": {k: getattr(r, k) for k in NUTRIENTS},
        }
        for r in rows
    }


async def remember(session: AsyncSession, user_id: uuid.UUID, items: Iterable) -> None:
    """Upsert per-unit values for corrected/added items; count uses of remembered ones.
    `items` are api.schemas.MealItemIn. The caller commits."""
    for item in items:
        if item.source not in LEARN_FROM and item.source != "memory":
            continue
        key = food_key(item.name)
        row = await session.scalar(select(FoodMemory).where(FoodMemory.user_id == user_id, FoodMemory.name_key == key))
        if item.source == "memory":
            if row is not None:
                row.times_used += 1
            continue
        if row is None:
            row = FoodMemory(user_id=user_id, name_key=key, times_used=0)
            session.add(row)
        row.name, row.unit, row.grams_per_unit = item.name, item.unit, item.grams_per_unit
        for k in NUTRIENTS:
            setattr(row, k, getattr(item.per_unit, k))
        row.times_used += 1
