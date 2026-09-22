"""Natural-language questions over scoped analytics."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import require_roles, write_audit
from app.models import User
from app.services.assistant import ask_assistant

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


class AssistantTurn(BaseModel):
    role: str
    content: str


class AssistantAskIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[AssistantTurn] = Field(default_factory=list, max_length=8)
    mode: Literal["service", "onec"] = "service"


@router.post("/ask")
def assistant_ask(
    body: AssistantAskIn,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.ANALYTIC, UserRole.REGIONAL_DIRECTOR)
    ),
) -> dict:
    result = ask_assistant(
        db,
        user,
        body.message,
        [item.model_dump() for item in body.history],
        mode=body.mode,
    )
    write_audit(
        db,
        user_id=user.id,
        action="assistant_ask",
        details={"mode": body.mode, "tools": [item.get("name") for item in result.get("tools") or []]},
    )
    db.commit()
    return result
