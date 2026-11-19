"""Food-rule engine (PRD C-04). Pure functions: rules + what was eaten -> status.

Rule kinds (parsed from plain English by the model, confirmed by the user):
- max_days_per_week  "idli at most 3 days a week"   (calendar week; WEEK_STARTS_ON, default Sunday)
- max_per_day        "max 2 cups of tea a day"      (sum of quantities today)
- not_after          "no tea after 4 PM"
- not_before         "no coffee before 9 AM"
- avoid              "no sugar"

A rule matches a logged food when every word of the rule's food appears in the food's
name ("tea" matches "masala tea"; simple plurals ignored). Status per rule:
- ok / at_limit / broken, a gentle message, and `blocks_now`: whether eating the food
  now would break the rule. Suggestions drop blocked foods, so a rule used up today
  changes what is suggested next (including tomorrow, for weekly limits).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from spotonfit.config import settings

RuleKind = Literal["max_days_per_week", "max_per_day", "not_after", "not_before", "avoid"]
State = Literal["ok", "at_limit", "broken"]
NEEDS_LIMIT = {"max_days_per_week", "max_per_day"}
NEEDS_TIME = {"not_after", "not_before"}


@dataclass(frozen=True)
class Rule:
    id: str
    kind: RuleKind
    food: str
    limit: int | None = None
    time: dt.time | None = None


@dataclass(frozen=True)
class Eaten:
    at: dt.datetime  # local, timezone-aware
    name: str
    quantity: float = 1


@dataclass(frozen=True)
class RuleStatus:
    rule: Rule
    state: State
    used: float | None
    blocks_now: bool
    message: str


def validate(kind: str, limit: int | None, time: str | None) -> str | None:
    """Return a problem description, or None if the fields fit the kind."""
    if kind in NEEDS_LIMIT and (limit is None or limit < 0):
        return "this rule needs a number (how many)"
    if kind in NEEDS_TIME:
        if not time:
            return "this rule needs a time"
        try:
            dt.time.fromisoformat(time)
        except ValueError:
            return "the time must look like 16:00"
    return None


def _words(name: str) -> list[str]:
    out = []
    for w in name.lower().replace("-", " ").split():
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


def matches(food: str, item_name: str) -> bool:
    want, have = _words(food), set(_words(item_name))
    return bool(want) and all(w in have for w in want)


WEEKDAY = {"monday": 0, "sunday": 6}


def week_start(day: dt.date, starts_on: str | None = None) -> dt.date:
    """First day of the calendar week containing `day` (WEEK_STARTS_ON: monday | sunday)."""
    first = WEEKDAY[starts_on or settings.week_starts_on]
    return day - dt.timedelta(days=(day.weekday() - first) % 7)


def evaluate(
    rules: list[Rule], eaten: list[Eaten], now: dt.datetime, week_starts_on: str | None = None
) -> list[RuleStatus]:
    today, monday = now.date(), week_start(now.date(), week_starts_on)
    out = []
    for r in rules:
        hits = [e for e in eaten if matches(r.food, e.name)]
        today_hits = [e for e in hits if e.at.date() == today]
        food = r.food
        if r.kind == "max_days_per_week":
            days = {e.at.date() for e in hits if monday <= e.at.date() <= today}
            used, limit = len(days), r.limit or 0
            had_today = today in days
            if used > limit:
                st, msg = (
                    "broken",
                    f"{food.capitalize()} on {used} days this week (your limit is {limit}). "
                    "A new week is a fresh start.",
                )
            elif used == limit:
                st, msg = "at_limit", f"{food.capitalize()}: {used} of {limit} days used this week."
            else:
                st, msg = "ok", f"{food.capitalize()}: {used} of {limit} days used this week."
            out.append(RuleStatus(r, st, used, used >= limit and not had_today, msg))
        elif r.kind == "max_per_day":
            used, limit = sum(e.quantity for e in today_hits), r.limit or 0
            if used > limit:
                st, msg = (
                    "broken",
                    f"{food.capitalize()}: {used:g} today (your limit is {limit}). Tomorrow is a fresh start.",
                )
            elif used == limit:
                st, msg = "at_limit", f"{food.capitalize()}: {used:g} of {limit} today; that's your limit."
            else:
                st, msg = "ok", f"{food.capitalize()}: {used:g} of {limit} today."
            out.append(RuleStatus(r, st, used, used >= limit, msg))
        elif r.kind in ("not_after", "not_before"):
            after = r.kind == "not_after"
            t = r.time or dt.time.min
            outside = [e for e in today_hits if (e.at.time() >= t if after else e.at.time() < t)]
            blocks = now.time() >= t if after else now.time() < t
            when = f"after {t:%H:%M}" if after else f"before {t:%H:%M}"
            if outside:
                st, msg = "broken", f"You had {food} {when} today. No stress; tomorrow is a fresh start."
            else:
                st, msg = "ok", f"No {food} {when}." + (" That window is now." if blocks else "")
            out.append(RuleStatus(r, st, len(outside), blocks, msg))
        else:  # avoid
            if today_hits:
                st, msg = "broken", f"You had {food} today. It happens; back on track at the next meal."
            else:
                st, msg = "ok", f"Avoiding {food}."
            out.append(RuleStatus(r, st, len(today_hits), True, msg))
    return out


def nudges(statuses: list[RuleStatus]) -> list[str]:
    """Gentle messages for rules at their limit or broken (shown on Today)."""
    return [s.message for s in statuses if s.state != "ok"]


def blocked_foods(statuses: list[RuleStatus]) -> list[str]:
    return [s.rule.food for s in statuses if s.blocks_now]
