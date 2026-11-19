"""Coach chat built with Deep Agents (LangChain + LangGraph harness).

The coach answers ONLY from async tool results over the user's own data:
- Tools are closures over `user_id`, so the model can never choose whose data to read.
- Food numbers come from the food-estimation graph (structured per-unit estimate x
  quantity, computed in code), never from free-form chat text.
- The system prompt is static (cache-friendly). The current local time is sent with
  every user message (`with_clock`), so a long-lived agent never uses a stale clock.
- Conversations persist in the checkpointer (agents/checkpoint.py), one thread per day.
- Safety routing happens before the model (agents/safety.py); `record_exchange` writes
  such fixed replies into the thread so history stays complete.
- `stream_reply` yields Server-Sent-Event-ready events (status, token, done).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from sqlalchemy.ext.asyncio import async_sessionmaker

from spotonfit.agents.suggester import Suggester
from spotonfit.config import settings
from spotonfit.core.trend import aggregate
from spotonfit.services.ledger import daily_frame, day_summary, get_profile, local_today
from spotonfit.services.my_foods import EFFORT_LABELS, list_my_foods
from spotonfit.services.progress import progress
from spotonfit.services.rules import statuses
from spotonfit.services.suggestions import ProfileMissing, suggest_for_user

SYSTEM_PROMPT = """You are SpotOn, a practical personal trainer and nutrition coach
for an Indian user. Each user message starts with the user's current local date and time
in square brackets; use it for anything time-related ("now", "tonight", "after 4 PM").

How you work:
- ALWAYS call tools to get the user's real numbers before answering. Never guess totals.
- For any food's calories or protein, call estimate_food or simulate_add. Never state
  nutrition numbers that did not come from a tool.
- Answer short: a yes/no or direct answer first, then the numbers (kcal, protein left),
  then one practical swap or next step. Call out oily or fried food gently.
- For "what should I eat", call suggest_meal and present its options. It uses the user's
  My Foods by default; use mode "ideal" if they ask for any food or their list is empty.
- For questions about progress, maintenance or "when will I reach X kg", call get_progress.
  Predictions are always ranges, never promises.
- The user's food rules (get_rules) are their own choices: respect them, and mention gently
  when something would break one. Their My Foods (get_my_foods) are what they can get.

Safety:
- Never recommend eating below the calorie floor returned by get_targets.
- Never present supplements as mandatory.
- For chest pain, fainting, dizziness or other worrying symptoms, tell the user to see a doctor.
- No shaming language. If intake looks very low or weight loss very fast, respond with care.
"""

Estimator = Callable[[str], Awaitable[dict]]


def make_tools(
    user_id: uuid.UUID, sessionmaker: async_sessionmaker, estimate: Estimator, suggester: Suggester
) -> list[Callable]:
    async def get_today() -> str:
        """Today's totals so far (calories, protein, carbs, fat, water, steps, workouts) and what is left."""
        async with sessionmaker() as s:
            d = await day_summary(s, local_today(), user_id)
        return json.dumps(
            {
                "eaten": {
                    "kcal": round(d.kcal),
                    "protein_g": round(d.protein),
                    "carbs_g": round(d.carbs),
                    "fat_g": round(d.fat),
                    "water_ml": d.water_ml,
                },
                "steps": d.steps,
                "workout_kcal": d.workout_kcal,
                "left": d.left(),
            }
        )

    async def get_targets() -> str:
        """The user's daily targets, BMR, maintenance and the minimum safe calorie floor."""
        async with sessionmaker() as s:
            t = (await day_summary(s, local_today(), user_id)).targets
        return json.dumps(t.__dict__ if t else {"error": "profile not set up"})

    async def estimate_food(description: str) -> str:
        """Estimated calories, protein, carbs and fat for a food description, e.g. '2 boiled eggs'
        or 'one cup masala chai with sugar'. Includes oil level and warnings."""
        return json.dumps(await estimate(description))

    async def simulate_add(description: str) -> str:
        """What today's remaining calories and protein would be if the user ate this now."""
        est = await estimate(description)
        async with sessionmaker() as s:
            left = (await day_summary(s, local_today(), user_id)).left()
        t = est["totals"]
        return json.dumps(
            {
                "food": description,
                "adds_kcal": round(t["kcal"]),
                "adds_protein_g": round(t["protein"], 1),
                "kcal_left_after": round(left.get("kcal", 0) - t["kcal"]),
                "protein_left_after_g": round(left.get("protein_g", 0) - t["protein"]),
                "oily_items": [i["name"] for i in est["items"] if i["oil_level"] in settings.estimates.oily_levels],
            }
        )

    async def suggest_meal(mode: str = "my_foods") -> str:
        """Two meal options that fit the calories left today and help close the protein gap.
        mode: "my_foods" (only foods the user can get; default) or "ideal" (any food)."""
        async with sessionmaker() as s:
            try:
                return json.dumps(
                    await suggest_for_user(s, user_id, suggester, "ideal" if mode == "ideal" else "my_foods")
                )
            except ProfileMissing as e:
                return json.dumps({"error": str(e)})

    async def get_rules() -> str:
        """The user's food rules (e.g. 'idli at most 3 days a week') and today's status of each."""
        async with sessionmaker() as s:
            rows = await statuses(s, user_id)
        return json.dumps(
            [{"rule": r.summary, "state": st.state, "blocks_now": st.blocks_now, "note": st.message} for r, st in rows]
        )

    async def get_progress() -> str:
        """Trend weight, learned maintenance (with how it was worked out) and goal-date / 4-week predictions."""
        async with sessionmaker() as s:
            data = await progress(s, user_id)
        if data is None:
            return json.dumps({"error": "profile not set up"})
        w = data["weight"]
        return json.dumps(
            {
                "trend_kg": w["trend_kg"],
                "trend_change_4w_kg": w["trend_change_4w_kg"],
                "maintenance": {k: data["maintenance"][k] for k in ("active", "kcal", "explanation")},
                "goal_prediction": data["prediction"],
                "in_weeks": data["in_weeks"],
            },
            default=str,
        )

    async def get_my_foods() -> str:
        """Foods the user can actually get, with effort (no cooking, 5-minute prep, buy nearby, order in)."""
        async with sessionmaker() as s:
            foods = await list_my_foods(s, user_id, available_only=True)
        return json.dumps(
            [{"food": f.name, "effort": EFFORT_LABELS.get(f.effort, f.effort), "slots": f.slots} for f in foods]
        )

    async def get_history(period: str = "week", days: int = 30) -> str:
        """Averages over recent history. period: day | week | month | year; days: how far back."""
        end = local_today()
        async with sessionmaker() as s:
            df = aggregate(await daily_frame(s, end - dt.timedelta(days=days), end, user_id), period)
            prof = await get_profile(s, user_id)
        return json.dumps(
            {
                "current_weight_kg": prof.weight_kg if prof else None,
                "rows": df.tail(settings.coach_history_rows).astype(str).to_dict(orient="records"),
            }
        )

    return [
        get_today,
        get_targets,
        estimate_food,
        simulate_add,
        suggest_meal,
        get_rules,
        get_my_foods,
        get_progress,
        get_history,
    ]


