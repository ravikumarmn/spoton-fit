"""Two meal options for what is left today (PRD C-02). Model-proposed, code-checked:
totals, calorie fit, My Foods only (my_foods mode) and your food rules."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status

from spotonfit.agents.models import LLMNotConfigured
from spotonfit.api.deps import Session, get_suggester
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import ai_limit
from spotonfit.api.routers.profile import profile_required
from spotonfit.api.schemas import SuggestionsOut
from spotonfit.api.security import CurrentUser
from spotonfit.services.suggestions import ProfileMissing, suggest_for_user

router = APIRouter(prefix="/v1", tags=["suggestions"])


@router.get("/suggestions", response_model=SuggestionsOut)
async def suggestions(
    user: CurrentUser,
    request: Request,
    session: Session,
    suggester: Annotated[object, Depends(get_suggester)],
    mode: Literal["my_foods", "ideal"] = "my_foods",
) -> dict:
    """mode=my_foods (default): only your available My Foods; mode=ideal: any food.
    Foods your rules block right now are never suggested."""
    ai_limit(request, user.id)
    try:
        return await suggest_for_user(session, user.id, suggester, mode)
    except ProfileMissing as e:
        raise profile_required() from e
    except LLMNotConfigured as e:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "ai_not_configured", str(e)) from e
    except Exception as e:
        raise api_error(status.HTTP_502_BAD_GATEWAY, "ai_failed", "Could not get suggestions, try again") from e
