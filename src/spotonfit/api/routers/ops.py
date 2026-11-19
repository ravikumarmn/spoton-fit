"""Liveness and readiness (PRD F-03). Public; used by deploy smoke tests."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from spotonfit import __version__
from spotonfit.config import settings

router = APIRouter(tags=["ops"])


@router.get("/healthz")
async def healthz() -> dict:
    """The process is up. Also shows which models are configured."""
    return {
        "status": "ok",
        "version": __version__,
        "llm_configured": settings.has_llm_key,
        "models": {
            "provider": settings.model_provider,
            "vision": settings.vision_model,
            "coach": settings.coach_model,
            "parser": settings.parser_model,
        },
    }


@router.get("/readyz")
async def readyz(request: Request):
    """Ready to serve: the database answers."""
    try:
        await request.app.state.db.ping()
    except Exception:
        return JSONResponse({"status": "unavailable", "database": "down"}, status.HTTP_503_SERVICE_UNAVAILABLE)
    return {"status": "ok", "database": "ok", "version": __version__}
