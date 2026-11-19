"""Error envelope for every API error (Technical PRD section 6):

    {"error": {"code": "not_found", "message": "Meal not found", "request_id": "..."}}

Raise `api_error(status, code, message)` for a specific machine-readable code;
a plain `HTTPException` gets a code derived from its status.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from spotonfit.observability import error_body

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    502: "upstream_error",
    503: "unavailable",
    504: "timeout",
}


def api_error(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message}, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            code, message = exc.detail["code"], exc.detail.get("message", "")
        else:
            code, message = STATUS_CODES.get(exc.status_code, "error"), str(exc.detail)
        return JSONResponse(error_body(exc.status_code, code, message), exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{k: v for k, v in e.items() if k in {"loc", "msg", "type"}} for e in exc.errors()]
        # Readable summary, e.g. "password: String should have at least 8 characters"
        parts = [f"{e['loc'][-1]}: {e['msg']}" if e.get("loc") else e["msg"] for e in details[:3]]
        message = "; ".join(parts) or "Invalid request"
        body = error_body(422, "validation_error", message, details=jsonable_encoder(details))
        return JSONResponse(body, 422)
