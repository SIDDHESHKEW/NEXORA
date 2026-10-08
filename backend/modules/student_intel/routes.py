"""Student Intelligence API routes (M01, M02, M03, SK01, PR01, PR02, PR04, T01)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import get_current_user_claims, require_role, assert_student_self
from backend.core.ratelimit import rate_limit_ai
from backend.modules.student_intel.service import (
    get_student_mastery_service,
    get_student_recommendations_service,
    get_student_evidence_service,
    generate_practice_service,
    get_practice_set_service,
    assign_practice_service,
    ask_tutor_service,
)
from backend.modules.skills.service import get_student_skills_passport
from backend.schemas.intelligence import (
    StudentMasteryResponse,
    StudentRecommendationResponse,
    StudentEvidenceItem,
    SkillPassportResponse,
    PracticeGenerateRequest,
    PracticeSetResponse,
    PracticeAssignRequest,
    PracticeAssignResponse,
    TutorAskRequest,
    TutorAskResponse,
)

router = APIRouter(prefix="/api", tags=["Student Intelligence"])


@router.get("/students/{id}/mastery", response_model=StudentMasteryResponse)
def get_student_mastery(
    id: int,
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """M01: Personal mastery levels per learning outcome."""
    assert_student_self(claims, id, db)
    return get_student_mastery_service(id, db)


@router.get("/students/{id}/recommendations", response_model=List[StudentRecommendationResponse])
def get_student_recommendations(
    id: int,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """M02: Learning gap recommendations for student."""
    assert_student_self(claims, id, db)
    return get_student_recommendations_service(id, db)


@router.get("/students/{id}/evidence", response_model=List[StudentEvidenceItem])
def get_student_evidence(
    id: int,
    outcome_id: Optional[int] = Query(None),
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """M03: Drill-down learning evidence from recent assessments."""
    assert_student_self(claims, id, db)
    return get_student_evidence_service(id, outcome_id, db)


@router.get("/students/{id}/skills", response_model=SkillPassportResponse)
def get_student_skills(
    id: int,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """SK01: Student Skill Passport data."""
    assert_student_self(claims, id, db)
    return get_student_skills_passport(id, db)


@router.post("/practice/generate", response_model=PracticeSetResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit_ai)])
async def generate_practice(
    req: PracticeGenerateRequest,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """PR01: Generate targeted practice questions using AI Gateway."""
    student_id = int(claims["student_id"])
    return await generate_practice_service(req.outcome_id, student_id, db)


@router.get("/practice/{set_id}", response_model=PracticeSetResponse)
def get_practice_set(
    set_id: int,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """PR02: Retrieve generated practice question set."""
    student_id = int(claims["student_id"])
    return get_practice_set_service(set_id, student_id, db)


@router.post("/practice/assign", response_model=PracticeAssignResponse)
def assign_practice(
    req: PracticeAssignRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """PR04: Teacher assigns practice set to weak cohort students."""
    teacher_user_id = int(claims["sub"])
    assigned_count = assign_practice_service(req.section_id, req.outcome_id, teacher_user_id, db)
    return PracticeAssignResponse(assigned_count=assigned_count)


@router.post("/tutor/ask", response_model=TutorAskResponse, dependencies=[Depends(rate_limit_ai)])
async def ask_tutor(
    req: TutorAskRequest,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """T01: Ask grounded course tutor (locked during open exit quiz)."""
    student_id = int(claims["student_id"])
    user_id = int(claims["sub"])
    return await ask_tutor_service(req.question, req.outcome_id, student_id, user_id, db)
