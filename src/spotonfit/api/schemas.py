"""Request/response models (Pydantic v2). These are the API contract shown in /docs."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator

from spotonfit.agents.schemas import MealSlot, OilLevel
from spotonfit.config import settings
from spotonfit.core.targets import Goal

# --- Auth -------------------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(UserCreate):
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    timezone: str = Field(default_factory=lambda: settings.timezone, description="Timezone 'today' is computed in")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str = Field(description="Opaque; send to /v1/auth/refresh. Rotates on every use.")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds")


class AccountDeleteIn(BaseModel):
    password: str = Field(min_length=1, max_length=128, description="Confirms it is really you")


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=200)


# --- Profile and targets ----------------------------------------------------


class ProfileIn(BaseModel):
    age: int = Field(ge=18, le=100, description="SpotOn is for adults (18+)")
    sex: Literal["male", "female"]
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    goal: Goal = Goal.LOSE_FAT
    activity: Literal["sedentary", "light", "moderate", "active"] = "sedentary"
    body_fat_pct: float | None = Field(None, ge=3, le=70)
    goal_weight_kg: float | None = Field(None, ge=30, le=300)
    baseline_steps: int = Field(5000, ge=0, le=50_000)
    start_date: dt.date | None = None


class TargetsOut(BaseModel):
    bmi: float
    bmr: float
    maintenance: float
    kcal: int
    kcal_floor: int
    protein_g: int
    fat_g: int
    carbs_g: int
    fibre_g: int
    water_ml: int
    steps: int
    kcal_adjustment: int = Field(0, description="From accepted weekly reviews")
    steps_adjustment: int = 0
    maintenance_source: Literal["formula", "learned"] = "formula"


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)
    start_date: dt.date
    targets: TargetsOut
    warnings: list[str] = Field(default_factory=list, description="Inputs worth double-checking")


# --- Meals ------------------------------------------------------------------


class NutrientsIO(BaseModel):
    kcal: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)
    fibre: float = Field(0, ge=0)


class MealItemIn(BaseModel):
    """One food to save. Totals are computed on the server as quantity x per_unit, so
    editing the count (6 eggs -> 4 eggs) is enough to correct a draft."""

    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=100)
    unit: str = Field("serving", min_length=1, max_length=30)
    grams_per_unit: float | None = Field(None, gt=0, le=3000)
    per_unit: NutrientsIO
    oil_level: OilLevel = "none"
    remark: str | None = Field(None, max_length=300)
    # ai_estimate: the model's values · memory: the user's remembered values ·
    # edited: the user changed per-unit values (remembered) · manual: added by hand (remembered)
    source: Literal["ai_estimate", "memory", "edited", "manual"] = "ai_estimate"


class DraftItem(MealItemIn):
    """A draft item: the model's per-unit estimate plus code-computed totals."""

    grams: float
    kcal: float
    protein: float
    carbs: float
    fat: float
    fibre: float
    confidence: float


class MealDraft(BaseModel):
    """Result of analysis; nothing is saved until the user confirms with POST /v1/meals."""

    items: list[DraftItem]
    totals: dict[str, float]
    oily_items: list[str] = Field(default_factory=list, description="Foods that look oily or fried")
    warnings: list[str] = Field(default_factory=list, description="Things to double-check before saving")
    meal_slot: MealSlot
    clarify: str | None = None
    latency_ms: int


def _local_if_naive(v: dt.datetime | None) -> dt.datetime | None:
    return v.replace(tzinfo=settings.tz) if v is not None and v.tzinfo is None else v


# A datetime where a value without a UTC offset means the user's local time.
LocalDateTime = Annotated[dt.datetime | None, AfterValidator(_local_if_naive)]


class MealCreate(BaseModel):
    slot: MealSlot
    items: list[MealItemIn] = Field(min_length=1, max_length=30)
    note: str | None = Field(None, max_length=500)
    source: Literal["photo", "text", "repeat"] = "text"
    eaten_at: LocalDateTime = Field(None, description="Defaults to now; a time without offset is local time")
    is_favourite: bool = False


class MealPatch(BaseModel):
    """Edit a saved meal. Only the fields you send change; `items` replaces all items."""

    slot: MealSlot | None = None
    items: list[MealItemIn] | None = Field(None, min_length=1, max_length=30)
    note: str | None = Field(None, max_length=500)
    eaten_at: LocalDateTime = None
    is_favourite: bool | None = None


class RepeatIn(BaseModel):
    slot: MealSlot | None = Field(None, description="Defaults to the original meal's slot")
    eaten_at: LocalDateTime = Field(None, description="Defaults to now")


class MealItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    quantity: float
    unit: str
    grams: float | None
    kcal: float
    protein: float
    carbs: float
    fat: float
    fibre: float
    oil_level: str
    remark: str | None
    source: str

    @computed_field
    @property
    def per_unit(self) -> dict[str, float]:
        q = self.quantity or 1
        return {k: round(getattr(self, k) / q, 1) for k in ("kcal", "protein", "carbs", "fat", "fibre")}


class MealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    eaten_at: dt.datetime
    slot: str
    note: str | None
    source: str
    is_favourite: bool
    items: list[MealItemOut]

    @computed_field
    @property
    def totals(self) -> dict[str, float]:
        return {
            k: round(sum(getattr(i, k) for i in self.items), 1) for k in ("kcal", "protein", "carbs", "fat", "fibre")
        }


class FoodMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    unit: str
    grams_per_unit: float | None
    kcal: float
    protein: float
    carbs: float
    fat: float
    fibre: float
    times_used: int


