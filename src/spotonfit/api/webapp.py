"""Serves the SpotOn web app (the Flutter app built for the browser) from the API itself.

One address then works for everyone: Android and iPhone users open it, and on an iPhone use
Share > Add to Home Screen to get the app icon. The app is on the same origin as the API, so
there is no CORS to configure. The build is copied to ``WEB_DIR`` (default ``webapp/``) by the
deploy pipeline; when that folder has no ``index.html`` (local development, tests) nothing is
mounted and the API behaves exactly as before.
"""

from pathlib import Path

from fastapi import FastAPI
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class WebAppFiles(StaticFiles):
    """Static files that browsers re-check on every load (a cheap 304 when unchanged).

    Flutter's build files have fixed names, so letting browsers cache them would keep people on
    an old version after a deploy.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_webapp(app: FastAPI, directory: str) -> bool:
    """Mount the web build at ``/`` (after the API routes, so they win). True if mounted."""
    root = Path(directory)
    if not (root / "index.html").is_file():
        return False
    app.mount("/", WebAppFiles(directory=root, html=True), name="webapp")
    return True
