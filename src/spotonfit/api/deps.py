"""Shared FastAPI dependencies. Agents are dependencies too, so tests can override
them with stubs (no API calls)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db.sessionmaker() as session:
        yield session


Session = Annotated[AsyncSession, Depends(get_session)]


def get_food_graph(request: Request):
    return request.app.state.food_graph()


def get_workout_parser(request: Request):
    return request.app.state.workout_parser()


def get_suggester(request: Request):
    return request.app.state.suggester()


def get_rule_parser(request: Request):
    return request.app.state.rule_parser()


def get_coach_factory(request: Request):
    return request.app.state.coach_factory
