"""Account deletion (PRD L-02, and a Google Play / App Store requirement).

Removes EVERYTHING the user stored: profile, meals and items, water/weight/steps/workouts,
measurements, learned maintenance, weekly reviews, remembered foods, My Foods, rules,
sessions (refresh tokens), the coach's saved conversations, and finally the user row.
Rows are deleted explicitly (SQLite does not enforce ON DELETE CASCADE by default).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.db import (
    FoodMemory,
    FoodRule,
    Meal,
    MealItem,
    Measurement,
    MyFood,
    ProfileRow,
    RefreshToken,
    StepLog,
    TdeeEstimate,
    User,
    WaterLog,
    WeeklyReview,
    WeightLog,
    Workout,
)

log = logging.getLogger(__name__)

# Every table with a user_id column except meals (items hang off meals) and users.
USER_TABLES = (
    WaterLog, WeightLog, StepLog, Workout, Measurement, TdeeEstimate, WeeklyReview,
    FoodMemory, MyFood, FoodRule, RefreshToken, ProfileRow,
)  # fmt: skip


async def delete_user_data(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete all rows owned by the user, then the user. Commits."""
    meal_ids = select(Meal.id).where(Meal.user_id == user_id)
    await session.execute(delete(MealItem).where(MealItem.meal_id.in_(meal_ids)))
    await session.execute(delete(Meal).where(Meal.user_id == user_id))
    for model in USER_TABLES:
        await session.execute(delete(model).where(model.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def delete_chat_threads(checkpointer, user_id: uuid.UUID) -> int:
    """Delete the coach's saved conversations for a user (threads are named u<id>-<thread>).
    Lists every stored thread once; fine for one container, revisit before many users."""
    prefix = f"u{user_id}-"
    threads: set[str] = set()
    async for tup in checkpointer.alist(None):
        thread_id = tup.config["configurable"].get("thread_id", "")
        if thread_id.startswith(prefix):
            threads.add(thread_id)
    for thread_id in threads:
        await checkpointer.adelete_thread(thread_id)
    return len(threads)
