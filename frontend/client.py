"""Thin HTTP client for the SpotOn API (the web client never touches the database).

- Tokens live in the Streamlit session (per browser tab); closing the tab logs out.
- When the 15-minute access token expires, the client rotates the refresh token once
  and retries the request; if that fails, the session is cleared (back to sign-in).
- API errors arrive as {"error": {"code", "message", "request_id"}} and are raised
  as `ApiError`.

Configuration: SPOTON_API_URL (default http://127.0.0.1:8000).
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator, MutableMapping
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("SPOTON_API_URL", "http://127.0.0.1:8000")
TIMEOUT_S = float(os.environ.get("SPOTON_API_TIMEOUT_S", "60"))  # photo analysis can take a while
TOKENS = "tokens"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, request_id: str | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.request_id = status, code, message, request_id


class SessionExpired(ApiError):
    pass


@st.cache_resource
def _shared_http() -> httpx.Client:
    return httpx.Client(base_url=API_URL, timeout=TIMEOUT_S)


class SpotOnClient:
    def __init__(self, http: httpx.Client, store: MutableMapping):
        self.http, self.store = http, store

    # --- session ------------------------------------------------------------------

    @property
    def logged_in(self) -> bool:
        return bool(self.store.get(TOKENS))

    def _set_tokens(self, tokens: dict | None) -> None:
        if tokens:
            self.store[TOKENS] = tokens
            self.store.pop("_session_expired", None)
        else:
            self.store.pop(TOKENS, None)

    def _auth_header(self) -> dict:
        tokens = self.store.get(TOKENS)
        return {"Authorization": f"Bearer {tokens['access_token']}"} if tokens else {}

    def _refresh(self) -> bool:
        tokens = self.store.get(TOKENS)
        if not tokens:
            return False
        r = self.http.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        if r.status_code != 200:
            self._set_tokens(None)
            return False
        self._set_tokens(r.json())
        return True

    @staticmethod
    def _raise(r: httpx.Response) -> None:
        try:
            err = r.json()["error"]
            raise ApiError(r.status_code, err.get("code", "error"), err.get("message", ""), err.get("request_id"))
        except ValueError, KeyError, TypeError:
            raise ApiError(r.status_code, "error", r.text[:200] or f"HTTP {r.status_code}") from None

    def request(self, method: str, path: str, *, auth: bool = True, **kwargs) -> httpx.Response:
        headers = {**kwargs.pop("headers", {}), **(self._auth_header() if auth else {})}
        r = self.http.request(method, path, headers=headers, **kwargs)
        if r.status_code == 401 and auth and self._refresh():
            headers.update(self._auth_header())
            r = self.http.request(method, path, headers=headers, **kwargs)
        if r.status_code == 401 and auth:
            self._set_tokens(None)
            raise SessionExpired(401, "session_expired", "Your session expired, please sign in again")
        if r.status_code >= 400:
            self._raise(r)
        return r

    def _json(self, method: str, path: str, **kwargs) -> Any:
        r = self.request(method, path, **kwargs)
        return None if r.status_code == 204 or not r.content else r.json()

    # --- auth ---------------------------------------------------------------------

    def register(self, email: str, password: str) -> None:
        self._set_tokens(
            self._json("POST", "/v1/auth/register", auth=False, json={"email": email, "password": password})
        )

    def login(self, email: str, password: str) -> None:
        self._set_tokens(self._json("POST", "/v1/auth/login", auth=False, json={"email": email, "password": password}))

    def logout(self) -> None:
        tokens = self.store.get(TOKENS)
        try:
            if tokens:
                self.request("POST", "/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        except ApiError:
            pass  # logging out locally is what matters
        finally:
            self._set_tokens(None)

    def me(self) -> dict:
        return self._json("GET", "/v1/me")

    # --- profile ------------------------------------------------------------------

    def profile(self) -> dict | None:
        try:
            return self._json("GET", "/v1/profile")
        except ApiError as e:
            if e.code == "profile_not_found":
                return None
            raise

    def save_profile(self, body: dict) -> dict:
        return self._json("PUT", "/v1/profile", json=body)

    # --- meals --------------------------------------------------------------------

    def analyze(self, note: str | None, image: tuple[str, bytes, str] | None) -> dict:
        data = {"note": note} if note else {}
        files = {"image": image} if image else None
        return self._json("POST", "/v1/meals/analyze", data=data, files=files)

    def save_meal(self, body: dict, idempotency_key: str | None = None) -> dict:
        key = idempotency_key or uuid.uuid4().hex
        return self._json("POST", "/v1/meals", json=body, headers={"Idempotency-Key": key})

    def meals(self, day: str | None = None) -> list[dict]:
        return self._json("GET", "/v1/meals", params={"date": day} if day else None)

    def recent_meals(self) -> list[dict]:
        return self._json("GET", "/v1/meals/recent")

    def favourite_meals(self) -> list[dict]:
        return self._json("GET", "/v1/meals/favourites")

    def edit_meal(self, meal_id: str, body: dict) -> dict:
        return self._json("PATCH", f"/v1/meals/{meal_id}", json=body)

    def repeat_meal(self, meal_id: str) -> dict:
        return self._json("POST", f"/v1/meals/{meal_id}/repeat")

    def delete_meal(self, meal_id: str) -> None:
        self._json("DELETE", f"/v1/meals/{meal_id}")

    # --- tracking -------------------------------------------------------------------

    def add_water(self, ml: int) -> None:
        self._json("POST", "/v1/water", json={"ml": ml})

    def set_steps(self, day: str, steps: int) -> None:
        self._json("PUT", f"/v1/steps/{day}", json={"steps": steps})

    def log_weight(self, kg: float) -> None:
        self._json("POST", "/v1/weights", json={"kg": kg})

    def log_workout(self, text: str) -> list[dict]:
        return self._json("POST", "/v1/workouts", json={"text": text})

    def today(self) -> dict:
        return self._json("GET", "/v1/today")

    def history(self, period: str, start: str | None = None, end: str | None = None) -> dict:
        params = {"period": period} | ({"from": start} if start else {}) | ({"to": end} if end else {})
        return self._json("GET", "/v1/history", params=params)

    # --- AI and data ----------------------------------------------------------------

    def suggestions(self, mode: str = "my_foods") -> dict:
        return self._json("GET", "/v1/suggestions", params={"mode": mode})

    def coach(self, message: str, thread_id: str | None = None) -> dict:
        return self._json("POST", "/v1/coach/messages", json={"message": message, "thread_id": thread_id})

    def coach_stream(self, message: str, thread_id: str | None = None) -> Iterator[tuple[str, dict]]:
        """Server-Sent Events from the coach: ("status"|"token"|"done"|"error", data)."""
        body = {"message": message, "thread_id": thread_id}
        for attempt in (1, 2):
            headers = {"Accept": "text/event-stream", **self._auth_header()}
            with self.http.stream("POST", "/v1/coach/messages", json=body, headers=headers) as r:
                if r.status_code == 401 and attempt == 1 and self._refresh():
                    continue
                if r.status_code == 401:
                    self._set_tokens(None)
                    raise SessionExpired(401, "session_expired", "Your session expired, please sign in again")
                if r.status_code >= 400:
                    r.read()
                    self._raise(r)
                event = None
                for line in r.iter_lines():
                    if line.startswith("event: "):
                        event = line[len("event: ") :]
                    elif line.startswith("data: ") and event:
                        yield event, json.loads(line[len("data: ") :])
                return

    def coach_thread(self, thread_id: str) -> list[dict]:
        return self._json("GET", f"/v1/coach/threads/{thread_id}")["messages"]

    # --- My Foods and rules -----------------------------------------------------------

    def my_foods(self) -> list[dict]:
        return self._json("GET", "/v1/my-foods")

    def save_my_foods(self, foods: list[dict]) -> list[dict]:
        return self._json("PUT", "/v1/my-foods", json=foods)

    def rules(self) -> list[dict]:
        return self._json("GET", "/v1/rules")

    def parse_rule(self, text: str) -> dict:
        return self._json("POST", "/v1/rules/parse", json={"text": text})

    def save_rule(self, rule: dict) -> dict:
        return self._json("POST", "/v1/rules", json=rule)

    def delete_rule(self, rule_id: str) -> None:
        self._json("DELETE", f"/v1/rules/{rule_id}")

    def food_memory(self) -> list[dict]:
        return self._json("GET", "/v1/food-memory")

    def forget_food(self, food_id: str) -> None:
        self._json("DELETE", f"/v1/food-memory/{food_id}")

    # --- Progress (Phase 3) --------------------------------------------------------------

    def progress(self) -> dict:
        return self._json("GET", "/v1/progress")

    def weekly_review(self) -> dict:
        return self._json("GET", "/v1/reviews/weekly")

    def decide_review(self, review_id: str, accept: bool) -> dict:
        return self._json(
            "POST", f"/v1/reviews/{review_id}/decision", json={"decision": "accept" if accept else "reject"}
        )

    def log_measurement(self, body: dict) -> dict:
        return self._json("POST", "/v1/measurements", json=body)

    def export(self, fmt: str) -> bytes:
        return self.request("GET", "/v1/export", params={"format": fmt}).content


def get_client() -> SpotOnClient:
    """Tests put a FastAPI TestClient in st.session_state["_http"]; the app uses a shared pool."""
    http = st.session_state.get("_http") or _shared_http()
    return SpotOnClient(http, st.session_state)
