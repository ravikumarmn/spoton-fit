"""Typed settings (pydantic-settings). Every tunable number in SpotOn lives here.

Values come from, in order of priority:
1. real environment variables,
2. a `.env` file in the repository root (copy `.env.example` to `.env`),
3. the defaults below.

Field names map to UPPER_CASE env vars (`database_url` -> `DATABASE_URL`) unless an
explicit alias is given (`SPOTON_VISION_MODEL`, ...). Nested policies use a double
underscore: `TARGETS__DEFICIT_FRACTION=0.15`, `LIMITS__AI_PER_DAY=50`,
`TARGETS__PROTEIN_G_PER_KG='{"lose_fat": 1.8, "build_muscle": 2.0, "maintain": 1.6}'`.

What is NOT configurable, on purpose: food and activity nutrition data (estimated
by the model for each meal/workout), and textbook equations and physical constants
(Mifflin-St Jeor, Katch-McArdle, the MET equation, 4/4/9 kcal per gram), which are
definitions rather than tuning choices. Defaults below follow Technical PRD section 9.
"""

from __future__ import annotations

import logging
import secrets
from functools import cached_property
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

# src/spotonfit/config.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]

# Gemini 3.x reasoning depth. Gemini 3.6+ ignores temperature/top_p/top_k (and
# future models reject them), so thinking_level is the knob for speed vs depth.
ThinkingLevel = Literal["minimal", "low", "medium", "high"]


class TargetPolicy(BaseModel):
    """How daily targets are derived from a profile (Technical PRD section 9)."""

    activity_factors: dict[str, float] = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
    deficit_fraction: float = Field(0.20, ge=0, le=0.35, description="Calorie cut for lose_fat")
    surplus_fraction: float = Field(0.08, ge=0, le=0.25, description="Calorie surplus for build_muscle")
    protein_g_per_kg: dict[str, float] = {"lose_fat": 1.7, "build_muscle": 2.0, "maintain": 1.6}
    # Safety floor = max(BMR, this value by sex). PRD section 10.
    floor_kcal: dict[str, float] = {"male": 1500, "female": 1200}
    # Above this body-fat %, protein is based on a reference weight, not total weight.
    high_body_fat_pct: dict[str, float] = {"male": 25, "female": 32}
    reference_body_fat_pct: float = 15  # reference weight = lean mass at this body-fat %
    # Below these the profile shows a warning: a too-low body fat inflates BMR (Katch-McArdle).
    unusual_body_fat_below: dict[str, float] = {"male": 8, "female": 15}
    fat_fraction_of_kcal: float = 0.27
    fat_min_g_per_kg: float = 0.6
    carbs_min_g: float = 50
    fibre_g_per_1000_kcal: float = 14
    water_ml_per_kg: float = 35
    step_increment_per_week: int = 500
    step_cap: int = 10_000
    kcal_round_up_to: int = 10


class EnergyPolicy(BaseModel):
    """Energy balance, weight trend and learned maintenance (Technical PRD section 9)."""

    kcal_per_kg_body_weight: float = 7700  # energy in 1 kg of body-weight change
    walk_kcal_per_kg_per_km: float = 0.5
    steps_per_km: float = 1350
    trend_alpha: float = Field(0.1, gt=0, le=1, description="EMA smoothing for the weight trend")
    tdee_window_days: int = 21
    tdee_min_logged_days: int = 14
    tdee_min_weigh_ins: int = 6
    tdee_prior_weight: float = Field(0.7, ge=0, le=1, description="Blend: prior x w + observed x (1 - w)")
    tdee_max_weekly_change_kcal: float = 100  # learned maintenance moves at most this much per week
    prediction_band_kcal: float = 150  # +- uncertainty on maintenance for prediction ranges


class ReviewPolicy(BaseModel):
    """Weekly review and target proposals (PRD P-05; Technical PRD section 9)."""

    backfill_weeks: int = 8  # how many missed weeks to generate at most
    good_adherence_days: int = 5  # logged days AND on-target days needed to call a week "consistent"
    kcal_on_target_tolerance: float = 0.10  # a day is on target within +-10% of the calorie target
    protein_hit_fraction: float = 0.9  # a day hits protein at >= 90% of the target
    stall_weeks: int = 2  # weeks of no progress before proposing a change
    stall_kg_per_week: float = 0.1  # less trend change than this per week = stalled
    maintain_drift_kg_per_week: float = 0.25
    max_weekly_loss_pct: float = 1.0  # PRD safety: faster loss than ~1% body weight per week
    max_weekly_gain_pct: float = 0.5
    proposal_steps: int = 1500
    proposal_kcal: int = 100
    prediction_weeks: int = 4  # "in 4 weeks: x-y kg"
    progress_days: int = 90  # weight series length on /v1/progress