def with_clock(message: str, now: dt.datetime | None = None) -> str:
    """Prefix a user message with the local date/time the coach should reason about."""
    now = now or dt.datetime.now(settings.tz)
    return f"[{now.strftime('%A %d %b %Y, %H:%M')}] {message}"


CLOCK_PREFIX = re.compile(r"^\[[^\]]*\]\s*")


def thread_config(user_id: uuid.UUID, thread: str, user_ref: str) -> dict:
    return {"configurable": {"thread_id": f"u{user_id}-{thread}"}, "tags": ["coach"], "metadata": {"user": user_ref}}


def visible_messages(messages: list) -> list[dict]:
    """User and assistant turns for display (tool calls/results hidden, clock prefix removed)."""
    out = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append({"role": "user", "content": CLOCK_PREFIX.sub("", m.text)})
        elif isinstance(m, AIMessage) and m.text and not m.tool_calls:
            out.append({"role": "assistant", "content": m.text})
    return out


async def thread_history(agent, config: dict) -> list[dict]:
    state = await agent.aget_state(config)
    return visible_messages(state.values.get("messages", [])) if state and state.values else []


async def record_exchange(agent, config: dict, user_text: str, reply: str) -> None:
    """Store a turn that didn't go through the model (safety routing) in the thread."""
    await agent.aupdate_state(config, {"messages": [HumanMessage(with_clock(user_text)), AIMessage(reply)]})


async def stream_reply(agent, message: str, config: dict) -> AsyncIterator[dict]:
    """Run one coach turn, yielding events: {"event": "status"|"token", ...} then "done"."""
    seen_tools: set[str] = set()
    async for chunk, meta in agent.astream(
        {"messages": [{"role": "user", "content": with_clock(message)}]}, config=config, stream_mode="messages"
    ):
        if meta.get("langgraph_node") != "model" or not isinstance(chunk, AIMessageChunk):
            continue
        for tc in chunk.tool_call_chunks or []:
            if tc.get("name") and tc["name"] not in seen_tools:
                seen_tools.add(tc["name"])
                yield {"event": "status", "tool": tc["name"]}
        if chunk.text:
            yield {"event": "token", "text": chunk.text}
    history = await agent.aget_state(config)
    final = history.values["messages"][-1].text if history and history.values.get("messages") else ""
    yield {"event": "done", "reply": final}


def build_coach(
    user_id: uuid.UUID,
    sessionmaker: async_sessionmaker,
    checkpointer,
    estimate: Estimator,
    suggester: Suggester,
    model=None,
):
    """Compile a coach agent bound to one user (about 35 ms; the API caches it per user)."""
    from spotonfit.agents.models import coach_model

    return create_deep_agent(
        model=model or coach_model(),
        tools=make_tools(user_id, sessionmaker, estimate, suggester),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        name="spotonfit_coach",
    )
