"""Database reads for the daily ledger, history and targets (services layer).

Layering (Technical PRD section 3): api -> services -> (core, agents, db). The maths
lives in `core/`; this module only queries and assembles.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict, dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.config import settings
from spotonfit.core.targets import Profile, Targets, compute_targets, steps_kcal
from spotonfit.core.trend import HISTORY_COLUMNS
from spotonfit.db import Meal, MealItem, Measurement, ProfileRow, StepLog, TdeeEstimate, WaterLog, WeightLog, Workout


@dataclass
class DaySummary:
    day: dt.date
    kcal: float
    protein: float
    carbs: float
    fat: float
    fibre: float
    water_ml: int
    steps: int
    workout_kcal: float
    workout_min: float
    targets: Targets | None

    def left(self) -> dict[str, float]:
        if not self.targets:
            return {}
        t = self.targets
        return {
            "kcal": round(t.kcal - self.kcal),
            "protein_g": round(t.protein_g - self.protein),
            "carbs_g": round(t.carbs_g - self.carbs),
            "fat_g": round(t.fat_g - self.fat),
            "water_ml": t.water_ml - self.water_ml,
            "steps": t.steps - self.steps,
        }

    def to_dict(self) -> dict:
        d = asdict(self)
        d["left"] = self.left()
        return d


def local_today() -> dt.date:
    return dt.datetime.now(settings.tz).date()


class FutureDay(ValueError):
    """Logging for a day that hasn't happened yet."""


def logged_at(day: dt.date | None) -> dt.datetime:
    """When to record a log for a local `day`: now for today (or no day), else the same clock
    time on that day, so it lands inside that day's boundaries. Raises FutureDay."""
    now = dt.datetime.now(dt.UTC)
    today = local_today()
    if day is None or day == today:
        return now
    if day > today:
        raise FutureDay("You can't log for a day that hasn't happened yet")
    return dt.datetime.combine(day, now.astimezone(settings.tz).timetz()).astimezone(dt.UTC)


