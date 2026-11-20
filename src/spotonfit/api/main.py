"""FastAPI application factory.

Run locally:  uv run uvicorn spotonfit.api.main:app --reload
Docs:         http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from spotonfit import __version__
from spotonfit.agents.activity import gemini_workout_parser
from spotonfit.agents.checkpoint import open_checkpointer
from spotonfit.agents.coach import build_coach
from spotonfit.agents.food_logger import build_food_graph, estimate_text
from spotonfit.agents.rules_parser import gemini_rule_parser
from spotonfit.agents.safety import gemini_safety_confirmer
from spotonfit.agents.suggester import gemini_suggester
from spotonfit.api.errors import install_error_handlers
from spotonfit.api.ratelimit import RateLimiter
from spotonfit.api.routers import (
    auth,
    coach,
    export,
    foods,
    legal,
    meals,
    ops,
    plans,
    profile,
    progress,
    suggestions,
    tracking,
)
from spotonfit.config import settings
from spotonfit.db import Database
from spotonfit.observability import RequestContextMiddleware, setup_logging, setup_tracing
from spotonfit.services import food_memory


def create_app(db: Database | None = None) -> FastAPI:
    """`db` is injected by tests (tables created directly, in-memory coach memory).
    Otherwise the app opens DATABASE_URL, applies migrations when AUTO_MIGRATE is on
    (dev default) and keeps coach conversations in a persistent checkpointer."""
    setup_logging()
    setup_tracing()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db = db or Database()
        if db is not None:
            await app.state.db.create_all()
        elif settings.auto_migrate:
            await app.state.db.migrate()
        app.state.limiter = RateLimiter()
        stack = AsyncExitStack()
        checkpointer = await stack.enter_async_context(
            open_checkpointer(app.state.db.url, "memory" if db is not None else None)
        )
        app.state.checkpointer = checkpointer
        food_graph = build_food_graph()
        parser = gemini_workout_parser()
        suggester = gemini_suggester()
        rule_parser = gemini_rule_parser()
        safety_confirmer = gemini_safety_confirmer()
        coaches: OrderedDict[object, object] = OrderedDict()

        def estimator_for(user_id, sessionmaker):
            """The coach's food estimates use the same graph and the user's food memory."""

            async def estimate(text: str) -> dict:
                async with sessionmaker() as s:
                    memory = await food_memory.load(s, user_id)
                return await estimate_text(app.state.food_graph(), text, memory=memory)

            return estimate

        def coach_factory(user_id, sessionmaker):
            """One compiled coach per user, least-recently-used eviction."""
            if user_id in coaches:
                coaches.move_to_end(user_id)
            else:
                estimate = estimator_for(user_id, sessionmaker)
                coaches[user_id] = build_coach(user_id, sessionmaker, checkpointer, estimate, app.state.suggester())
                if len(coaches) > settings.coach_cache_size:
                    coaches.popitem(last=False)
            return coaches[user_id]

        app.state.food_graph = lambda: food_graph
        app.state.workout_parser = lambda: parser
        app.state.suggester = lambda: suggester
        app.state.rule_parser = lambda: rule_parser
        app.state.safety_confirmer = lambda: safety_confirmer
        app.state.coach_factory = coach_factory
        try:
            yield
        finally:
            await stack.aclose()
            await app.state.db.dispose()

    app = FastAPI(
        title="SpotOn API",
        version=__version__,
        lifespan=lifespan,
        description="AI personal trainer: photo/text food logging, targets, coach and history.",
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RequestContextMiddleware)  # added last = outermost: wraps CORS and errors
    install_error_handlers(app)
    for r in (ops, legal, auth, profile, meals, foods, plans, tracking, progress, suggestions, coach, export):
        app.include_router(r.router)
    return app


app = create_app()
