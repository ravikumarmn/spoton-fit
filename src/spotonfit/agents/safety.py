"""Deterministic safety routing for the coach (PRD C-06, PRD section 10).

Before the model sees a message, `screen` checks it against the configured phrases
(config.SafetyPolicy). Red-flag symptoms get a "see a doctor now" reply; signs of
disordered eating or self-harm get a supportive reply with a helpline. The model is not
asked for diet advice in those cases, so the outcome doesn't depend on the model.
The calorie floor is enforced separately in core/targets.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from spotonfit.config import SafetyPolicy, settings


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
