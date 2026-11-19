"""Two meal options for what is left today (GET /v1/suggestions and the coach), PRD C-02.

Modes:
- my_foods (default): only the user's available My Foods. Falls back to `ideal` (and
  says so) when the list is empty.
- ideal: any common food.

The model proposes; code then:
- totals each option (quantity x per-unit; the user's food memory overrides estimates),
- drops options containing foods a rule blocks right now (core/rules.py),
- in my_foods mode, keeps only options built from My Foods when any exist,
- flags whether each option fits the calories left.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.agents.suggester import Suggester, finalize
from spotonfit.config import settings
from spotonfit.core.rules import blocked_foods, matches
from spotonfit.services import food_memory
from spotonfit.services.ledger import day_summary, get_profile, local_today
from spotonfit.services.my_foods import describe, list_my_foods
from spotonfit.services.rules import statuses

Mode = Literal["my_foods", "ideal"]


class ProfileMissing(LookupError):
    pass


def _is_my_food(item_name: str, my_names: list[str]) -> bool:
    return any(matches(m, item_name) or matches(item_name, m) for m in my_names)


async def suggest_for_user(
    session: AsyncSession, user_id: uuid.UUID, suggester: Suggester, mode: Mode = "my_foods"
) -> dict:
    profile = await get_profile(session, user_id)
    if profile is None:
        raise ProfileMissing("Set up your profile first")
    d = await day_summary(session, local_today(), user_id)
    left = d.left()
    mine = await list_my_foods(session, user_id, available_only=True)
    blocked = blocked_foods([s for _, s in await statuses(session, user_id)])
    effective: Mode = mode if (mode == "ideal" or mine) else "ideal"
    note = "Your My Foods list is empty, so these are general ideas." if mode == "my_foods" and not mine else None

    context = {
        "local time": dt.datetime.now(settings.tz).strftime("%A %H:%M"),
        "goal": str(profile.goal),
        "calories left today": left["kcal"],
        "protein left today (g)": left["protein_g"],
        "eaten so far (kcal / protein g)": f"{d.kcal:.0f} / {d.protein:.0f}",
    }
    if effective == "my_foods":
        context["use ONLY these foods (the user can get them)"] = describe(mine)
    if blocked:
        context["do NOT suggest (the user's own rules)"] = ", ".join(blocked)

    options = finalize(await suggester(context), left["kcal"], await food_memory.load(session, user_id))
    options = [o for o in options if not any(matches(b, i["name"]) for b in blocked for i in o["items"])]
    if effective == "my_foods":
        names = [f.name for f in mine]
        for o in options:
            o["only_my_foods"] = all(_is_my_food(i["name"], names) for i in o["items"])
        if any(o["only_my_foods"] for o in options):
            options = [o for o in options if o["only_my_foods"]]
        else:
            note = "Couldn't build an option only from My Foods; these include other foods."
    return {"mode": effective, "left": left, "options": options, "note": note}
