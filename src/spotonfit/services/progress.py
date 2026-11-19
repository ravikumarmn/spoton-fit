"""Progress intelligence (PRD Phase 3): weekly learned maintenance, weekly reviews,
predictions. Pure maths in core/progress.py and core/trend.py.

`generate_weekly(sessionmaker, user_id)` is idempotent: for every completed week
(WEEK_STARTS_ON, default Sunday-Saturday) that has no review yet, it
1. estimates maintenance from the TDEE window ending that week (observed -> blended with
   the previous estimate -> capped weekly change) and stores a TdeeEstimate with a
   plain-language explanation,
2. writes a WeeklyReview: averages, adherence, trend, waist, and at most one proposal.
It runs lazily when the user opens progress/reviews, and from the scheduled job
(`python -m spotonfit.jobs.weekly`).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spotonfit.config import settings
from spotonfit.core.progress import goal_eta, week_stats, weekly_review
from spotonfit.core.rules import week_start
from spotonfit.core.targets import Goal, compute_targets
from spotonfit.core.trend import blend, gradual, observed_tdee, predict_weight, weight_trend
from spotonfit.db import Measurement, ProfileRow, TdeeEstimate, WeeklyReview, WeightLog
from spotonfit.services.ledger import current_targets, daily_frame, get_profile, latest_tdee, local_today

log = logging.getLogger(__name__)


def completed_weeks(start: dt.date, today: dt.date) -> list[dt.date]:
    """Week starts of every fully finished week since the user's start date."""
    first, current = week_start(start), week_start(today)
    weeks = []
    ws = first
    while ws < current:
        weeks.append(ws)
        ws += dt.timedelta(days=7)
    return weeks


async def _trend_series(session: AsyncSession, user_id: uuid.UUID, until: dt.date) -> list[tuple[dt.date, float]]:
    rows = await session.execute(
        select(WeightLog.day, WeightLog.kg).where(WeightLog.user_id == user_id, WeightLog.day <= until)
    )
    return weight_trend([(d, kg) for d, kg in rows], settings.energy.trend_alpha)


def _trend_at(trend: list[tuple[dt.date, float]], day: dt.date) -> float | None:
    """Trend value on or before `day`."""
    value = None
    for d, t in trend:
        if d > day:
            break
        value = t
    return value


async def _waist_change(session: AsyncSession, user_id: uuid.UUID, ws: dt.date, we: dt.date) -> float | None:
    async def latest(until: dt.date):
        return await session.scalar(
            select(Measurement.waist_cm)
            .where(Measurement.user_id == user_id, Measurement.day <= until, Measurement.waist_cm.is_not(None))
            .order_by(Measurement.day.desc())
            .limit(1)
        )

    now, before = await latest(we), await latest(ws - dt.timedelta(days=1))
    return round(now - before, 1) if now is not None and before is not None else None


def _explain(obs: dict, window_end: dt.date, previous: float, new: float, prior_kind: str) -> str:
    cap = settings.energy.tdee_max_weekly_change_kcal
    moved = round(new - previous)
    capped = abs(blend(previous, obs["tdee"]) - previous) > cap
    change = "stays" if moved == 0 else f"moves {previous:,.0f} → {new:,.0f} kcal ({moved:+,})"
    return (
        f"Over the {settings.energy.tdee_window_days} days to {window_end:%d %b} "
        f"you ate {obs['avg_intake']:,.0f} kcal a day on average "
        f"({obs['logged_days']} days logged) and your trend weight changed by {obs['trend_change_kg']:+.2f} kg. "
        f"That points to a maintenance of about {obs['tdee']:,.0f} kcal. Your {prior_kind} estimate {change}"
        + (f"; changes are capped at {cap:,.0f} kcal a week." if capped else ".")
    )