class EstimatePolicy(BaseModel):
    """Checks applied to the model's food estimates before the user sees them."""

    # Flag an item when its calories disagree with 4p + 4c + 9f by more than this fraction.
    macro_energy_tolerance: float = 0.25
    low_confidence: float = 0.5  # flag items the model is unsure about
    oily_levels: list[str] = ["medium", "heavy"]  # oil levels reported as "oily"
    suggestion_kcal_slack: float = 0.10  # a suggestion "fits" if within kcal left x (1 + slack)


class SafetyPolicy(BaseModel):
    """Deterministic safety routing for the coach (PRD C-06). If a message contains one of
    these phrases, the fixed reply is returned and the model is not asked for diet advice.
    Matching is case-insensitive substring matching; it errs on the side of caution.
    A red-flag match is then confirmed by the small model ("no chest pain" is not a symptom);
    if that check fails or times out, the fixed reply still goes out. Support matches
    (self-harm, purging) are never second-guessed."""

    confirm_red_flags: bool = True
    confirm_timeout_s: float = 6.0

    red_flag_terms: list[str] = [
        "chest pain", "chest tightness", "fainted", "fainting", "passed out", "blacked out",
        "dizzy", "dizziness", "palpitation", "heart racing", "shortness of breath",
        "can't breathe", "cannot breathe", "blood in stool", "vomiting blood", "severe headache",
        "numbness", "slurred speech",
    ]  # fmt: skip
    red_flag_reply: str = (
        "Please stop and get medical help first. Symptoms like these need a doctor, not a diet change. "
        "If it is severe or sudden (chest pain, fainting, trouble breathing), call 112 or go to the nearest "
        "emergency department now. I'll help with food and training once you've been checked."
    )
    support_terms: list[str] = [
        "make myself vomit", "make myself throw up", "purge", "purging", "starve myself", "starving myself",
        "laxatives to lose", "eat nothing for", "hate my body", "self harm", "self-harm", "hurt myself",
        "kill myself", "suicid",
    ]  # fmt: skip
    support_reply: str = (
        "Thank you for telling me. You deserve support, not punishment, and I won't help with purging, "
        "starving or anything that could hurt you. Please talk to someone you trust or a professional: "
        "in India, Tele-MANAS is free and open 24x7 on 14416. If you feel unsafe right now, call 112."
    )


