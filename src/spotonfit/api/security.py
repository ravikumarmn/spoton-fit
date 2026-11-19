"""Password hashing (Argon2id via pwdlib) and the `CurrentUser` dependency
(bearer access token -> active user, plus the general per-user rate limit).
Token creation/verification lives in services/auth.py."""

from __future__ import annotations

from functools import cache
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.api.deps import get_session
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import check
from spotonfit.config import settings
from spotonfit.db import User
from spotonfit.observability import bind_user
from spotonfit.services.auth import InvalidAccessToken, decode_access_token

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


@cache
def _dummy_hash() -> str:
    return password_hash.hash("timing-equaliser-not-a-real-password")


def verify_password(password: str, hashed: str | None) -> bool:
    """Constant-ish time: verifies against a dummy hash when the user doesn't exist,
    so response time doesn't reveal which emails are registered."""
    if hashed is None:
        password_hash.verify(password, _dummy_hash())
        return False
    return password_hash.verify(password, hashed)


def _unauthorized(message: str = "Invalid or expired token"):
    return api_error(status.HTTP_401_UNAUTHORIZED, "unauthorized", message, headers={"WWW-Authenticate": "Bearer"})


async def current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    try:
        user_id = decode_access_token(token)
    except InvalidAccessToken as e:
        raise _unauthorized() from e
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise _unauthorized("User not found or disabled")
    bind_user(user.id)
    check(request, f"user:{user.id}", settings.limits.general_per_minute, "Too many requests, slow down")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
