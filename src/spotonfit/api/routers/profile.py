"""Profile (PRD T-01) and the targets derived from it (T-02)."""

import dataclasses

from fastapi import APIRouter, status
from sqlalchemy import select

from spotonfit.api.deps import Session
from spotonfit.api.errors import api_error
from spotonfit.api.schemas import ProfileIn, ProfileOut, TargetsOut
from spotonfit.api.security import CurrentUser
from spotonfit.config import settings
from spotonfit.db import ProfileRow, WeightLog
from spotonfit.services.ledger import current_targets, get_profile_row, local_today

router = APIRouter(prefix="/v1", tags=["profile"])

PROFILE_FIELDS = set(ProfileIn.model_fields) - {"start_date"}


def profile_required():
    return api_error(status.HTTP_409_CONFLICT, "profile_required", "Set up your profile first (PUT /v1/profile)")


def profile_warnings(row: ProfileRow) -> list[str]:
    """Plausibility checks on inputs that move the targets a lot."""
    out = []
    low = settings.targets.unusual_body_fat_below.get(row.sex)
    if row.body_fat_pct is not None and low is not None and row.body_fat_pct < low:
        out.append(
            f"Body fat {row.body_fat_pct:g}% is unusually low (under {low:g}% is rare for a {row.sex} adult). "
            "A too-low value raises your BMR and calorie target a lot; check it against your body-composition "
            "report, or leave it empty."
        )
    return out


async def _out(session, row: ProfileRow) -> ProfileOut:
    targets = await current_targets(session, row.user_id)
    data = {f: getattr(row, f) for f in (*PROFILE_FIELDS, "start_date")}
    return ProfileOut(**data, targets=TargetsOut(**dataclasses.asdict(targets)), warnings=profile_warnings(row))


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: CurrentUser, session: Session) -> ProfileOut:
    row = await get_profile_row(session, user.id)
    if not row:
        raise api_error(status.HTTP_404_NOT_FOUND, "profile_not_found", "Profile not set up")
    return await _out(session, row)


@router.put("/profile", response_model=ProfileOut)
async def upsert_profile(body: ProfileIn, user: CurrentUser, session: Session) -> ProfileOut:
    row = await session.scalar(select(ProfileRow).where(ProfileRow.user_id == user.id))
    if row is None:
        row = ProfileRow(user_id=user.id, start_date=body.start_date or local_today())
        session.add(row)
    for field, value in body.model_dump(include=PROFILE_FIELDS).items():
        setattr(row, field, value.value if hasattr(value, "value") else value)
    if body.start_date:
        row.start_date = body.start_date
    # Targets use the latest weight log, so the profile weight is also today's weigh-in.
    today = local_today()
    weight = await session.scalar(select(WeightLog).where(WeightLog.user_id == user.id, WeightLog.day == today))
    if weight is None:
        session.add(WeightLog(user_id=user.id, day=today, kg=body.weight_kg))
    else:
        weight.kg = body.weight_kg
    await session.commit()
    return await _out(session, row)


@router.get("/targets", response_model=TargetsOut)
async def get_targets(user: CurrentUser, session: Session) -> TargetsOut:
    """Today's targets (uses learned maintenance once there is enough data)."""
    targets = await current_targets(session, user.id)
    if targets is None:
        raise profile_required()
    return TargetsOut(**dataclasses.asdict(targets))
