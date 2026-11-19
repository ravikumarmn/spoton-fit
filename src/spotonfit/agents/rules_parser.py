"""Plain-English food rule -> RuleSpec (PRD C-04). The user confirms the restated rule
before it is saved; the rule engine (core/rules.py) then checks it in code."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from spotonfit.agents.schemas import RuleSpec

SYSTEM = (
    "Turn the user's food rule into structured fields. Examples: 'idli at most 3 days a week' -> "
    "max_days_per_week, food 'idli', limit 3. 'no tea after 4 PM' -> not_after, food 'tea', time '16:00'. "
    "'max 2 cups of coffee a day' -> max_per_day, food 'coffee', limit 2. 'no sugar' -> avoid, food 'sugar'. "
    "If it is not a rule about a food or drink, set understood to false."
)

RuleParser = Callable[[str], Awaitable[RuleSpec]]


def gemini_rule_parser(model=None) -> RuleParser:
    async def _parse(text: str) -> RuleSpec:
        from spotonfit.agents.models import parser_model

        llm = (model or parser_model()).with_structured_output(RuleSpec)
        return await llm.ainvoke([SystemMessage(SYSTEM), HumanMessage(text)])

    return _parse
