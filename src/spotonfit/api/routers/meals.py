"""Meal logging: analyze (photo and/or text -> draft), save, list, delete.

Flow (PRD T-03..T-06):
1. POST /v1/meals/analyze returns a draft and saves nothing. Each item has the model's
   per-unit estimate (one egg, one idli, one katori) and code-computed totals, plus
   oiliness and warnings.
2. The user reviews it: fix a count, remove an item, or replace a per-unit value.
3. POST /v1/meals saves it. Totals are recomputed on the server as quantity x per_unit.
   Send an `Idempotency-Key` header so a retried save never creates a duplicate.
   Corrected per-unit values are remembered for next time (services/food_memory.py).

Also: PATCH (edit), favourites, recent meals and one-tap repeat (PRD T-08).
"""

import asyncio
import base64
import datetime as dt
import io
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from spotonfit.agents.food_logger import shrink_image
from spotonfit.agents.models import LLMNotConfigured
from spotonfit.api.deps import Session, get_food_graph
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import ai_limit
from spotonfit.api.schemas import MealCreate, MealDraft, MealItemIn, MealOut, MealPatch, RepeatIn
from spotonfit.api.security import CurrentUser
from spotonfit.config import settings
from spotonfit.core.nutrition import Nutrients, item_totals
from spotonfit.db import Meal, MealItem
from spotonfit.observability import hash_user
from spotonfit.services import food_memory
from spotonfit.services.ledger import day_bounds, local_today

router = APIRouter(prefix="/v1/meals", tags=["meals"])
log = logging.getLogger(__name__)

# HEIC/HEIF (iPhone default) can't be decoded by Pillow, but Gemini accepts it natively.
PASSTHROUGH = {"image/heic", "image/heif"}
BAD_TYPE = "Send a JPG, PNG, WEBP or HEIC photo"


