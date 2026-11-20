"""Store readiness: privacy page, password change, admin password reset."""

import asyncio
import importlib.util
from pathlib import Path

from spotonfit.config import settings
from tests.conftest import PASSWORD, register


def test_privacy_page_is_public_html(client, monkeypatch):
    r = client.get("/privacy")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    body = r.text
    for must in ("What SpotOn stores", "Google Gemini API", "Delete account", "18+", "the person who invited you"):
        assert must in body
    monkeypatch.setattr(settings, "privacy_contact", "help@example.com")
    assert 'href="mailto:help@example.com"' in client.get("/privacy").text


def test_change_password_signs_out_other_sessions(client, monkeypatch):
    monkeypatch.setattr(settings.limits, "login_per_minute", 50)  # many sign-ins in one test
    first = register(client, "pw@example.com")
    second = client.post("/v1/auth/login", json={"email": "pw@example.com", "password": PASSWORD}).json()
    h = {"Authorization": f"Bearer {first['access_token']}"}

    wrong = client.post("/v1/account/password", headers=h, json={"current_password": "nope", "new_password": "x" * 8})
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "invalid_credentials"
    short = client.post("/v1/account/password", headers=h, json={"current_password": PASSWORD, "new_password": "short"})
    assert short.status_code == 422

    r = client.post(
        "/v1/account/password", headers=h, json={"current_password": PASSWORD, "new_password": "brand-new-1"}
    )
    assert r.status_code == 200 and r.json()["refresh_token"]
    # the other device is signed out; the new password works, the old one doesn't
    assert client.post("/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401
    assert client.post("/v1/auth/refresh", json={"refresh_token": r.json()["refresh_token"]}).status_code == 200
    login = client.post("/v1/auth/login", json={"email": "pw@example.com", "password": "brand-new-1"})
    assert login.status_code == 200
    assert client.post("/v1/auth/login", json={"email": "pw@example.com", "password": PASSWORD}).status_code == 401


def _reset_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "reset_password.py"
    spec = importlib.util.spec_from_file_location("reset_password", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_admin_reset_gives_a_working_temporary_password(client, db, monkeypatch):
    monkeypatch.setattr(settings.limits, "login_per_minute", 50)
    tokens = register(client, "locked@example.com")
    temp = asyncio.run(_reset_module().reset(db, "Locked@Example.com"))
    assert len(temp) >= 8
    assert client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    login = client.post("/v1/auth/login", json={"email": "locked@example.com", "password": temp})
    assert login.status_code == 200


def test_admin_reset_unknown_email(client, db):  # client: creates the tables
    import pytest

    with pytest.raises(LookupError):
        asyncio.run(_reset_module().reset(db, "nobody@example.com"))
