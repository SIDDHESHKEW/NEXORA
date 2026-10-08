"""Curriculum routes (C01, C02, C03, C04, C05, S01)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import get_current_user_claims, require_role
from backend.modules.curriculum.service import (
    list_courses,
    get_course_detail,
    get_topic_detail,
    list_learning_outcomes,
    list_sections,
    list_approved_sources,
)
from backend.schemas.curriculum import (
    CourseSchema,
    CourseDetailSchema,
    TopicDetailSchema,
    OutcomeSchema,
    SectionSummarySchema,
    SourceSchema,
)

router = APIRouter(prefix="/api", tags=["Curriculum"])


@router.get("/courses", response_model=List[CourseSchema])
def get_courses(
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """C01: List all courses with sections and topic counts."""
    return list_courses(db)


@router.get("/courses/{id}", response_model=CourseDetailSchema)
def get_course(
    id: int,
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """C02: Get course details and topics."""
    return get_course_detail(id, db)


@router.get("/topics/{id}", response_model=TopicDetailSchema)
def get_topic(
    id: int,
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """C03: Get topic with learning outcomes (LO1–4) and prerequisites (P1, P2)."""
    return get_topic_detail(id, db)


@router.get("/learning-outcomes", response_model=List[OutcomeSchema])
def get_learning_outcomes(
    topic_id: Optional[int] = Query(None),
    kind: Optional[str] = Query(None),
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """C04: List learning outcomes filtered by topic and kind."""
    return list_learning_outcomes(topic_id, kind, db)


@router.get("/sections", response_model=List[SectionSummarySchema])
def get_sections(
    course_id: Optional[int] = Query(None),
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """C05: List class sections for course."""
    return list_sections(course_id, db)


@router.get("/sources", response_model=List[SourceSchema])
def get_sources(
    topic_id: Optional[int] = Query(None),
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """S01: List approved curriculum sources (citation fields only, body_text excluded)."""
    return list_approved_sources(topic_id, db)
