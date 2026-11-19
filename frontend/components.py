"""Shared UI pieces for the SpotOn web client."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

from client import ApiError, SessionExpired

SLOTS = ["breakfast", "snack", "lunch", "pre_workout", "dinner", "bedtime"]
OIL_LEVELS = ["none", "light", "medium", "heavy"]
NUTRIENTS = ["kcal", "protein", "carbs", "fat", "fibre"]


def show_error(e: Exception, quiet_codes: tuple[str, ...] = ()) -> None:
    """Show an API/network error in the page (session expiry returns to sign-in)."""
    if isinstance(e, SessionExpired):
        # Rerun once to land on the sign-in page; never loop if a page still runs signed out.
        if st.session_state.get("_session_expired"):
            st.stop()
        st.session_state["_session_expired"] = True
        st.warning(e.message)
        st.rerun()
    if isinstance(e, ApiError):
        if e.code in quiet_codes:
            return
        if e.code == "ai_not_configured":
            st.error("AI isn't set up on the server: add GOOGLE_API_KEY to the API's .env and restart it.")
        elif e.code == "rate_limited":
            st.warning(e.message)
        else:
            st.error(f"{e.message}" + (f"  \n`request id: {e.request_id}`" if e.request_id else ""))
        return
    st.error(f"Can't reach the SpotOn API ({type(e).__name__}). Is it running?")


def call(fn: Callable[..., Any], *args, quiet_codes: tuple[str, ...] = (), **kwargs) -> Any:
    """Run an API call; show errors in the page instead of crashing. Returns None on error."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        show_error(e, quiet_codes)
    return None


def today_id() -> str:
    """The coach's default thread id: today's date in the API's timezone."""
    return dt.datetime.now(user_tz()).date().isoformat()


def user_tz() -> ZoneInfo:
    """The API's timezone (from /v1/me), so times match the API's idea of 'today'."""
    if "tz" not in st.session_state:
        from client import get_client

        me = call(get_client().me)
        st.session_state["tz"] = (me or {}).get("timezone", "UTC")
    return ZoneInfo(st.session_state["tz"])


def local_time(iso: str) -> str:
    return dt.datetime.fromisoformat(iso).astimezone(user_tz()).strftime("%H:%M")


def need_profile_notice() -> None:
    st.info("Set up your profile first so SpotOn can work out your targets.")
    if st.button("Go to Profile", type="primary"):
        st.switch_page("pages/profile.py")


def progress_row(label: str, eaten: float, target: float, unit: str) -> None:
    """A labelled bar: eaten vs target. Over target shows full, with the overage in text."""
    target = max(target, 1)
    left = target - eaten
    text = f"**{label}** · {eaten:,.0f} / {target:,.0f} {unit}"
    text += f" · {left:,.0f} left" if left >= 0 else f" · {-left:,.0f} over"
    st.progress(min(max(eaten / target, 0.0), 1.0), text=text)


def item_line(item: dict) -> str:
    qty = f"{item['quantity']:g}"
    unit = f" {item['unit']}" if item.get("unit") and item["unit"] not in ("serving", "piece") else ""
    oily = " · 🛢️ oily" if item.get("oil_level") in ("medium", "heavy") else ""
    return f"{qty}{unit} × **{item['name']}** — {item['kcal']:.0f} kcal · {item['protein']:.1f} g protein{oily}"


def draft_rows(items: list[dict]) -> list[dict]:
    return [
        {
            "name": i["name"],
            "quantity": i["quantity"],
            "unit": i.get("unit") or "serving",
            **{f"{k}_per_unit": i["per_unit"][k] for k in NUTRIENTS},
            "oil_level": i.get("oil_level") or "none",
            "remark": i.get("remark") or "",
            "source": i.get("source", "ai_estimate"),
            "grams_per_unit": i.get("grams_per_unit"),
        }
        for i in items
    ]


def start_draft(draft: dict, source: str) -> None:
    st.session_state["draft"] = draft
    st.session_state["draft_rows"] = draft_rows(draft["items"])
    st.session_state["draft_key"] = uuid.uuid4().hex  # idempotency key + editor reset
    st.session_state["draft_source"] = source


def clear_draft() -> None:
    for k in ("draft", "draft_rows", "draft_key", "draft_source"):
        st.session_state.pop(k, None)


def totals_from_rows(rows: list[dict]) -> dict[str, float]:
    """Live preview of a draft's totals: Σ count × per-unit (the server recomputes on save)."""
    out = dict.fromkeys(NUTRIENTS, 0.0)
    for r in rows:
        qty = r.get("quantity") or 0
        for k in NUTRIENTS:
            out[k] += qty * (r.get(f"{k}_per_unit") or 0)
    return out


def macro_metrics(totals: dict[str, float]) -> None:
    c = st.columns(4)
    c[0].metric("Calories", f"{totals['kcal']:.0f}")
    c[1].metric("Protein", f"{totals['protein']:.1f} g")
    c[2].metric("Carbs", f"{totals['carbs']:.0f} g")
    c[3].metric("Fat", f"{totals['fat']:.0f} g")
