"""The web app (Flutter build) is served by the API at "/", and never shadows the API."""

from fastapi.testclient import TestClient

from spotonfit.api.main import create_app
from spotonfit.config import settings


def _client(monkeypatch, tmp_path, with_build: bool) -> TestClient:
    if with_build:
        (tmp_path / "index.html").write_text("<!doctype html><title>SpotOn</title>")
        (tmp_path / "manifest.json").write_text('{"name": "SpotOn"}')
    monkeypatch.setattr(settings, "web_dir", str(tmp_path))
    return TestClient(create_app())


def test_without_a_build_nothing_is_served(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, with_build=False) as c:
        assert c.get("/").status_code == 404
        assert c.get("/healthz").status_code == 200


def test_build_is_served_and_revalidated(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, with_build=True) as c:
        r = c.get("/")
        assert r.status_code == 200 and "SpotOn" in r.text
        assert r.headers["cache-control"] == "no-cache"
        assert c.get("/manifest.json").json() == {"name": "SpotOn"}


def test_api_routes_win_over_the_web_app(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, with_build=True) as c:
        assert c.get("/healthz").status_code == 200
        assert c.get("/privacy").headers["content-type"].startswith("text/html")
        assert "SpotOn privacy policy" in c.get("/privacy").text
        assert c.get("/openapi.json").status_code == 200
        # An unknown API path is still a 404, not the app's home page.
        assert c.get("/v1/nope").status_code == 404
        assert "<title>SpotOn</title>" not in c.get("/v1/nope").text
