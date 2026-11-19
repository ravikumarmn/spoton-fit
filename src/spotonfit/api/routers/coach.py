"""Coach chat (PRD C-01, C-05, C-06). One conversation thread per user per local day.

POST /v1/coach/messages
  - `Accept: text/event-stream` -> Server-Sent Events, so the first words arrive quickly:
        event: status  data: {"tool": "get_today"}          (the coach is checking something)
        event: token   data: {"text": "Yes, "}               (repeated)
        event: done    data: {"reply": "...", "thread_id": "2026-11-19", "safety": null}
        event: error   data: {"code": "...", "message": "..."}
  - otherwise -> one JSON response (ChatOut).
  Safety routing runs first: red-flag symptoms or signs of disordered eating get a fixed,
  supportive reply without asking the model (agents/safety.py).
GET /v1/coach/threads/{thread_id}   the conversation so far (default thread id = today's date).
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from spotonfit.agents.coach import record_exchange, stream_reply, thread_config, thread_history, with_clock
from spotonfit.agents.models import LLMNotConfigured
from spotonfit.agents.safety import screen
from spotonfit.api.deps import get_coach_factory
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import ai_limit
from spotonfit.api.schemas import ChatIn, ChatOut, ThreadOut
from spotonfit.api.security import CurrentUser
from spotonfit.config import settings
from spotonfit.observability import hash_user
from spotonfit.services.ledger import local_today

router = APIRouter(prefix="/v1/coach", tags=["coach"])
log = logging.getLogger(__name__)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _agent(factory, user, request):
    try:
        return factory(user.id, request.app.state.db.sessionmaker)
    except LLMNotConfigured as e:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "ai_not_configured", str(e)) from e


@router.post("/messages", response_model=ChatOut)
async def send_message(
    body: ChatIn, user: CurrentUser, request: Request, factory: Annotated[object, Depends(get_coach_factory)]
):
    ai_limit(request, user.id)
    thread = body.thread_id or local_today().isoformat()
    config = thread_config(user.id, thread, hash_user(user.id))
    wants_stream = "text/event-stream" in request.headers.get("accept", "")
    route = screen(body.message)

    if route is not None:
        log.info("coach safety route: %s", route.kind)
        try:  # keep the thread complete when an agent can be built (needs an API key)
            await record_exchange(
                factory(user.id, request.app.state.db.sessionmaker), config, body.message, route.reply
            )
        except Exception:
            log.warning("could not store safety reply in the thread", exc_info=True)
        if wants_stream:
            done = {"reply": route.reply, "thread_id": thread, "safety": route.kind}

            async def safety_events() -> AsyncIterator[str]:
                yield sse("token", {"text": route.reply})
                yield sse("done", done)

            return StreamingResponse(safety_events(), media_type="text/event-stream")
        return ChatOut(reply=route.reply, thread_id=thread, safety=route.kind)

    agent = _agent(factory, user, request)

    if wants_stream:

        async def events() -> AsyncIterator[str]:
            try:
                async with asyncio.timeout(settings.coach_budget_s):
                    async for ev in stream_reply(agent, body.message, config):
                        name = ev.pop("event")
                        if name == "done":
                            ev.update(thread_id=thread, safety=None)
                        yield sse(name, ev)
            except TimeoutError:
                yield sse("error", {"code": "timeout", "message": "The coach took too long, please try again"})
            except Exception:
                log.exception("coach stream failed")
                yield sse("error", {"code": "ai_failed", "message": "Coach is unavailable, try again"})

        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        return StreamingResponse(events(), media_type="text/event-stream", headers=headers)

    try:
        async with asyncio.timeout(settings.coach_budget_s):
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": with_clock(body.message)}]}, config=config
            )
    except TimeoutError as e:
        raise api_error(status.HTTP_504_GATEWAY_TIMEOUT, "timeout", "The coach took too long, please try again") from e
    except Exception as e:
        log.exception("coach failed")
        raise api_error(status.HTTP_502_BAD_GATEWAY, "ai_failed", "Coach is unavailable, try again") from e
    return ChatOut(reply=result["messages"][-1].text, thread_id=thread)


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(
    thread_id: str, user: CurrentUser, request: Request, factory: Annotated[object, Depends(get_coach_factory)]
) -> ThreadOut:
    """The conversation in a thread (default thread id is the local date, e.g. 2026-11-19)."""
    if len(thread_id) > 64:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", "thread id too long")
    agent = _agent(factory, user, request)
    messages = await thread_history(agent, thread_config(user.id, thread_id, hash_user(user.id)))
    return ThreadOut(thread_id=thread_id, messages=messages)
