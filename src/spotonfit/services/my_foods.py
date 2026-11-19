"""My Foods (PRD C-03): the foods a user can actually get, with an effort level."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.core.nutrition import food_key
from spotonfit.db import MyFood

EFFORT_LABELS = {"no_cook": "no cooking", "5_min": "5-minute prep", "buy_nearby": "buy nearby", "order": "order in"}


async def list_my_foods(session: AsyncSession, user_id: uuid.UUID, available_only: bool = False) -> list[MyFood]:
    q = select(MyFood).where(MyFood.user_id == user_id)
    if available_only:
        q = q.where(MyFood.available.is_(True))
    return list(await session.scalars(q.order_by(MyFood.name)))


async def replace_my_foods(session: AsyncSession, user_id: uuid.UUID, foods: list) -> list[MyFood]:
    """Replace the whole list (PUT semantics). Duplicate names keep the last entry. Commits."""
    by_key = {food_key(f.name): f for f in foods}
    await session.execute(delete(MyFood).where(MyFood.user_id == user_id))
    for key, f in by_key.items():
        session.add(
            MyFood(
                user_id=user_id,
                name=f.name.strip(),
                name_key=key,
                effort=f.effort,
                slots=f.slots,
                available=f.available,
            )
        )
    await session.commit()
    return await list_my_foods(session, user_id)


def describe(foods: list[MyFood]) -> str:
    return "; ".join(
        f"{f.name} ({EFFORT_LABELS.get(f.effort, f.effort)}" + (f", for {'/'.join(f.slots)})" if f.slots else ")")
        for f in foods
    )
