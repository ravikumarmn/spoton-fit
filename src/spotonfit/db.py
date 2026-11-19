"""Async database layer (SQLAlchemy 2 asyncio). SQLite (aiosqlite) locally,
Postgres (asyncpg) in production via DATABASE_URL. Schema changes go through
Alembic migrations in `spotonfit/migrations` (Technical PRD section 7).

Conventions:
- Every table has a UUID `id`, `created_at` and `updated_at`; user-owned rows have
  an indexed `user_id` with ON DELETE CASCADE.
- All timestamps are stored in UTC through `UTCDateTime`, so SQLite (no timezone
  type) and Postgres (`timestamptz`) behave the same. "Which day is this?" is decided
  only when reading, by converting to the user's timezone.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import AsyncIterator

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from spotonfit.config import settings


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class UTCDateTime(TypeDecorator[dt.datetime]):
    """Timezone-aware datetime stored as UTC on every backend.

    Writes: aware datetimes are converted to UTC; naive ones are rejected (ambiguous).
    Reads: always returns an aware UTC datetime (SQLite hands back naive values).
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; pass a timezone-aware value")
        value = value.astimezone(dt.UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: dt.datetime | None, dialect) -> dt.datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value.astimezone(dt.UTC)


# Deterministic constraint names, so Alembic migrations work the same on SQLite and Postgres.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


def user_fk() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshToken(Base):
    """Opaque refresh tokens, stored only as SHA-256 hashes. Each refresh rotates the
    token within its `family_id`; reusing a rotated token revokes the whole family."""

    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = user_fk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ProfileRow(Base):
    __tablename__ = "profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(10))
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    goal: Mapped[str] = mapped_column(String(20))
    activity: Mapped[str] = mapped_column(String(20), default="sedentary")
    body_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_steps: Mapped[int] = mapped_column(Integer, default=5000)
    start_date: Mapped[dt.date] = mapped_column(Date)
    # Cumulative changes from accepted weekly reviews (PRD P-05); applied on top of the formula.
    kcal_adjustment: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    steps_adjustment: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Meal(Base):
    __tablename__ = "meals"
    # client_key = the Idempotency-Key header of POST /v1/meals (a retried save returns the same meal).
    __table_args__ = (UniqueConstraint("user_id", "client_key"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    eaten_at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), index=True)
    slot: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(10))  # photo | text | repeat
    is_favourite: Mapped[bool] = mapped_column(Boolean, default=False)
    client_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thumbnail: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    items: Mapped[list[MealItem]] = relationship(back_populates="meal", cascade="all, delete-orphan", lazy="selectin")


class MealItem(Base):
    """One food in a meal. Nutrient columns are TOTALS for `quantity` units; the
    per-unit values are totals / quantity."""

    __tablename__ = "meal_items"
    meal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meals.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    fibre: Mapped[float] = mapped_column(Float, default=0)
    oil_level: Mapped[str] = mapped_column(String(10), default="none")
    remark: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source: Mapped[str] = mapped_column(String(20))  # ai_estimate | memory | edited | manual
    meal: Mapped[Meal] = relationship(back_populates="items")


class FoodMemory(Base):
    """The user's own per-unit values for a food, learned when they correct or add an
    item. Next time the model names the same food, these values replace its estimate."""

    __tablename__ = "food_memory"
    __table_args__ = (UniqueConstraint("user_id", "name_key"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    name_key: Mapped[str] = mapped_column(String(120))  # core.nutrition.food_key(name)
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(30))
    grams_per_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    kcal: Mapped[float] = mapped_column(Float)  # per unit
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    fibre: Mapped[float] = mapped_column(Float, default=0)
    times_used: Mapped[int] = mapped_column(Integer, default=0)


class MyFood(Base):
    """Foods the user can actually get (PRD C-03). Suggestions in "my_foods" mode use only
    available ones. Nutrition comes from food memory or the model, never from this table."""

    __tablename__ = "my_foods"
    __table_args__ = (UniqueConstraint("user_id", "name_key"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120))
    effort: Mapped[str] = mapped_column(String(20))  # no_cook | 5_min | buy_nearby | order
    slots: Mapped[list[str]] = mapped_column(JSON, default=list)  # meal slots it suits; empty = any
    available: Mapped[bool] = mapped_column(Boolean, default=True)


class FoodRule(Base):
    """A plain-English food rule the user confirmed (PRD C-04), stored as structured
    fields and checked by core.rules (code, not the model)."""

    __tablename__ = "food_rules"
    user_id: Mapped[uuid.UUID] = user_fk()
    kind: Mapped[str] = mapped_column(String(30))  # max_days_per_week | max_per_day | not_after | not_before | avoid
    food: Mapped[str] = mapped_column(String(120))
    limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # HH:MM local
    summary: Mapped[str] = mapped_column(String(300))
    original_text: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class WaterLog(Base):
    __tablename__ = "water_logs"
    user_id: Mapped[uuid.UUID] = user_fk()
    at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), index=True)
    ml: Mapped[int] = mapped_column(Integer)


class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    kg: Mapped[float] = mapped_column(Float)


class StepLog(Base):
    __tablename__ = "step_logs"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    steps: Mapped[int] = mapped_column(Integer)


class Measurement(Base):
    """Body measurements (PRD P-06). One row per day; any field may be empty."""

    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("user_id", "day"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    day: Mapped[dt.date] = mapped_column(Date, index=True)
    waist_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    hip_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class TdeeEstimate(Base):
    """Learned maintenance, one per completed week (PRD P-03). Targets use the latest."""

    __tablename__ = "tdee_estimates"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    week_start: Mapped[dt.date] = mapped_column(Date)
    tdee: Mapped[float] = mapped_column(Float)
    observed: Mapped[float] = mapped_column(Float)  # what the data alone says
    previous: Mapped[float] = mapped_column(Float)  # estimate (or formula) before this week
    uncertainty: Mapped[float] = mapped_column(Float)  # +- kcal used for prediction ranges
    explanation: Mapped[str] = mapped_column(Text)


class WeeklyReview(Base):
    """Weekly review (PRD P-05): summary, at most one proposed change, and the decision."""

    __tablename__ = "weekly_reviews"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)
    user_id: Mapped[uuid.UUID] = user_fk()
    week_start: Mapped[dt.date] = mapped_column(Date)
    summary: Mapped[dict] = mapped_column(JSON)
    proposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(10), nullable=True)  # accepted | rejected
    decided_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Workout(Base):
    __tablename__ = "workouts"
    user_id: Mapped[uuid.UUID] = user_fk()
    at: Mapped[dt.datetime] = mapped_column(UTCDateTime(), index=True)
    activity: Mapped[str] = mapped_column(String(80))
    minutes: Mapped[float] = mapped_column(Float)
    met: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Database:
    """Owns the engine and session factory; one per app (tests create their own)."""

    def __init__(self, url: str | None = None):
        self.url = url or settings.database_url
        kwargs: dict = {"pool_pre_ping": True}
        if not self.url.startswith("sqlite"):
            kwargs.update(pool_size=5, max_overflow=10)
        self.engine: AsyncEngine = create_async_engine(self.url, **kwargs)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        """Create tables directly (tests only; real databases use `migrate`)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def migrate(self) -> None:
        """Apply Alembic migrations up to head (dev startup convenience)."""
        import asyncio

        from spotonfit.migrations.runner import upgrade_head

        await asyncio.to_thread(upgrade_head, self.url)

    async def ping(self) -> None:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as s:
            yield s

    async def dispose(self) -> None:
        await self.engine.dispose()
