"""Email + password auth (PRD F-01, F-02).

- POST /v1/auth/register -> token pair (201)
- POST /v1/auth/login    -> token pair (JSON body: email, password)
- POST /v1/auth/token    -> token pair (OAuth2 form; used by the Swagger "Authorize" button)
- POST /v1/auth/refresh  -> new token pair; the old refresh token stops working
- POST /v1/auth/logout   -> revokes the session (token family)
- GET  /v1/me            -> the current user
- DELETE /v1/account     -> permanently deletes the account and all its data (needs the password)
Login, token and register are rate-limited per IP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from spotonfit.api.deps import Session
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import login_limit
from spotonfit.api.schemas import AccountDeleteIn, LoginIn, RefreshIn, TokenPair, UserCreate, UserOut
from spotonfit.api.security import CurrentUser, hash_password, verify_password
from spotonfit.config import settings
from spotonfit.db import User
from spotonfit.services.account import delete_chat_threads, delete_user_data
from spotonfit.services.auth import InvalidRefreshToken, issue_tokens, logout, rotate

router = APIRouter(prefix="/v1", tags=["auth"])
RateLimited = [Depends(login_limit)]


def _ua(request: Request) -> str | None:
    return request.headers.get("user-agent")


async def _login(session, request: Request, email: str, password: str) -> dict:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if not verify_password(password, user.password_hash if user else None) or not user.is_active:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Incorrect email or password")
    pair = await issue_tokens(session, user.id, user_agent=_ua(request))
    await session.commit()
    return pair


@router.post("/auth/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED, dependencies=RateLimited)
async def register(body: UserCreate, request: Request, session: Session) -> dict:
    if not settings.allow_registration:
        raise api_error(status.HTTP_403_FORBIDDEN, "registration_closed", "Registration is closed")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as e:
        await session.rollback()
        raise api_error(status.HTTP_409_CONFLICT, "email_taken", "Email already registered") from e
    pair = await issue_tokens(session, user.id, user_agent=_ua(request))
    await session.commit()
    return pair


@router.post("/auth/login", response_model=TokenPair, dependencies=RateLimited)
async def login(body: LoginIn, request: Request, session: Session) -> dict:
    return await _login(session, request, body.email, body.password)


@router.post("/auth/token", response_model=TokenPair, dependencies=RateLimited, include_in_schema=True)
async def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], request: Request, session: Session) -> dict:
    """Same as /auth/login but takes an OAuth2 form (username = email). Used by Swagger UI."""
    return await _login(session, request, form.username, form.password)


@router.post("/auth/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, request: Request, session: Session) -> dict:
    try:
        return await rotate(session, body.refresh_token, _ua(request))
    except InvalidRefreshToken as e:
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token", str(e)) from e


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_route(body: RefreshIn, user: CurrentUser, session: Session) -> None:
    await logout(session, body.refresh_token, user.id)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT, dependencies=RateLimited)
async def delete_account(body: AccountDeleteIn, request: Request, user: CurrentUser, session: Session) -> None:
    """Permanently delete the account and everything stored for it (PRD L-02). Cannot be undone."""
    if not verify_password(body.password, user.password_hash):
        raise api_error(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Incorrect password")
    user_id = user.id
    # Chats first: if that fails, nothing is deleted yet and the user can simply retry.
    await delete_chat_threads(request.app.state.checkpointer, user_id)
    await delete_user_data(session, user_id)
