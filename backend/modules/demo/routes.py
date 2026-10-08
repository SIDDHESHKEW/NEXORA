"""Demo routes (D01, D02, D03)."""

from typing import Optional
from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import require_role, get_current_user_optional, TokenPayload
from backend.schemas.assessment import QuizResult
from backend.schemas.intelligence import DemoResetResponse, DemoStateResponse
from backend.modules.demo.reset import execute_demo_reset
from backend.modules.demo.service import get_demo_state_service, autofill_quiz_service

router = APIRouter(prefix="/demo", tags=["Demo"])


class AutofillRequest(BaseModel):
    session_id: Optional[int] = None


@router.post("/reset", response_model=DemoResetResponse)
def post_demo_reset(
    token: TokenPayload = Depends(require_role(["TEACHER", "ADMIN"])),
    db: Session = Depends(get_db),
):
    """D01: Reset dynamic demonstrator state back to authoritative seed."""
    execute_demo_reset(db)
    return DemoResetResponse(reset=True, seed_version="v1.0-sgsu-demo")


@router.get("/state", response_model=DemoStateResponse)
def get_demo_state(
    db: Session = Depends(get_db),
):
    """D02: Derive intelligence loop progression state from database."""
    return get_demo_state_service(db)


@router.post("/autofill-quiz", response_model=QuizResult)
def post_autofill_quiz(
    payload: Optional[AutofillRequest] = Body(default=None),
    token: TokenPayload = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """D03: Scripted exit quiz autofill executing the exact server assessment pipeline."""
    session_id = payload.session_id if payload else None
    return autofill_quiz_service(
        student_id=token.student_id,
        session_id=session_id,
        db=db,
    )
