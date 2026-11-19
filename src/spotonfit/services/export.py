"""Data export (PRD T-12, privacy: "export any time"). Everything the user logged,
as one JSON document or a ZIP of CSV files (one per table)."""

from __future__ import annotations

import csv
import datetime as dt
import io
import uuid
import zipfile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.config import settings
from spotonfit.db import FoodMemory, Meal, ProfileRow, StepLog, WaterLog, WeightLog, Workout


def _local(t: dt.datetime) -> str:
    return t.astimezone(settings.tz).isoformat(timespec="seconds")


async def collect(session: AsyncSession, user_id: uuid.UUID, email: str) -> dict[str, list[dict]]:
    """All of a user's data as tables (lists of flat rows)."""

    async def rows(model, order):
        return list(await session.scalars(select(model).where(model.user_id == user_id).order_by(order)))

    profile = await session.scalar(select(ProfileRow).where(ProfileRow.user_id == user_id))
    meals = await rows(Meal, Meal.eaten_at)
    return {
        "account": [{"email": email, "exported_at": _local(dt.datetime.now(dt.UTC)), "timezone": settings.timezone}],
        "profile": [
            {
                c: getattr(profile, c)
                for c in (
                    "age",
                    "sex",
                    "height_cm",
                    "weight_kg",
                    "goal",
                    "activity",
                    "body_fat_pct",
                    "goal_weight_kg",
                    "baseline_steps",
                    "start_date",
                )
            }  # fmt: skip
        ]
        if profile
        else [],
        "meal_items": [
            {
                "meal_id": str(m.id),
                "eaten_at": _local(m.eaten_at),
                "slot": m.slot,
                "meal_source": m.source,
                "favourite": m.is_favourite,
                "note": m.note,
                "food": i.name,
                "quantity": i.quantity,
                "unit": i.unit,
                "grams": i.grams,
                "kcal": i.kcal,
                "protein_g": i.protein,
                "carbs_g": i.carbs,
                "fat_g": i.fat,
                "fibre_g": i.fibre,
                "oil_level": i.oil_level,
                "item_source": i.source,
            }
            for m in meals
            for i in m.items
        ],
        "water": [{"at": _local(w.at), "ml": w.ml} for w in await rows(WaterLog, WaterLog.at)],
        "weights": [{"day": w.day, "kg": w.kg} for w in await rows(WeightLog, WeightLog.day)],
        "steps": [{"day": s.day, "steps": s.steps} for s in await rows(StepLog, StepLog.day)],
        "workouts": [
            {"at": _local(w.at), "activity": w.activity, "minutes": w.minutes, "met": w.met, "kcal": w.kcal}
            for w in await rows(Workout, Workout.at)
        ],
        "food_memory": [
            {
                "food": f.name,
                "unit": f.unit,
                "grams_per_unit": f.grams_per_unit,
                "kcal": f.kcal,
                "protein_g": f.protein,
                "carbs_g": f.carbs,
                "fat_g": f.fat,
                "fibre_g": f.fibre,
                "times_used": f.times_used,
            }  # fmt: skip
            for f in await rows(FoodMemory, FoodMemory.name)
        ],
    }


def to_zip(tables: dict[str, list[dict]]) -> bytes:
    """One CSV per table, zipped. Empty tables are included with no rows."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, rows in tables.items():
            out = io.StringIO()
            if rows:
                writer = csv.DictWriter(out, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            zf.writestr(f"{name}.csv", out.getvalue())
    return buf.getvalue()
