"""Food rules: storage and live status (engine in core/rules.py)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.config import settings
from spotonfit.core.rules import Eaten, Rule, RuleStatus, evaluate, week_start
from spotonfit.db import FoodRule, Meal, MealItem
from spotonfit.services.ledger import day_bounds


def to_rule(row: FoodRule) -> Rule:
    return Rule(
        id=str(row.id),
        kind=row.kind,
        food=row.food,
        limit=row.limit,
        time=dt.time.fromisoformat(row.time) if row.time else None,
    )


async def active_rules(session: AsyncSession, user_id: uuid.UUID) -> list[FoodRule]:
    rows = await session.scalars(
        select(FoodRule).where(FoodRule.user_id == user_id, FoodRule.active.is_(True)).order_by(FoodRule.created_at)
    )
    return list(rows)


async def statuses(
    session: AsyncSession, user_id: uuid.UUID, now: dt.datetime | None = None
) -> list[tuple[FoodRule, RuleStatus]]:
    rows = await active_rules(session, user_id)
    if not rows:
        return []
    now = now or dt.datetime.now(settings.tz)
    since, _ = day_bounds(week_start(now.date()))
    eaten_rows = await session.execute(
        select(Meal.eaten_at, MealItem.name, MealItem.quantity)
        .join(Meal)
        .where(Meal.user_id == user_id, Meal.eaten_at >= since)
    )
    eaten = [Eaten(at.astimezone(settings.tz), name, qty) for at, name, qty in eaten_rows]
    return list(zip(rows, evaluate([to_rule(r) for r in rows], eaten, now), strict=True))
