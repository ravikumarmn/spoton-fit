"""Chat model factory (LangChain `init_chat_model`; the provider is a config value).

Gemini 3.x notes (Google docs, Nov 2026):
- `temperature`, `top_p` and `top_k` are deprecated from Gemini 3.6 on: ignored today
  and rejected by future models, so we never send them. `thinking_level` is the knob
  for latency vs reasoning depth.
- gemini-3.8-flash supports thinking_level low | medium (default) | high; `minimal`
  returns an error. gemini-3.5-flash-lite supports minimal (default) | low | medium | high.
- Each call gets a timeout and retries (Technical PRD section 4: 20 s, 2 retries).
"""

from __future__ import annotations

import os
from functools import cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from spotonfit.config import settings


class LLMNotConfigured(RuntimeError):
    """No API key for the configured provider; AI endpoints answer 503 with this message."""


def _vertex_configured() -> bool:
    return os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}


@cache
def chat_model(name: str, thinking_level: str | None = None) -> BaseChatModel:
    kwargs: dict = {"timeout": settings.llm_timeout_s, "max_retries": settings.llm_max_retries}
    if settings.model_provider == "google_genai":
        if settings.llm_api_key:
            kwargs["api_key"] = settings.llm_api_key
        elif not _vertex_configured():
            raise LLMNotConfigured("AI is not configured: set GOOGLE_API_KEY in .env and restart the API")
        if thinking_level:
            kwargs["thinking_level"] = thinking_level
    return init_chat_model(name, model_provider=settings.model_provider, **kwargs)


def vision_model() -> BaseChatModel:
    """Food photo/text understanding (needs image input)."""
    return chat_model(settings.vision_model, settings.vision_thinking)


def parser_model() -> BaseChatModel:
    """Cheap structured extraction (workouts, later rules)."""
    return chat_model(settings.parser_model, settings.parser_thinking)


def coach_model() -> BaseChatModel:
    """Tool-calling coach."""
    return chat_model(settings.coach_model, settings.coach_thinking)
