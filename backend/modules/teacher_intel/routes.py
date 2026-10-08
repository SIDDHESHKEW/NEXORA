"""Teacher Intelligence API routes (TI01 - TI05)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import require_role, assert_teacher_owns_section
from backend.core.ratelimit import rate_limit_ai
from backend.modules.teacher_intel.service import (
    get_teacher_dashboard_service,
    get_class_insights_service,
    get_class_evidence_service,
    get_class_recommendations_service,
    generate_reteach_service,
)
from backend.schemas.intelligence import (
    TeacherDashboardResponse,
    ClassInsightsResponse,
    ClassEvidenceResponse,
    TeacherRecommendationItem,
    ReteachRequest,
    ReteachSegment,
)

router = APIRouter(prefix="/api", tags=["Teacher Intelligence"])


@router.get("/teacher/dashboard", response_model=TeacherDashboardResponse)
def get_teacher_dashboard(
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """TI01: Teacher overview dashboard showing class mastery, weak LOs, and recommendations."""
    teacher_id = claims.get("teacher_id", 1)
    user_id = int(claims["sub"])
    return get_teacher_dashboard_service(teacher_id, user_id, db)


@router.get("/classes/{section_id}/insights", response_model=ClassInsightsResponse)
def get_class_insights(
    section_id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """TI02: Class mastery and weak-outcome analytics per section."""
    assert_teacher_owns_section(claims, section_id, db)
    return get_class_insights_service(section_id, db)


@router.get("/classes/{section_id}/evidence", response_model=ClassEvidenceResponse)
def get_class_evidence(
    section_id: int,
    outcome_id: Optional[int] = Query(None),
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """TI03: Class-level evidence drill-down with option distributions and top misconceptions."""
    assert_teacher_owns_section(claims, section_id, db)
    return get_class_evidence_service(section_id, outcome_id, db)


@router.get("/classes/{section_id}/recommendations", response_model=List[TeacherRecommendationItem])
def get_class_recommendations(
    section_id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """TI04: Pedagogical re-teach recommendations for section."""
    assert_teacher_owns_section(claims, section_id, db)
    return get_class_recommendations_service(section_id, db)


@router.post("/classes/{section_id}/reteach", response_model=ReteachSegment, dependencies=[Depends(rate_limit_ai)])
async def generate_reteach(
    section_id: int,
    req: ReteachRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """TI05: Generate structured 10-minute re-teach segment using AI Gateway."""
    assert_teacher_owns_section(claims, section_id, db)
    user_id = int(claims["sub"])
    return await generate_reteach_service(section_id, req.outcome_id, user_id, db)
