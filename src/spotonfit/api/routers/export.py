"""GET /v1/export: download everything (PRD T-12). JSON, or a ZIP of CSV files."""

import datetime as dt
import json
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from spotonfit.api.deps import Session
from spotonfit.api.security import CurrentUser
from spotonfit.services.export import collect, to_zip

router = APIRouter(prefix="/v1", tags=["export"])


@router.get("/export", response_class=Response)
async def export(user: CurrentUser, session: Session, format: Literal["json", "csv"] = "json") -> Response:
    tables = await collect(session, user.id, user.email)
    stamp = dt.date.today().isoformat()
    if format == "csv":
        content, media, ext = to_zip(tables), "application/zip", "zip"
    else:
        content, media, ext = json.dumps(tables, indent=2, default=str).encode(), "application/json", "json"
    headers = {"Content-Disposition": f'attachment; filename="spoton-export-{stamp}.{ext}"'}
    return Response(content, media_type=media, headers=headers)
