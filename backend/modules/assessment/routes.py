"""Assessment routes (Q01, Q02, Q03)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import require_role, get_current_user_claims
from backend.core.errors import NotFoundError, ValidationError
from backend.models.curriculum import Topic
from backend.models.assessment import Question, Response
from backend.modules.assessment.service import submit_assessment, _build_stored_result
from backend.schemas.classroom import TeacherQuestion, TeacherQuestionOption
from backend.schemas.assessment import QuizSubmitRequest, QuizResult

router = APIRouter(prefix="/api", tags=["Assessment"])


@router.get("/questions", response_model=List[TeacherQuestion])
def get_questions(
    topic_id: Optional[int] = Query(None),
    purpose: Optional[str] = Query(None),
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """Q01: Return questions with full answer keys and misconception tags for teachers."""
    query = db.query(Question)
    if topic_id:
        query = query.filter(Question.topic_id == topic_id)
    if purpose:
        query = query.filter(Question.purpose == purpose)

    questions = query.order_by(Question.seq.asc()).all()
    results = []
    for q in questions:
        opts = [
            TeacherQuestionOption(
                id=opt.id,
                label=opt.label,
                text=opt.text,
                is_correct=opt.is_correct,
                misconception={"tag": opt.misconception.tag, "label": opt.misconception.label} if opt.misconception else None,
            )
            for opt in q.options
        ]
        results.append(
            TeacherQuestion(
                id=q.id,
                seq=q.seq,
                stem=q.stem,
                learning_outcome_id=q.learning_outcome_id,
                purpose=q.purpose,
                options=opts,
                explanation=q.explanation,
            )
        )
    return results


@router.post("/quiz/submit", response_model=QuizResult)
def submit_quiz(
    request: QuizSubmitRequest,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """Q02: Submit exit quiz or practice set responses with server-side correctness calculation."""
    student_id = claims.get("student_id")
    if not student_id:
        raise ValidationError("Missing student identity claim in token")
    return submit_assessment(request, int(student_id), db)


@router.get("/quiz/result", response_model=QuizResult)
def get_quiz_result(
    session_id: Optional[int] = Query(None),
    set_id: Optional[int] = Query(None),
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """Q03: Retrieve stored result of previously submitted quiz or practice set."""
    student_id = int(claims["student_id"])
    query = db.query(Response).filter(Response.student_id == student_id)
    context = "EXIT_QUIZ"
    if session_id:
        query = query.filter(Response.session_id == session_id, Response.context == "EXIT_QUIZ")
    elif set_id:
        context = "PRACTICE"
        query = query.filter(Response.practice_set_id == set_id, Response.context == "PRACTICE")
    else:
        raise ValidationError("Either session_id or set_id query parameter must be provided")

    responses = query.all()
    if not responses:
        raise NotFoundError("No stored assessment result found for this session/set")

    return _build_stored_result(student_id, responses, context, duplicate=False, db=db)
