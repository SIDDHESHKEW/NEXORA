"""Auth and system routes (A01, A02, A03, SYS01, SYS02)."""

import json
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.db import get_db
from backend.core.security import get_current_user_claims
from backend.models.curriculum import User
from backend.models.governance import AuditLog, AppSetting
from backend.modules.auth.service import authenticate_demo_role
from backend.seed.seed_data import validate_seed_integrity
from backend.schemas.common import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    ConfigResponse,
    HealthResponse,
)

router = APIRouter(prefix="/api", tags=["Auth & System"])


@router.post("/auth/demo-login", response_model=TokenResponse)
def demo_login(request: LoginRequest, db: Session = Depends(get_db)):
    """A01: Demo role selection login."""
    return authenticate_demo_role(request.role, db)


@router.get("/auth/me", response_model=UserResponse)
def get_me(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """A02: Retrieve currently authenticated user."""
    user_id = int(claims["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    student_id = user.student.id if user.student else None
    teacher_id = user.teacher.id if user.teacher else None
    section_id = user.student.section_id if user.student else None

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        student_id=student_id,
        teacher_id=teacher_id,
        section_id=section_id,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """A03: Logout current session, recording audit log."""
    user_id = int(claims["sub"])
    role = claims.get("role")
    audit = AuditLog(
        action="LOGOUT",
        user_id=user_id,
        role=role,
        entity="USER",
        entity_id=user_id,
    )
    db.add(audit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/config", response_model=ConfigResponse)
def get_config(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """SYS01: Retrieve platform configuration, thresholds, and labels."""
    strong_setting = db.query(AppSetting).filter(AppSetting.key == "mastery_strong").first()
    dev_setting = db.query(AppSetting).filter(AppSetting.key == "mastery_developing").first()
    labels_setting = db.query(AppSetting).filter(AppSetting.key == "status_labels").first()

    strong_val = int(strong_setting.value) if strong_setting else settings.MASTERY_STRONG
    dev_val = int(dev_setting.value) if dev_setting else settings.MASTERY_DEVELOPING
    labels_val = json.loads(labels_setting.value) if labels_setting else {
        "student": {"STRONG": "Strong", "DEVELOPING": "Developing", "WEAK": "Needs Attention"},
        "staff": {"STRONG": "Strong", "DEVELOPING": "Developing", "WEAK": "Weak"},
    }

    return ConfigResponse(
        thresholds={"strong": strong_val, "developing": dev_val},
        status_labels=labels_val,
        demo={
            "allow_audience_join": settings.ALLOW_AUDIENCE_JOIN,
            "ai_mode": "LIVE" if not settings.AI_FORCE_FALLBACK and (settings.GEMINI_API_KEY_1 or settings.GROK_API_KEY) else "FALLBACK_ONLY",
        },
        university="Scope Global Skills University (SGSU)",
    )


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """SYS02: System health and seed data integrity check."""
    from backend.services.ai_gateway import ai_gateway
    ai_status = "configured" if (ai_gateway.gemini_provider.has_keys() or ai_gateway.grok_provider.has_keys()) and not settings.AI_FORCE_FALLBACK else "fallback"
    seed_health = validate_seed_integrity(db)

    return HealthResponse(
        status="ok",
        db=True,
        ai=ai_status,
        seed_health=seed_health,
    )