class LimitsPolicy(BaseModel):
    """Rate limits (Technical PRD section 5). In-process: fine for one container."""

    login_per_minute: int = 5  # per IP, on login/token/register
    ai_per_minute: int = 30  # per user, on analyze/coach/suggestions/workouts
    ai_per_day: int = 100  # per user per local day
    general_per_minute: int = 120  # per user, every authenticated request


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files win: a .env in the current directory overrides the repo-root one.
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite+aiosqlite:///./spotonfit.db"
    # dev: apply Alembic migrations on startup. prod: the deploy pipeline runs them.
    auto_migrate: bool = True
    timezone: str = Field("Asia/Kolkata", alias="SPOTON_TZ")

    # --- Auth (Technical PRD section 5) ----------------------------------------
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "spotonfit-api"
    jwt_audience: str = "spotonfit-clients"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    allow_registration: bool = True
    # Privacy policy page (GET /privacy): who to contact (email or URL; empty = "the person who
    # invited you") and the date the text last changed.
    privacy_contact: str = ""
    privacy_updated: str = "20 November 2026"
    # JSON list in env, e.g. CORS_ORIGINS='["http://localhost:8501"]'
    cors_origins: list[str] = ["http://localhost:8501", "http://127.0.0.1:8501", "http://localhost:3000"]

    # --- LLM (LangChain init_chat_model) ---------------------------------------
    # The API key is read from GOOGLE_API_KEY (GEMINI_API_KEY also works).
    model_provider: str = Field("google_genai", alias="SPOTON_MODEL_PROVIDER")
    vision_model: str = Field("gemini-3.8-flash", alias="SPOTON_VISION_MODEL")
    coach_model: str = Field("gemini-3.8-flash", alias="SPOTON_COACH_MODEL")
    parser_model: str = Field("gemini-3.5-flash-lite", alias="SPOTON_PARSER_MODEL")
    # gemini-3.8-flash accepts low | medium | high (NOT minimal);
    # gemini-3.5-flash-lite accepts minimal | low | medium | high.
    vision_thinking: ThinkingLevel = Field("low", alias="SPOTON_VISION_THINKING")
    coach_thinking: ThinkingLevel = Field("low", alias="SPOTON_COACH_THINKING")
    parser_thinking: ThinkingLevel = Field("minimal", alias="SPOTON_PARSER_THINKING")
    llm_timeout_s: float = Field(20.0, alias="SPOTON_LLM_TIMEOUT_S")  # per model call
    llm_max_retries: int = Field(2, alias="SPOTON_LLM_MAX_RETRIES")
    photo_budget_s: float = Field(15.0, alias="SPOTON_PHOTO_BUDGET_S")  # whole /meals/analyze
    coach_budget_s: float = Field(45.0, alias="SPOTON_COACH_BUDGET_S")  # whole coach turn
    google_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    # --- Policies (all tunable numbers) ------------------------------------------
    targets: TargetPolicy = TargetPolicy()
    energy: EnergyPolicy = EnergyPolicy()
    estimates: EstimatePolicy = EstimatePolicy()
    limits: LimitsPolicy = LimitsPolicy()
    safety: SafetyPolicy = SafetyPolicy()
    reviews: ReviewPolicy = ReviewPolicy()
    # Weeks run Sunday-Saturday by default, so the weekly review is ready every Sunday for
    # the completed week (PRD section 8). Used by reviews, food rules and weekly History.
    week_starts_on: Literal["monday", "sunday"] = "sunday"

    # --- Coach memory (LangGraph checkpointer) -------------------------------------
    # auto: Postgres DATABASE_URL -> AsyncPostgresSaver in the same database;
    #       SQLite -> AsyncSqliteSaver in CHAT_DB_PATH. memory: in-process only (lost on restart).
    coach_memory: Literal["auto", "memory"] = "auto"
    chat_db_path: str = "./spotonfit_chat.db"
    checkpoint_pool_size: int = 5
    max_my_foods: int = 100
    max_rules: int = 30

    # --- Uploads -----------------------------------------------------------------
    max_upload_mb: int = 10
    image_max_side_px: int = 1024  # photos are resized to this before the model sees them
    image_jpeg_quality: int = Field(85, ge=30, le=100)
    thumbnail_side_px: int = 384
    thumbnail_jpeg_quality: int = Field(70, ge=30, le=100)

    # --- History and caches --------------------------------------------------------
    history_default_days: int = 30  # when the user has no profile start date
    history_max_days: int = 3660
    coach_history_rows: int = 12  # rows the coach's get_history tool returns
    coach_cache_size: int = 256  # compiled coach agents kept per process (LRU)
    recent_meals_days: int = 14  # window for GET /v1/meals/recent
    recent_meals_limit: int = 10
    food_memory_prompt_limit: int = 60  # remembered food names shown to the model

    # --- Observability --------------------------------------------------------
    log_level: str = "INFO"
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "spotonfit"
    mlflow_tracking_uri: str | None = None

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        """Accept plain Postgres URLs (Neon/Supabase/Render) and use asyncpg."""
        for prefix in ("postgres://", "postgresql://", "postgresql+psycopg://"):
            if v.startswith(prefix):
                v = "postgresql+asyncpg://" + v.removeprefix(prefix)
        if v.startswith("postgresql+asyncpg://"):
            v = v.replace("sslmode=require", "ssl=require").replace("&channel_binding=require", "")
        return v

    @cached_property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @cached_property
    def jwt_key(self) -> str:
        key = self.jwt_secret.get_secret_value()
        if not key:
            if self.environment == "prod":
                raise RuntimeError("JWT_SECRET must be set in production")
            log.warning("JWT_SECRET not set; using a random key (tokens reset on restart)")
            key = secrets.token_urlsafe(48)
        return key

    @property
    def llm_api_key(self) -> str | None:
        """GOOGLE_API_KEY, else GEMINI_API_KEY (same order as the Google client)."""
        for key in (self.google_api_key, self.gemini_api_key):
            if key is not None and key.get_secret_value():
                return key.get_secret_value()
        return None

    @property
    def has_llm_key(self) -> bool:
        return self.llm_api_key is not None


settings = Settings()