# --- Tracking -----------------------------------------------------------------


class WaterIn(BaseModel):
    ml: int = Field(gt=0, le=3000)
    day: dt.date | None = Field(None, description="Local day to log for (default today); not in the future")


class WeightIn(BaseModel):
    kg: float = Field(ge=30, le=300)
    day: dt.date | None = Field(None, description="Local day (default today); not in the future")


class StepsIn(BaseModel):
    steps: int = Field(ge=0, le=150_000)


class WorkoutIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    day: dt.date | None = Field(None, description="Local day to log for (default today); not in the future")


class WorkoutOut(BaseModel):
    activity: str
    minutes: float
    met: float = Field(description="Intensity estimated by the model")
    kcal: float = Field(description="MET x weight (kg) x hours")


class TodayOut(BaseModel):
    day: dt.date
    eaten: dict[str, float]
    left: dict[str, float]
    targets: TargetsOut | None
    water_ml: int
    steps: int
    workout_min: float
    burned_kcal_est: float
    nudges: list[str] = Field(default_factory=list, description="Gentle notes from your food rules")
    # Everything the Today screen needs in one call (it used to make three).
    meals: list[MealOut] = Field(default_factory=list, description="The day's meals, oldest first")
    weekly_review: WeeklyReviewOut | None = Field(None, description="Only when the day is today")


class HistoryOut(BaseModel):
    period: Literal["day", "week", "month", "year"]
    start: dt.date
    end: dt.date
    days_logged: int
    rows: list[dict]
    weight_trend: list[dict]


# --- Progress, reviews, measurements (PRD Phase 3) ---------------------------------


class MeasurementIn(BaseModel):
    day: dt.date | None = Field(None, description="Defaults to today; logging the same day again replaces it")
    waist_cm: float | None = Field(None, ge=40, le=250)
    hip_cm: float | None = Field(None, ge=40, le=250)
    body_fat_pct: float | None = Field(None, ge=3, le=70, description="Also used for BMR (Katch-McArdle)")

    @model_validator(mode="after")
    def _something(self):
        if self.waist_cm is None and self.hip_cm is None and self.body_fat_pct is None:
            raise ValueError("send at least one of waist_cm, hip_cm, body_fat_pct")
        return self


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    day: dt.date
    waist_cm: float | None
    hip_cm: float | None
    body_fat_pct: float | None


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    week_start: dt.date
    summary: dict
    proposal: dict | None = Field(None, description="At most one change: {kind: steps|kcal, delta, text, reason}")
    decision: Literal["accepted", "rejected"] | None
    decided_at: dt.datetime | None


class WeeklyReviewOut(BaseModel):
    review: ReviewOut | None = Field(None, description="The latest completed week's review")
    pending_decision: bool
    next_review_on: dt.date


class DecisionIn(BaseModel):
    decision: Literal["accept", "reject"]


class ProgressOut(BaseModel):
    weight: dict = Field(description="latest_kg, trend_kg, trend_change_4w_kg, series [{day, kg, trend_kg}]")
    maintenance: dict = Field(description="active, kcal, formula_kcal, explanation, history")
    prediction: dict | None = Field(None, description="Goal-weight date range (needs a goal weight)")
    in_weeks: dict | None = Field(None, description="Trend weight range N weeks from now")
    measurements: list[dict]
    logged_days_in_window: int


# --- Suggestions and coach ---------------------------------------------------


class SuggestionOut(BaseModel):
    title: str
    why: str
    items: list[DraftItem]
    totals: dict[str, float]
    fits: bool = Field(description="True if the option fits the calories left today")
    only_my_foods: bool | None = Field(None, description="my_foods mode: built only from your My Foods")


class SuggestionsOut(BaseModel):
    mode: Literal["my_foods", "ideal"]
    left: dict[str, float]
    options: list[SuggestionOut]
    note: str | None = None


# --- My Foods and rules ------------------------------------------------------------

Effort = Literal["no_cook", "5_min", "buy_nearby", "order"]


class MyFoodIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    effort: Effort = "no_cook"
    slots: list[MealSlot] = Field(default_factory=list, description="Meals it suits; empty = any")
    available: bool = True


class MyFoodOut(MyFoodIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class RuleParseIn(BaseModel):
    text: str = Field(min_length=3, max_length=300, examples=["idli at most 3 days a week", "no tea after 4 PM"])


class RuleIn(BaseModel):
    """A rule to save, usually the confirmed result of POST /v1/rules/parse."""

    kind: Literal["max_days_per_week", "max_per_day", "not_after", "not_before", "avoid"]
    food: str = Field(min_length=1, max_length=120)
    limit: int | None = Field(None, ge=0, le=50)
    time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    summary: str = Field(min_length=1, max_length=300)
    original_text: str = Field("", max_length=300)


class RuleOut(RuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID | None = None
    state: Literal["ok", "at_limit", "broken"] | None = None
    blocks_now: bool | None = None
    status: str | None = Field(None, description="Today's status in plain words")


class CoachNotes(BaseModel):
    notes: str = Field("", max_length=1000, description="Things the coach should remember across days")


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(None, max_length=64)


class ChatOut(BaseModel):
    reply: str
    thread_id: str
    safety: Literal["red_flag", "support"] | None = Field(None, description="Set when a safety reply was given")


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ThreadOut(BaseModel):
    thread_id: str
    messages: list[ChatMessage]


TodayOut.model_rebuild()  # resolves the forward reference to WeeklyReviewOut
