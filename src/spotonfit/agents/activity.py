"""Parse free-text workouts ("15 min cycling, 40 min heavy weights").

The model estimates the MET (intensity) of each activity; code applies the MET
equation with the user's latest weight (core/targets.workout_kcal). No MET table.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from spotonfit.agents.schemas import WorkoutLog
from spotonfit.core.targets import workout_kcal

SYSTEM = (
    "Extract each physical activity from the user's text with its duration in minutes and intensity. "
    "Use simple activity names like 'cycling', 'treadmill walk', 'weight training', 'running', 'yoga'. "
    "Estimate a realistic MET value for each activity at the described intensity (Compendium of Physical "
    "Activities). If the user did not give a duration, set minutes to null; never invent one."
)

Parser = Callable[[str], Awaitable[WorkoutLog]]


class MissingDuration(ValueError):
    """The user didn't say how long; the API asks instead of guessing."""


def gemini_workout_parser(model=None) -> Parser:
    async def _parse(text: str) -> WorkoutLog:
        from spotonfit.agents.models import parser_model

        llm = (model or parser_model()).with_structured_output(WorkoutLog)
        return await llm.ainvoke([SystemMessage(SYSTEM), HumanMessage(text)])

    return _parse


async def parse_workouts(text: str, weight_kg: float, parser: Parser) -> list[dict]:
    log = await parser(text)
    missing = [w.activity for w in log.workouts if not w.minutes]
    if missing:
        raise MissingDuration(f"How many minutes of {', '.join(missing)}?")
    return [
        {
            "activity": w.activity,
            "minutes": w.minutes,
            "met": w.met,
            "kcal": round(workout_kcal(w.met, w.minutes, weight_kg)),
        }
        for w in log.workouts
    ]
