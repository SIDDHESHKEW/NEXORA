"""Governance routes (G01, G02)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import require_role, TokenPayload
from backend.schemas.intelligence import GovernancePolicyResponse, GovernanceLogsResponse
from backend.modules.governance.service import (
    get_governance_policy_service,
    get_governance_logs_service,
)

router = APIRouter(prefix="/governance", tags=["Governance"])


@router.get("/policy", response_model=GovernancePolicyResponse)
def get_governance_policy(db: Session = Depends(get_db)):
    """G01: View AI usage and governance policy."""
    return get_governance_policy_service(db)


@router.get("/logs", response_model=GovernanceLogsResponse)
def get_governance_logs(
    limit: int = Query(100, ge=1, le=500),
    token: TokenPayload = Depends(require_role(["ADMIN", "TEACHER"])),
    db: Session = Depends(get_db),
):
    """G02: View AI interactions and system audit logs."""
    return get_governance_logs_service(db, limit=limit)