async def _generate_week(session: AsyncSession, user_id: uuid.UUID, row: ProfileRow, ws: dt.date) -> WeeklyReview:
    we = ws + dt.timedelta(days=6)
    profile = await get_profile(session, user_id)
    formula = compute_targets(profile).maintenance

    # 1. learned maintenance for this week
    prev = await latest_tdee(session, user_id, before=ws)
    previous, prior_kind = (prev.tdee, "previous") if prev else (formula, "formula")
    window = await daily_frame(session, we - dt.timedelta(days=settings.energy.tdee_window_days - 1), we, user_id)
    trend = await _trend_series(session, user_id, we)  # all weigh-ins so far: a warmed-up trend
    obs = observed_tdee(window, full_trend=trend)
    learned = prev.tdee if prev else None
    if obs is not None:
        learned = round(gradual(previous, blend(previous, obs["tdee"])))
        session.add(
            TdeeEstimate(
                user_id=user_id,
                week_start=ws,
                tdee=learned,
                observed=round(obs["tdee"]),
                previous=round(previous),
                uncertainty=settings.energy.prediction_band_kcal,
                explanation=_explain(obs, we, previous, learned, prior_kind),
            )
        )

    # 2. the review
    targets = compute_targets(
        profile,
        week_index=max(0, (ws - row.start_date).days // 7),
        learned_tdee=learned,
        kcal_adjustment=row.kcal_adjustment or 0,
        steps_adjustment=row.steps_adjustment or 0,
    )
    stats = week_stats(await daily_frame(session, ws, we, user_id), targets)
    ends = [we - dt.timedelta(days=7 * k) for k in range(settings.reviews.stall_weeks, -1, -1)]
    values = [_trend_at(trend, d) for d in ends]
    changes = [round(b - a, 2) for a, b in zip(values, values[1:], strict=False) if a is not None and b is not None]
    trend_end = values[-1]
    proposal, notes = weekly_review(stats, changes, trend_end, Goal(profile.goal), targets)
    summary = {
        "week_start": ws.isoformat(),
        "week_end": we.isoformat(),
        **dataclasses.asdict(stats),
        "kcal_target": targets.kcal,
        "protein_target_g": targets.protein_g,
        "steps_target": targets.steps,
        "trend_start_kg": values[-2] if len(values) > 1 else None,
        "trend_end_kg": trend_end,
        "trend_change_kg": changes[-1] if changes else None,
        "waist_change_cm": await _waist_change(session, user_id, ws, we),
        "maintenance_kcal": targets.maintenance,
        "maintenance_source": targets.maintenance_source,
        "notes": notes,
    }
    review = WeeklyReview(user_id=user_id, week_start=ws, summary=summary, proposal=proposal)
    session.add(review)
    return review


async def generate_weekly(sessionmaker: async_sessionmaker, user_id: uuid.UUID, today: dt.date | None = None) -> int:
    """Create missing weekly estimates and reviews (oldest first). Returns how many."""
    today = today or local_today()
    async with sessionmaker() as session:
        row = await session.scalar(select(ProfileRow).where(ProfileRow.user_id == user_id))
        if row is None:
            return 0
        done = set(await session.scalars(select(WeeklyReview.week_start).where(WeeklyReview.user_id == user_id)))
        todo = [w for w in completed_weeks(row.start_date, today) if w not in done][-settings.reviews.backfill_weeks :]
        for ws in todo:
            await _generate_week(session, user_id, row, ws)
            await session.flush()  # later weeks build on this week's estimate
        try:
            await session.commit()
        except IntegrityError:  # another request generated the same weeks concurrently
            await session.rollback()
            return 0
    if todo:
        log.info("weekly reviews generated: %d", len(todo))
    return len(todo)


async def decide(session: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID, accept: bool) -> WeeklyReview:
    """Accept (apply the proposal to the profile's adjustments) or reject. Commits."""
    review = await session.scalar(
        select(WeeklyReview).where(WeeklyReview.id == review_id, WeeklyReview.user_id == user_id)
    )
    if review is None:
        raise LookupError("Review not found")
    if review.decision is not None:
        raise ValueError(f"Already {review.decision}")
    if accept and review.proposal:
        row = await session.scalar(select(ProfileRow).where(ProfileRow.user_id == user_id))
        if review.proposal["kind"] == "steps":
            row.steps_adjustment = (row.steps_adjustment or 0) + review.proposal["delta"]
        else:
            row.kcal_adjustment = (row.kcal_adjustment or 0) + review.proposal["delta"]
    review.decision = "accepted" if accept else "rejected"
    review.decided_at = dt.datetime.now(dt.UTC)
    await session.commit()
    return review


async def progress(session: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Weight trend, learned maintenance with its explanation, and prediction ranges."""
    row = await session.scalar(select(ProfileRow).where(ProfileRow.user_id == user_id))
    if row is None:
        return None
    today = local_today()
    profile = await get_profile(session, user_id)
    targets = await current_targets(session, user_id)
    learned = await latest_tdee(session, user_id)
    policy, review_policy = settings.energy, settings.reviews

    trend = await _trend_series(session, user_id, today)
    since = today - dt.timedelta(days=review_policy.progress_days)
    weights = dict(
        (d, kg)
        for d, kg in await session.execute(
            select(WeightLog.day, WeightLog.kg).where(WeightLog.user_id == user_id, WeightLog.day >= since)
        )
    )
    series = [{"day": d.isoformat(), "kg": weights.get(d), "trend_kg": t} for d, t in trend if d >= since]
    trend_now = trend[-1][1] if trend else None
    four_weeks_ago = _trend_at(trend, today - dt.timedelta(days=28))

    window = await daily_frame(session, today - dt.timedelta(days=policy.tdee_window_days), today, user_id)
    logged = int(window["logged"].sum()) if not window.empty else 0
    if learned:
        maint = {
            "active": True,
            "kcal": learned.tdee,
            "week_start": learned.week_start,
            "explanation": learned.explanation,
        }
    else:
        need = max(0, policy.tdee_min_logged_days - logged)
        maint = {
            "active": False,
            "kcal": targets.maintenance,
            "week_start": None,
            "explanation": (
                f"Using the formula ({targets.maintenance:,.0f} kcal) for now. Learned maintenance starts after "
                f"{policy.tdee_min_logged_days} logged days and {policy.tdee_min_weigh_ins} weigh-ins in "
                f"{policy.tdee_window_days} days"
                + (f"; {need} more logged days to go." if need else "; it will appear in your next weekly review.")
            ),
        }
    maint["formula_kcal"] = compute_targets(profile).maintenance
    maint["history"] = [
        {"week_start": e.week_start.isoformat(), "kcal": e.tdee, "observed": e.observed}
        for e in await session.scalars(
            select(TdeeEstimate).where(TdeeEstimate.user_id == user_id).order_by(TdeeEstimate.week_start)
        )
    ]

    prediction = in_weeks = None
    if trend_now is not None:
        days = 7 * review_policy.prediction_weeks
        low, high = predict_weight(trend_now, maint["kcal"], targets.kcal, days, policy)
        in_weeks = {"weeks": review_policy.prediction_weeks, "low_kg": low, "high_kg": high}
        if row.goal_weight_kg:
            prediction = goal_eta(trend_now, row.goal_weight_kg, maint["kcal"], targets.kcal, today, policy) | {
                "goal_kg": row.goal_weight_kg
            }

    meas = list(
        await session.scalars(select(Measurement).where(Measurement.user_id == user_id).order_by(Measurement.day))
    )
    return {
        "weight": {
            "latest_kg": series[-1]["kg"] if series else None,
            "trend_kg": trend_now,
            "trend_change_4w_kg": round(trend_now - four_weeks_ago, 2) if trend_now and four_weeks_ago else None,
            "series": series,
        },
        "maintenance": maint,
        "prediction": prediction,
        "in_weeks": in_weeks,
        "measurements": [
            {"day": m.day.isoformat(), "waist_cm": m.waist_cm, "hip_cm": m.hip_cm, "body_fat_pct": m.body_fat_pct}
            for m in meas
        ],
        "logged_days_in_window": logged,
    }
