"""Progress intelligence (PRD P-02..P-06).

- GET  /v1/progress                       trend weight, learned maintenance + explanation, predictions
- GET  /v1/reviews/weekly                 the latest weekly review (generated if missing)
- GET  /v1/reviews                        all weekly reviews, newest first
- POST /v1/reviews/{id}/decision          accept or reject the proposed change
- POST /v1/measurements · GET /v1/measurements   waist, hip, body fat
Reviews and learned maintenance are generated lazily here and by the scheduled job.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from spotonfit.api.deps import Session
from spotonfit.api.errors import api_error
from spotonfit.api.routers.profile import profile_required
from spotonfit.api.schemas import DecisionIn, MeasurementIn, MeasurementOut, ProgressOut, ReviewOut, WeeklyReviewOut
from spotonfit.api.security import CurrentUser
from spotonfit.core.rules import week_start
from spotonfit.db import Measurement, WeeklyReview
from spotonfit.services.ledger import local_today
from spotonfit.services.progress import decide, generate_weekly, progress

router = APIRouter(prefix="/v1", tags=["progress"])


@router.get("/progress", response_model=ProgressOut)
async def get_progress(user: CurrentUser, request: Request, session: Session) -> dict:
    await generate_weekly(request.app.state.db.sessionmaker, user.id)
    data = await progress(session, user.id)
    if data is None:
        raise profile_required()
    return data


@router.get("/reviews/weekly", response_model=WeeklyReviewOut)
async def weekly(user: CurrentUser, request: Request, session: Session) -> WeeklyReviewOut:
    """The latest completed week's review. Weeks run WEEK_STARTS_ON (default Sunday) to the
    day before, so a new review is ready each week on that day."""
    return await weekly_review_out(request, session, user.id)


async def weekly_review_out(request: Request, session, user_id: uuid.UUID) -> WeeklyReviewOut:
    """Shared by GET /v1/reviews/weekly and GET /v1/today."""
    await generate_weekly(request.app.state.db.sessionmaker, user_id)
    latest = await session.scalar(
        select(WeeklyReview).where(WeeklyReview.user_id == user_id).order_by(WeeklyReview.week_start.desc()).limit(1)
    )
    review = ReviewOut.model_validate(latest) if latest else None
    return WeeklyReviewOut(
        review=review,
        pending_decision=bool(latest and latest.proposal and latest.decision is None),
        next_review_on=week_start(local_today()) + dt.timedelta(days=7),
    )


@router.get("/reviews", response_model=list[ReviewOut])
async def all_reviews(user: CurrentUser, request: Request, session: Session) -> list:
    await generate_weekly(request.app.state.db.sessionmaker, user.id)
    rows = await session.scalars(
        select(WeeklyReview).where(WeeklyReview.user_id == user.id).order_by(WeeklyReview.week_start.desc())
    )
    return list(rows)


@router.post("/reviews/{review_id}/decision", response_model=ReviewOut)
async def decision(review_id: uuid.UUID, body: DecisionIn, user: CurrentUser, session: Session) -> WeeklyReview:
    """Accept applies the proposal to your targets (never below the calorie floor); reject keeps them."""
    try:
        return await decide(session, user.id, review_id, accept=body.decision == "accept")
    except LookupError as e:
        raise api_error(status.HTTP_404_NOT_FOUND, "review_not_found", str(e)) from e
    except ValueError as e:
        raise api_error(status.HTTP_409_CONFLICT, "already_decided", str(e)) from e


@router.post("/measurements", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
async def log_measurement(body: MeasurementIn, user: CurrentUser, session: Session) -> Measurement:
    day = body.day or local_today()
    row = await session.scalar(select(Measurement).where(Measurement.user_id == user.id, Measurement.day == day))
    if row is None:
        row = Measurement(user_id=user.id, day=day)
        session.add(row)
    for field in ("waist_cm", "hip_cm", "body_fat_pct"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)
    await session.commit()
    return row


@router.get("/measurements", response_model=list[MeasurementOut])
async def list_measurements(user: CurrentUser, session: Session) -> list:
    rows = await session.scalars(select(Measurement).where(Measurement.user_id == user.id).order_by(Measurement.day))
    return list(rows)
