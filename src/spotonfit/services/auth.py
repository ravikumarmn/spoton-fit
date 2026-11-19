"""Tokens and sessions (Technical PRD section 5, PRD F-02).

Access token: JWT, ACCESS_TOKEN_MINUTES (default 15) lifetime, claims sub (user
UUID), iat, exp, iss, aud, jti, scope; verified for signature, expiry, issuer, audience.

Refresh tokens (opaque, rotating):

- A refresh token is 256 random bits, given to the client once and stored only as
  its SHA-256 hash, so a database leak doesn't leak sessions.
- Login starts a token *family*. Each refresh revokes the presented token and issues
  a new pair in the same family (rotation).
- Presenting an already-revoked token means it was stolen or replayed: the whole
  family is revoked and the user must log in again (reuse detection).
- Logout revokes the family; the short-lived access token expires on its own.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from spotonfit.config import settings
from spotonfit.db import RefreshToken, User, utcnow

TOKEN_BYTES = 32  # 256 bits


class InvalidRefreshToken(Exception):
    pass


class InvalidAccessToken(Exception):
    pass


def create_access_token(user_id: uuid.UUID) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": uuid.uuid4().hex,
        "scope": "user",
    }
    return jwt.encode(payload, settings.jwt_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    """Verify signature, expiry, issuer and audience; return the user id."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud", "jti"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as e:
        raise InvalidAccessToken(str(e)) from e


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_tokens(
    session: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID | None = None, user_agent: str | None = None
) -> dict:
    """Create an access token and a new refresh token (stored hashed). Caller commits."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw),
            family_id=family_id or uuid.uuid4(),
            expires_at=utcnow() + dt.timedelta(days=settings.refresh_token_days),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": raw,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
    }


async def revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def rotate(session: AsyncSession, raw: str, user_agent: str | None = None) -> dict:
    """Exchange a refresh token for a new pair. Commits."""
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    if row is None:
        raise InvalidRefreshToken("Unknown refresh token")
    if row.revoked_at is not None:
        await revoke_family(session, row.family_id)  # reuse of a rotated token
        await session.commit()
        raise InvalidRefreshToken("Refresh token reused; please log in again")
    if row.expires_at <= utcnow():
        raise InvalidRefreshToken("Refresh token expired; please log in again")
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshToken("User not found or disabled")
    # Conditional update: if two requests race with the same token, only one wins.
    res = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if res.rowcount != 1:
        await revoke_family(session, row.family_id)
        await session.commit()
        raise InvalidRefreshToken("Refresh token reused; please log in again")
    pair = await issue_tokens(session, user.id, row.family_id, user_agent)
    await session.commit()
    return pair


async def logout(session: AsyncSession, raw: str, user_id: uuid.UUID) -> None:
    """Revoke the session (token family) the refresh token belongs to. Commits."""
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw), RefreshToken.user_id == user_id)
    )
    if row is not None:
        await revoke_family(session, row.family_id)
        await session.commit()