def day_bounds(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """[start, end) of a local calendar day as aware datetimes (DB compares in UTC)."""
    start = dt.datetime.combine(day, dt.time.min, tzinfo=settings.tz)
    return start, start + dt.timedelta(days=1)


async def get_profile_row(session: AsyncSession, user_id: uuid.UUID) -> ProfileRow | None:
    return await session.scalar(select(ProfileRow).where(ProfileRow.user_id == user_id))


def to_profile(row: ProfileRow, latest_kg: float | None = None, latest_body_fat: float | None = None) -> Profile:
    return Profile(
        age=row.age,
        sex=row.sex,
        height_cm=row.height_cm,
        weight_kg=latest_kg if latest_kg is not None else row.weight_kg,
        goal=row.goal,
        activity=row.activity,
        body_fat_pct=latest_body_fat if latest_body_fat is not None else row.body_fat_pct,
        goal_weight_kg=row.goal_weight_kg,
        baseline_steps=row.baseline_steps,
    )


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile | None:
    """The profile with the latest logged weight and measured body fat (targets follow
    your weigh-ins and measurements)."""
    row = await get_profile_row(session, user_id)
    if not row:
        return None
    latest = await session.scalar(
        select(WeightLog.kg).where(WeightLog.user_id == user_id).order_by(WeightLog.day.desc()).limit(1)
    )
    body_fat = await session.scalar(
        select(Measurement.body_fat_pct)
        .where(Measurement.user_id == user_id, Measurement.body_fat_pct.is_not(None))
        .order_by(Measurement.day.desc())
        .limit(1)
    )
    return to_profile(row, latest, body_fat)


async def latest_tdee(session: AsyncSession, user_id: uuid.UUID, before: dt.date | None = None) -> TdeeEstimate | None:
    """The newest weekly learned-maintenance estimate (optionally for weeks before a date)."""
    q = select(TdeeEstimate).where(TdeeEstimate.user_id == user_id)
    if before is not None:
        q = q.where(TdeeEstimate.week_start < before)
    return await session.scalar(q.order_by(TdeeEstimate.week_start.desc()).limit(1))


async def current_targets(session: AsyncSession, user_id: uuid.UUID, day: dt.date | None = None) -> Targets | None:
    """Targets for a day: formula, or learned maintenance once a weekly estimate exists
    (services/progress.py writes those), plus accepted weekly-review adjustments."""
    row = await get_profile_row(session, user_id)
    if not row:
        return None
    profile = await get_profile(session, user_id)
    day = day or local_today()
    week = max(0, (day - row.start_date).days // 7)
    learned = await latest_tdee(session, user_id)
    return compute_targets(
        profile,
        week_index=week,
        learned_tdee=learned.tdee if learned else None,
        kcal_adjustment=row.kcal_adjustment or 0,
        steps_adjustment=row.steps_adjustment or 0,
    )


async def day_summary(session: AsyncSession, day: dt.date, user_id: uuid.UUID) -> DaySummary:
    start, end = day_bounds(day)
    items = (
        await session.scalars(
            select(MealItem).join(Meal).where(Meal.user_id == user_id, Meal.eaten_at >= start, Meal.eaten_at < end)
        )
    ).all()
    water = (
        await session.scalars(
            select(WaterLog.ml).where(WaterLog.user_id == user_id, WaterLog.at >= start, WaterLog.at < end)
        )
    ).all()
    workouts = (
        await session.scalars(select(Workout).where(Workout.user_id == user_id, Workout.at >= start, Workout.at < end))
    ).all()
    steps = await session.scalar(select(StepLog.steps).where(StepLog.user_id == user_id, StepLog.day == day)) or 0
    return DaySummary(
        day=day,
        kcal=round(sum(i.kcal for i in items), 1),
        protein=round(sum(i.protein for i in items), 1),
        carbs=round(sum(i.carbs for i in items), 1),
        fat=round(sum(i.fat for i in items), 1),
        fibre=round(sum(i.fibre for i in items), 1),
        water_ml=sum(water),
        steps=steps,
        workout_kcal=round(sum(w.kcal for w in workouts)),
        workout_min=sum(w.minutes for w in workouts),
        targets=await current_targets(session, user_id, day),
    )


def burned_so_far(summary: DaySummary, weight_kg: float, now: dt.datetime | None = None) -> float:
    """Resting burn prorated through the day + steps + workouts (an estimate; never
    added back to the food budget, PRD section 10)."""
    if not summary.targets:
        return 0.0
    now = now or dt.datetime.now(settings.tz)
    fraction = 1.0 if summary.day < now.date() else (now.hour * 60 + now.minute) / (24 * 60)
    return round(summary.targets.bmr * fraction + steps_kcal(summary.steps, weight_kg) + summary.workout_kcal)


def _to_local_day(series: pd.Series) -> pd.Series:
    """UTC timestamps (as stored by db.UTCDateTime) -> the user's local calendar day."""
    return pd.to_datetime(series, utc=True).dt.tz_convert(settings.timezone).dt.date


async def daily_frame(session: AsyncSession, start: dt.date, end: dt.date, user_id: uuid.UUID) -> pd.DataFrame:
    """One row per day from start to end inclusive (days with no logs = 0)."""
    s, _ = day_bounds(start)
    _, e = day_bounds(end)
    out = pd.DataFrame({"day": pd.date_range(start, end, freq="D").date}).set_index("day")

    rows = (
        await session.execute(
            select(Meal.eaten_at, MealItem.kcal, MealItem.protein, MealItem.carbs, MealItem.fat)
            .join(Meal)
            .where(Meal.user_id == user_id, Meal.eaten_at >= s, Meal.eaten_at < e)
        )
    ).all()
    food = pd.DataFrame(rows, columns=["at", "kcal", "protein", "carbs", "fat"])
    if not food.empty:
        food["day"] = _to_local_day(food["at"])
        out = out.join(food.groupby("day")[["kcal", "protein", "carbs", "fat"]].sum())

    water = (
        await session.execute(
            select(WaterLog.at, WaterLog.ml).where(WaterLog.user_id == user_id, WaterLog.at >= s, WaterLog.at < e)
        )
    ).all()
    if water:
        w = pd.DataFrame(water, columns=["at", "ml"])
        w["day"] = _to_local_day(w["at"])
        out = out.join(w.groupby("day")["ml"].sum().rename("water_ml"))

    steps = (
        await session.execute(
            select(StepLog.day, StepLog.steps).where(
                StepLog.user_id == user_id, StepLog.day >= start, StepLog.day <= end
            )
        )
    ).all()
    if steps:
        out = out.join(pd.DataFrame(steps, columns=["day", "steps"]).set_index("day"))

    weights = (
        await session.execute(
            select(WeightLog.day, WeightLog.kg).where(
                WeightLog.user_id == user_id, WeightLog.day >= start, WeightLog.day <= end
            )
        )
    ).all()
    if weights:
        out = out.join(pd.DataFrame(weights, columns=["day", "weight_kg"]).set_index("day"))

    for col in HISTORY_COLUMNS:
        out[col] = out[col].fillna(0) if col in out else 0
    if "weight_kg" not in out:
        out["weight_kg"] = float("nan")
    out["logged"] = out["kcal"] > 0
    return out.reset_index()
