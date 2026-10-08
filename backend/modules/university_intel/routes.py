"""University Intelligence routes (AD01-AD04)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import require_role, TokenPayload
from backend.schemas.intelligence import (
    AdminOverviewResponse,
    AdminGapItem,
    AdminAnalyticsResponse,
    AdminRecommendationRequest,
    AdminRecommendationResponse,
)
from backend.modules.university_intel.service import (
    get_admin_overview_service,
    get_admin_gaps_service,
    get_admin_analytics_service,
    generate_admin_recommendation_service,
)

router = APIRouter(prefix="/admin", tags=["University Intelligence"])


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    token: TokenPayload = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    """AD01: University institutional overview."""
    return get_admin_overview_service(db)


@router.get("/gaps", response_model=List[AdminGapItem])
def get_admin_gaps(
    token: TokenPayload = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    """AD02: Recurring learning gaps across sections."""
    return get_admin_gaps_service(db)


@router.get("/analytics", response_model=AdminAnalyticsResponse)
def get_admin_analytics(
    outcome_id: Optional[int] = Query(None),
    token: TokenPayload = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    """AD03: Institutional analytics comparison across sections and prerequisites."""
    return get_admin_analytics_service(outcome_id=outcome_id, db=db)


@router.post("/recommendations", response_model=AdminRecommendationResponse)
@router.post("/recommendation", response_model=AdminRecommendationResponse)
async def generate_admin_recommendation(
    payload: AdminRecommendationRequest,
    token: TokenPayload = Depends(require_role("ADMIN")),
    db: Session = Depends(get_db),
):
    """AD04: Generate institution-level academic curriculum recommendation."""
    return await generate_admin_recommendation_service(
        outcome_id=payload.outcome_id,
        admin_user_id=token.user_id,
        db=db,
    )