def sniff_image_type(data: bytes) -> str | None:
    """Detect the real image type from magic bytes (the client's content-type is not trusted)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx"}:
            return "image/heic"
        if brand in {b"mif1", b"msf1", b"heif"}:
            return "image/heif"
    return None


async def read_upload(image: UploadFile) -> bytes:
    """Read at most max_upload_mb (+1 byte to detect overflow) without buffering huge bodies."""
    limit = settings.max_upload_mb * 1024 * 1024
    data = await image.read(limit + 1)
    if len(data) > limit:
        raise api_error(
            status.HTTP_413_CONTENT_TOO_LARGE, "image_too_large", f"Image larger than {settings.max_upload_mb} MB"
        )
    return data


async def prepare_image(data: bytes) -> tuple[str, str]:
    """Validate and shrink an upload. Returns (base64, mime) for the model."""
    kind = sniff_image_type(data)
    if kind is None:
        raise api_error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_image", BAD_TYPE)
    try:
        return await asyncio.to_thread(shrink_image, data)
    except Exception as e:  # PIL.UnidentifiedImageError, OSError, DecompressionBombError, ...
        if kind in PASSTHROUGH:
            return base64.b64encode(data).decode(), kind
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "unreadable_image", "Could not read this image") from e


def _thumbnail(data: bytes) -> bytes:
    from PIL import Image

    side = settings.thumbnail_side_px
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=settings.thumbnail_jpeg_quality)
    return buf.getvalue()


def to_row(item: MealItemIn) -> MealItem:
    """Totals = quantity x per-unit values (computed here, never trusted from the client)."""
    totals = item_totals(Nutrients(**item.per_unit.model_dump()), item.quantity)
    grams = round(item.grams_per_unit * item.quantity) if item.grams_per_unit else None
    return MealItem(
        name=item.name,
        quantity=item.quantity,
        unit=item.unit,
        grams=grams,
        **totals.as_dict(),
        oil_level=item.oil_level,
        remark=item.remark,
        source=item.source,
    )


def copy_row(item: MealItem) -> MealItem:
    """Duplicate a saved item (for repeat)."""
    fields = ("name", "quantity", "unit", "grams", "kcal", "protein", "carbs", "fat", "fibre", "oil_level", "remark")
    return MealItem(**{f: getattr(item, f) for f in fields}, source=item.source)


async def own_meal(session, meal_id: uuid.UUID, user_id: uuid.UUID) -> Meal:
    meal = await session.scalar(select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id))
    if meal is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "meal_not_found", "Meal not found")
    return meal


@router.post("/analyze", response_model=MealDraft)
async def analyze(
    user: CurrentUser,
    request: Request,
    session: Session,
    graph: Annotated[object, Depends(get_food_graph)],
    image: Annotated[UploadFile | None, File(description="Meal photo (camera or gallery)")] = None,
    note: Annotated[str | None, Form(max_length=500)] = None,
) -> MealDraft:
    """Photo and/or text -> draft meal with estimated calories and macros. Nothing is saved."""
    if image is None and not note:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "empty_request", "Send a photo, a note, or both")
    ai_limit(request, user.id)
    state: dict = {
        "note": note,
        "local_time": dt.datetime.now(settings.tz).strftime("%H:%M"),
        "memory": await food_memory.load(session, user.id),
    }
    if image is not None:
        state["image_b64"], state["mime"] = await prepare_image(await read_upload(image))
    try:
        async with asyncio.timeout(settings.photo_budget_s):
            result = await graph.ainvoke(
                state, config={"tags": ["food_logger"], "metadata": {"user": hash_user(user.id)}}
            )
    except LLMNotConfigured as e:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "ai_not_configured", str(e)) from e
    except TimeoutError as e:
        log.warning("food analysis exceeded %.0fs budget", settings.photo_budget_s)
        raise api_error(status.HTTP_504_GATEWAY_TIMEOUT, "timeout", "Analysis took too long, please try again") from e
    except Exception as e:
        log.exception("food analysis failed")
        raise api_error(status.HTTP_502_BAD_GATEWAY, "ai_failed", "Food analysis failed, try again") from e
    return MealDraft(
        items=result["items"],
        totals=result["totals"],
        oily_items=result.get("oily_items", []),
        warnings=result.get("warnings", []),
        meal_slot=result["estimate"].meal_slot,
        clarify=result["estimate"].clarify,
        latency_ms=result.get("latency_ms", 0),
    )


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def create_meal(
    body: MealCreate,
    user: CurrentUser,
    session: Session,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=64)] = None,
) -> Meal:
    """Save a confirmed meal. Totals are recomputed as quantity x per_unit.
    Repeating a request with the same Idempotency-Key returns the first meal (200)."""
    if idempotency_key:
        existing = await session.scalar(select(Meal).where(Meal.user_id == user.id, Meal.client_key == idempotency_key))
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing
    items = [to_row(i) for i in body.items]
    meal = Meal(
        user_id=user.id,
        eaten_at=body.eaten_at or dt.datetime.now(dt.UTC),
        slot=body.slot,
        note=body.note,
        source=body.source,
        is_favourite=body.is_favourite,
        client_key=idempotency_key,
        items=items,
    )
    session.add(meal)
    await food_memory.remember(session, user.id, body.items)
    try:
        await session.commit()
    except IntegrityError:  # the same key raced in from a parallel retry
        await session.rollback()
        response.status_code = status.HTTP_200_OK
        return await session.scalar(select(Meal).where(Meal.user_id == user.id, Meal.client_key == idempotency_key))
    await session.refresh(meal, ["items"])
    log.info("meal saved: %.0f kcal", sum(i.kcal for i in items))
    return meal


@router.get("/favourites", response_model=list[MealOut])
async def favourites(user: CurrentUser, session: Session) -> list[Meal]:
    """Meals marked as favourite, newest first (repeat them with POST /{id}/repeat)."""
    rows = await session.scalars(
        select(Meal).where(Meal.user_id == user.id, Meal.is_favourite.is_(True)).order_by(Meal.eaten_at.desc())
    )
    return list(rows)


@router.get("/recent", response_model=list[MealOut])
async def recent(user: CurrentUser, session: Session) -> list[Meal]:
    """Recent meals (RECENT_MEALS_DAYS / RECENT_MEALS_LIMIT), newest first."""
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=settings.recent_meals_days)
    rows = await session.scalars(
        select(Meal)
        .where(Meal.user_id == user.id, Meal.eaten_at >= since)
        .order_by(Meal.eaten_at.desc())
        .limit(settings.recent_meals_limit)
    )
    return list(rows)


@router.get("/{meal_id}", response_model=MealOut)
async def get_meal(meal_id: uuid.UUID, user: CurrentUser, session: Session) -> Meal:
    return await own_meal(session, meal_id, user.id)


@router.patch("/{meal_id}", response_model=MealOut)
async def edit_meal(meal_id: uuid.UUID, body: MealPatch, user: CurrentUser, session: Session) -> Meal:
    """Edit a saved meal: slot, note, time, favourite flag, or replace its items."""
    meal = await own_meal(session, meal_id, user.id)
    for field, value in body.model_dump(exclude_unset=True, exclude={"items"}).items():
        if value is None and field != "note":  # only the note can be cleared
            continue
        setattr(meal, field, value)
    if body.items is not None:
        meal.items = [to_row(i) for i in body.items]
        await food_memory.remember(session, user.id, body.items)
    await session.commit()
    await session.refresh(meal, ["items"])
    return meal


@router.post("/{meal_id}/repeat", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def repeat_meal(meal_id: uuid.UUID, user: CurrentUser, session: Session, body: RepeatIn | None = None) -> Meal:
    """Log a saved meal again, now (one tap). No model call."""
    original = await own_meal(session, meal_id, user.id)
    body = body or RepeatIn()
    meal = Meal(
        user_id=user.id,
        eaten_at=body.eaten_at or dt.datetime.now(dt.UTC),
        slot=body.slot or original.slot,
        note=original.note,
        source="repeat",
        items=[copy_row(i) for i in original.items],
    )
    session.add(meal)
    await session.commit()
    await session.refresh(meal, ["items"])
    return meal


@router.post("/{meal_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
async def attach_photo(
    meal_id: uuid.UUID, user: CurrentUser, session: Session, image: Annotated[UploadFile, File()]
) -> None:
    meal = await own_meal(session, meal_id, user.id)
    data = await read_upload(image)
    if sniff_image_type(data) is None:
        raise api_error(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_image", BAD_TYPE)
    try:
        meal.thumbnail = await asyncio.to_thread(_thumbnail, data)
    except Exception as e:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "unreadable_image", "Could not read this image") from e
    await session.commit()


@router.get("", response_model=list[MealOut])
async def list_meals(
    user: CurrentUser, session: Session, day: Annotated[dt.date | None, Query(alias="date")] = None
) -> list[Meal]:
    """Meals for one local day (default today)."""
    start, end = day_bounds(day or local_today())
    rows = await session.scalars(
        select(Meal).where(Meal.user_id == user.id, Meal.eaten_at >= start, Meal.eaten_at < end).order_by(Meal.eaten_at)
    )
    return list(rows)


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(meal_id: uuid.UUID, user: CurrentUser, session: Session) -> None:
    await own_meal(session, meal_id, user.id)
    await session.execute(delete(MealItem).where(MealItem.meal_id == meal_id))
    await session.execute(delete(Meal).where(Meal.id == meal_id))
    await session.commit()
