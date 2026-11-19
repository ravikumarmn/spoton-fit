"""Logging, request tracing and LLM tracing.

- Logs: one JSON object per line on stdout with the request id (`X-Request-ID`;
  generated if the client doesn't send one) and a hashed user id (never the raw id).
- LangSmith: automatic for LangChain/LangGraph/Deep Agents calls when
  LANGSMITH_TRACING=true and LANGSMITH_API_KEY are set (in the env or `.env`).
- MLflow (optional): if MLFLOW_TRACKING_URI is set, LangChain/LangGraph calls are
  also traced via mlflow.langchain.autolog() (needs `uv sync --group evals`).
"""

from __future__ import annotations

import contextvars
import datetime as dt
import hashlib
import json
import logging
import os
import sys
import time
import uuid

from spotonfit.config import settings

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
user_ref: contextvars.ContextVar[str] = contextvars.ContextVar("user_ref", default="-")
log = logging.getLogger("spotonfit")


def hash_user(user_id: object) -> str:
    """Stable, non-reversible user reference for logs and traces."""
    return hashlib.sha256(f"spotonfit:{user_id}".encode()).hexdigest()[:12]


def bind_user(user_id: object) -> str:
    ref = hash_user(user_id)
    user_ref.set(ref)
    return ref


class JsonFormatter(logging.Formatter):
    """Serialise each record with json.dumps so quotes/newlines never break a line."""

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "t": dt.datetime.fromtimestamp(record.created, dt.UTC).isoformat(timespec="milliseconds"),
            "lvl": record.levelname,
            "rid": request_id.get(),
            "uid": user_ref.get(),
            "log": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level)
    logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)  # noisy at INFO


def setup_tracing() -> None:
    # LangSmith reads env vars; mirror values loaded from .env into the environment.
    if settings.langsmith_tracing and settings.langsmith_api_key and settings.langsmith_api_key.get_secret_value():
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key.get_secret_value())
        os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
        log.info("langsmith tracing enabled (project=%s)", os.environ["LANGSMITH_PROJECT"])
    if settings.mlflow_tracking_uri:
        try:
            import mlflow

            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            mlflow.set_experiment("spotonfit")
            mlflow.langchain.autolog()
            log.info("mlflow tracing enabled")
        except ImportError:
            log.warning("MLFLOW_TRACKING_URI set but mlflow is not installed (uv sync --group evals)")


def error_body(status: int, code: str, message: str, **extra) -> dict:
    """The API's error envelope (Technical PRD section 6)."""
    return {"error": {"code": code, "message": message, "request_id": request_id.get(), **extra}}


class RequestContextMiddleware:
    """Pure ASGI middleware (safe for streaming responses):
    request id in/out, one access-log line per request, and a JSON 500 for crashes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")[:64]
        rid = incoming or uuid.uuid4().hex[:12]
        rid_token = request_id.set(rid)
        user_token = user_ref.set("-")
        status = 500
        started = False
        t0 = time.perf_counter()

        async def send_with_id(message):
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", rid.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            log.exception("unhandled error %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            body = json.dumps(error_body(500, "internal_error", "Something went wrong, please try again")).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"application/json"), (b"x-request-id", rid.encode())],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            ms = (time.perf_counter() - t0) * 1000
            log.info("%s %s %s %.0fms", scope.get("method"), scope.get("path"), status, ms)
            user_ref.reset(user_token)
            request_id.reset(rid_token)
