"""Water, steps, weights, workouts, today and history (PRD T-09..T-11, P-01).

"Today" and every day boundary use the configured timezone (SPOTON_TZ). History
returns one row per day from the profile start date, including days with no logs,
aggregated to week/month/year averages over logged days.
"""

import datetime as dt
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select

from spotonfit.agents.activity import MissingDuration, parse_workouts
from spotonfit.agents.models import LLMNotConfigured
from spotonfit.api.deps import Session, get_workout_parser
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import ai_limit
from spotonfit.api.routers.profile import profile_required
from spotonfit.api.schemas import HistoryOut, StepsIn, TargetsOut, TodayOut, WaterIn, WeightIn, WorkoutIn, WorkoutOut
from spotonfit.api.security import CurrentUser
from spotonfit.config import settings
from spotonfit.core.rules import nudges
from spotonfit.core.trend import aggregate, weight_trend
from spotonfit.db import StepLog, WaterLog, WeightLog, Workout
from spotonfit.services.ledger import (
    FutureDay,
    burned_so_far,
    daily_frame,
    day_summary,
    get_profile,
    get_profile_row,
    local_today,
    logged_at,
)
from spotonfit.services.rules import statuses

router = APIRouter(prefix="/v1", tags=["tracking"])
log = logging.getLogger(__name__)


def _when(day: dt.date | None) -> dt.datetime:
    try:
        return logged_at(day)
    except FutureDay as e:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "future_day", str(e)) from e


def _not_future(day: dt.date) -> dt.date:
    _when(day)
    return day


@router.post("/water", status_code=status.HTTP_201_CREATED)
async def add_water(body: WaterIn, user: CurrentUser, session: Session) -> dict:
    session.add(WaterLog(user_id=user.id, at=_when(body.day), ml=body.ml))
    await session.commit()
    return {"ml": body.ml}


@router.post("/weights", status_code=status.HTTP_201_CREATED)
async def log_weight(body: WeightIn, user: CurrentUser, session: Session) -> dict:
    """One weigh-in per day; logging again the same day replaces it."""
    day = _not_future(body.day or local_today())
    row = await session.scalar(select(WeightLog).where(WeightLog.user_id == user.id, WeightLog.day == day))
    if row:
        row.kg = body.kg
    else:
        session.add(WeightLog(user_id=user.id, day=day, kg=body.kg))
    await session.commit()
    return {"day": day, "kg": body.kg}


@router.put("/steps/{day}")
async def set_steps(day: dt.date, body: StepsIn, user: CurrentUser, session: Session) -> dict:
    """Total steps for a day (manual now; synced from Android in Phase 4)."""
    _not_future(day)
    row = await session.scalar(select(StepLog).where(StepLog.user_id == user.id, StepLog.day == day))
    if row:
        row.steps = body.steps
    else:
        session.add(StepLog(user_id=user.id, day=day, steps=body.steps))
    await session.commit()
    return {"day": day, "steps": body.steps}


@router.post("/workouts", response_model=list[WorkoutOut], status_code=status.HTTP_201_CREATED)
async def log_workout(
    body: WorkoutIn,
    user: CurrentUser,
    request: Request,
    session: Session,
    parser: Annotated[object, Depends(get_workout_parser)],
) -> list[dict]:
    """Plain words -> activities with model-estimated MET; kcal = MET x kg x hours."""
    profile = await get_profile(session, user.id)
    if not profile:
        raise profile_required()
    at = _when(body.day)  # before the model call: a future day costs nothing
    ai_limit(request, user.id)
    try:
        rows = await parse_workouts(body.text, profile.weight_kg, parser)
    except MissingDuration as e:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "needs_duration", str(e)) from e
    except LLMNotConfigured as e:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "ai_not_configured", str(e)) from e
    except Exception as e:
        log.exception("workout parsing failed")
        raise api_error(status.HTTP_502_BAD_GATEWAY, "ai_failed", "Could not read that workout, try again") from e
    for r in rows:
        session.add(Workout(user_id=user.id, at=at, raw_text=body.text, **r))
    await session.commit()
    return rows


@router.get("/today", response_model=TodayOut)
async def today(user: CurrentUser, session: Session, day: Annotated[dt.date | None, Query(alias="date")] = None):
    """Eaten, left and burned (estimate) for a day. Exercise is not added back to the budget."""
    profile = await get_profile(session, user.id)
    if not profile:
        raise profile_required()
    d = await day_summary(session, day or local_today(), user.id)
    return TodayOut(
        day=d.day,
        eaten={"kcal": d.kcal, "protein_g": d.protein, "carbs_g": d.carbs, "fat_g": d.fat, "fibre_g": d.fibre},
        left=d.left(),
        targets=TargetsOut(**d.targets.__dict__) if d.targets else None,
        water_ml=d.water_ml,
        steps=d.steps,
        workout_min=d.workout_min,
        burned_kcal_est=burned_so_far(d, profile.weight_kg),
        nudges=nudges([st for _, st in await statuses(session, user.id)]) if day in (None, local_today()) else [],
    )


@router.get("/history", response_model=HistoryOut)
async def history(
    user: CurrentUser,
    session: Session,
    period: Literal["day", "week", "month", "year"] = "day",
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> HistoryOut:
    row = await get_profile_row(session, user.id)
    end = end or local_today()
    start = start or (row.start_date if row else end - dt.timedelta(days=settings.history_default_days))
    if start > end:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "bad_range", "'from' must be on or before 'to'")
    if (end - start).days > settings.history_max_days:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "bad_range",
            f"Range too large (max {settings.history_max_days} days)",
        )
    df = await daily_frame(session, start, end, user.id)
    w = df.dropna(subset=["weight_kg"])
    trend = weight_trend(list(zip(w["day"], w["weight_kg"], strict=True)), settings.energy.trend_alpha)
    view = aggregate(df, period)
    rows = view.astype(object).where(view.notna(), None).to_dict(orient="records")
    for r in rows:  # make dates JSON-friendly
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()[:10]
    return HistoryOut(
        period=period,
        start=start,
        end=end,
        days_logged=int(df["logged"].sum()),
        rows=rows,
        weight_trend=[{"day": d.isoformat(), "trend_kg": t} for d, t in trend],
    )
