"""My Foods (PRD C-03) and food rules (PRD C-04).

- GET/PUT /v1/my-foods                 the foods you can get (PUT replaces the list)
- POST /v1/rules/parse                 plain English -> rule, NOT saved (shown back for confirmation)
- POST /v1/rules                       save a confirmed rule
- GET /v1/rules · DELETE /v1/rules/{id} rules with today's status
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import delete, func, select

from spotonfit.agents.models import LLMNotConfigured
from spotonfit.api.deps import Session, get_rule_parser
from spotonfit.api.errors import api_error
from spotonfit.api.ratelimit import ai_limit
from spotonfit.api.schemas import MyFoodIn, MyFoodOut, RuleIn, RuleOut, RuleParseIn
from spotonfit.api.security import CurrentUser
from spotonfit.config import settings
from spotonfit.core.rules import validate
from spotonfit.db import FoodRule
from spotonfit.services.my_foods import list_my_foods, replace_my_foods
from spotonfit.services.rules import statuses

router = APIRouter(prefix="/v1", tags=["my foods and rules"])


@router.get("/my-foods", response_model=list[MyFoodOut])
async def get_my_foods(user: CurrentUser, session: Session) -> list:
    return await list_my_foods(session, user.id)


@router.put("/my-foods", response_model=list[MyFoodOut])
async def put_my_foods(body: list[MyFoodIn], user: CurrentUser, session: Session) -> list:
    if len(body) > settings.max_my_foods:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "too_many", f"At most {settings.max_my_foods} foods")
    return await replace_my_foods(session, user.id, body)


@router.post("/rules/parse", response_model=RuleOut)
async def parse_rule(
    body: RuleParseIn,
    user: CurrentUser,
    request: Request,
    parser: Annotated[object, Depends(get_rule_parser)],
) -> RuleOut:
    """Turn plain English into a rule and restate it. Nothing is saved: confirm with POST /v1/rules."""
    ai_limit(request, user.id)
    try:
        spec = await parser(body.text)
    except LLMNotConfigured as e:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "ai_not_configured", str(e)) from e
    except Exception as e:
        raise api_error(status.HTTP_502_BAD_GATEWAY, "ai_failed", "Couldn't read that rule, try again") from e
    problem = None if spec.understood else "not a food rule I can check"
    problem = problem or validate(spec.kind, spec.limit, spec.time)
    if problem:
        msg = f"Sorry, I couldn't turn that into a rule ({problem}). Try e.g. 'no tea after 4 PM'."
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "rule_not_understood", msg)
    return RuleOut(**spec.model_dump(exclude={"understood"}), original_text=body.text)


@router.post("/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(body: RuleIn, user: CurrentUser, session: Session) -> RuleOut:
    problem = validate(body.kind, body.limit, body.time)
    if problem:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_rule", problem)
    count = await session.scalar(select(func.count()).select_from(FoodRule).where(FoodRule.user_id == user.id))
    if count >= settings.max_rules:
        raise api_error(status.HTTP_422_UNPROCESSABLE_CONTENT, "too_many", f"At most {settings.max_rules} rules")
    row = FoodRule(user_id=user.id, **body.model_dump())
    session.add(row)
    await session.commit()
    return next(r for r in await list_rules(user, session) if r.id == row.id)


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(user: CurrentUser, session: Session) -> list[RuleOut]:
    return [
        RuleOut.model_validate(row).model_copy(
            update={"state": st.state, "blocks_now": st.blocks_now, "status": st.message}
        )
        for row, st in await statuses(session, user.id)
    ]


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, user: CurrentUser, session: Session) -> None:
    res = await session.execute(delete(FoodRule).where(FoodRule.id == rule_id, FoodRule.user_id == user.id))
    if res.rowcount == 0:
        raise api_error(status.HTTP_404_NOT_FOUND, "rule_not_found", "Rule not found")
    await session.commit()
