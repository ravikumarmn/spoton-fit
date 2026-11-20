"""Deterministic safety routing for the coach (PRD C-06, PRD section 10).

Before the model sees a message, `screen` checks it against the configured phrases
(config.SafetyPolicy). Red-flag symptoms get a "see a doctor now" reply; signs of
disordered eating or self-harm get a supportive reply with a helpline. The model is not
asked for diet advice in those cases, so the outcome doesn't depend on the model.
The calorie floor is enforced separately in core/targets.py.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from spotonfit.config import SafetyPolicy, settings

log = logging.getLogger(__name__)

# (message, matched term) -> does the user report this symptom? Errors mean "yes".
SafetyConfirmer = Callable[[str, str], Awaitable[bool]]

CONFIRM_SYSTEM = (
    "A safety filter matched a medical red-flag phrase in a message to a nutrition coach. Decide whether "
    "the user reports having (now or recently) the symptom. Answer applies=false only when it is clearly "
    "negated ('no chest pain'), hypothetical ('what if I feel dizzy'), about someone else, or a general "
    "question. If in doubt, answer applies=true."
)


@dataclass(frozen=True)
class SafetyRoute:
    kind: Literal["red_flag", "support"]
    term: str
    reply: str


def screen(message: str, policy: SafetyPolicy | None = None) -> SafetyRoute | None:
    policy = policy or settings.safety
    text = " ".join(message.lower().split())
    for term in policy.support_terms:  # checked first: the more sensitive route
        if term in text:
            return SafetyRoute("support", term, policy.support_reply)
    for term in policy.red_flag_terms:
        if term in text:
            return SafetyRoute("red_flag", term, policy.red_flag_reply)
    return None


def gemini_safety_confirmer(model=None) -> SafetyConfirmer:
    async def _confirm(message: str, term: str) -> bool:
        from langchain_core.messages import HumanMessage, SystemMessage

        from spotonfit.agents.models import parser_model
        from spotonfit.agents.schemas import SafetyCheck

        llm = (model or parser_model()).with_structured_output(SafetyCheck)
        out = await llm.ainvoke([SystemMessage(CONFIRM_SYSTEM), HumanMessage(f"Matched: {term!r}\nMessage: {message}")])
        return out.applies

    return _confirm


async def screen_confirmed(
    message: str, confirm: SafetyConfirmer | None, policy: SafetyPolicy | None = None
) -> SafetyRoute | None:
    """`screen`, then let the small model drop a red-flag match that is clearly not a symptom.
    Fails safe: any error or timeout keeps the route."""
    policy = policy or settings.safety
    route = screen(message, policy)
    if route is None or route.kind != "red_flag" or not policy.confirm_red_flags or confirm is None:
        return route
    try:
        async with asyncio.timeout(policy.confirm_timeout_s):
            applies = await confirm(message, route.term)
    except TimeoutError:
        log.warning("safety confirmation timed out; keeping the safety reply")
        return route
    except Exception:
        log.warning("safety confirmation failed; keeping the safety reply", exc_info=True)
        return route
    if not applies:
        log.info("safety: red-flag phrase %r judged not a symptom", route.term)
        return None
    return route
