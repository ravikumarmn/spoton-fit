"""In-process rate limiting (Technical PRD section 5). Limits come from `config.LimitsPolicy`.

Sliding one-minute windows plus a per-user daily cap for AI calls. State is per
process, which is right for a single container; move it to Postgres/Redis before
running several replicas.
"""

from __future__ import annotations

import datetime as dt
import math
import time
from collections import deque

from fastapi import Request, status

from spotonfit.api.errors import api_error
from spotonfit.config import settings

WINDOW_S = 60.0


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._daily: dict[str, int] = {}
        self._day: dt.date | None = None

    def hit(self, key: str, limit: int, window_s: float = WINDOW_S) -> float | None:
        """Record a hit. Returns None if allowed, else seconds until the next slot."""
        now = time.monotonic()
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] >= window_s:
            q.popleft()
        if len(q) >= limit:
            return window_s - (now - q[0])
        q.append(now)
        if len(self._hits) > 10_000:  # drop idle keys so memory stays bounded
            self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < window_s}
        return None

    def hit_daily(self, key: str, limit: int, day: dt.date) -> bool:
        if day != self._day:
            self._day, self._daily = day, {}
        if self._daily.get(key, 0) >= limit:
            return False
        self._daily[key] = self._daily.get(key, 0) + 1
        return True


def _limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


def _too_many(retry_after: float, message: str):
    return api_error(
        status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", message, headers={"Retry-After": str(math.ceil(retry_after))}
    )


def check(request: Request, key: str, limit: int, message: str) -> None:
    wait = _limiter(request).hit(key, limit)
    if wait is not None:
        raise _too_many(wait, message)


async def login_limit(request: Request) -> None:
    """Per-IP limit on login/token/register (brute-force protection)."""
    ip = request.client.host if request.client else "unknown"
    check(request, f"login:{ip}", settings.limits.login_per_minute, "Too many attempts, wait a minute")


def ai_limit(request: Request, user_id: object) -> None:
    """Per-user per-minute limit and daily cap on endpoints that call the model."""
    check(request, f"ai:{user_id}", settings.limits.ai_per_minute, "Too many AI requests, wait a minute")
    today = dt.datetime.now(settings.tz).date()
    if not _limiter(request).hit_daily(f"ai:{user_id}", settings.limits.ai_per_day, today):
        tomorrow = dt.datetime.combine(today + dt.timedelta(days=1), dt.time.min, tzinfo=settings.tz)
        wait = (tomorrow - dt.datetime.now(settings.tz)).total_seconds()
        raise _too_many(wait, "Daily AI limit reached; it resets at midnight")
