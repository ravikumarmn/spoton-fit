"""Personal food memory: foods whose per-unit values the user corrected or added.
These replace the model's estimate whenever the same food is logged again."""

import uuid

from fastapi import APIRouter, status
from sqlalchemy import delete, select

from spotonfit.api.deps import Session
from spotonfit.api.errors import api_error
from spotonfit.api.schemas import FoodMemoryOut
from spotonfit.api.security import CurrentUser
from spotonfit.db import FoodMemory

router = APIRouter(prefix="/v1/food-memory", tags=["foods"])


@router.get("", response_model=list[FoodMemoryOut])
async def list_food_memory(user: CurrentUser, session: Session) -> list[FoodMemory]:
    rows = await session.scalars(
        select(FoodMemory).where(FoodMemory.user_id == user.id).order_by(FoodMemory.times_used.desc())
    )
    return list(rows)


@router.delete("/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def forget_food(food_id: uuid.UUID, user: CurrentUser, session: Session) -> None:
    """Forget a food: next time the model's estimate is used again."""
    res = await session.execute(delete(FoodMemory).where(FoodMemory.id == food_id, FoodMemory.user_id == user.id))
    if res.rowcount == 0:
        raise api_error(status.HTTP_404_NOT_FOUND, "food_not_found", "Food not found")
    await session.commit()
