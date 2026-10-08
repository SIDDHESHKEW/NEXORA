"""Assessment service: handles secure server-side evaluated quiz and practice submissions."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.core.errors import (
    QuizNotOpenError,
    ValidationError,
    NotFoundError,
    ForbiddenScopeError,
)
from backend.models.curriculum import Student, LearningOutcome
from backend.models.classroom import ClassSession, SessionParticipant
from backend.models.assessment import Question, QuestionOption, Response
from backend.models.recommendation import PracticeSet, PracticeSetQuestion
from backend.models.learner import Mastery
from backend.modules.evidence.service import create_learning_event_for_response
from backend.modules.learner.service import recompute_mastery
from backend.modules.recommend.service import refresh_recommendations_for_student, refresh_recommendations_for_section
from backend.modules.skills.service import update_derived_skills
from backend.schemas.curriculum import OutcomeSchema
from backend.schemas.assessment import (
    QuizSubmitRequest,
    QuizResult,
    QuizResultItem,
    MasteryItemSchema,
    GapItemSchema,
    ScoreSummary,
)

logger = logging.getLogger("sgsu.assessment")


def submit_assessment(
    request: QuizSubmitRequest,
    student_id: int,
    db: Session,
    scripted: bool = False,
) -> QuizResult:
    """Execute complete, atomic assessment submission with server-side correctness evaluation."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError("Student record not found")

    # 1. Idempotency Check: check if already submitted with this idempotency key
    existing_responses = db.query(Response).filter(
        Response.student_id == student_id,
        Response.idempotency_key == request.idempotency_key,
    ).all()

    if existing_responses:
        logger.info(f"Duplicate submission detected for student {student_id} with key {request.idempotency_key}")
        return _build_stored_result(student_id, existing_responses, request.context, duplicate=True, db=db, scripted=scripted)

    # 2. Context-specific validation
    session: Optional[ClassSession] = None
    practice_set: Optional[PracticeSet] = None

    if request.context == "EXIT_QUIZ":
        if not request.session_id:
            raise ValidationError("session_id required for EXIT_QUIZ submission")
        session = db.query(ClassSession).filter(ClassSession.id == request.session_id).first()
        if not session:
            raise NotFoundError(f"Classroom session {request.session_id} not found")
        if session.quiz_status != "OPEN":
            raise QuizNotOpenError("Exit quiz is not currently open")

        # Check participant
        participant = db.query(SessionParticipant).filter(
            SessionParticipant.session_id == session.id,
            SessionParticipant.student_id == student_id,
        ).first()
        if not participant:
            # Auto-join if permitted
            from backend.models.curriculum import User
            u = db.query(User).filter(User.id == student.user_id).first()
            participant = SessionParticipant(
                session_id=session.id,
                student_id=student_id,
                display_name=u.name if u else "Student",
            )
            db.add(participant)
            db.flush()

        # Check if participant already submitted for this session
        prior_session_response = db.query(Response).filter(
            Response.student_id == student_id,
            Response.session_id == session.id,
            Response.context == "EXIT_QUIZ",
        ).first()
        if prior_session_response:
            logger.info("Student already submitted for this exit quiz session. Returning prior result.")
            all_session_resp = db.query(Response).filter(
                Response.student_id == student_id,
                Response.session_id == session.id,
                Response.context == "EXIT_QUIZ",
            ).all()
            return _build_stored_result(student_id, all_session_resp, request.context, duplicate=True, db=db, scripted=scripted)

    elif request.context == "PRACTICE":
        if not request.set_id:
            raise ValidationError("set_id required for PRACTICE submission")
        practice_set = db.query(PracticeSet).filter(PracticeSet.id == request.set_id).first()
        if not practice_set:
            raise NotFoundError(f"Practice set {request.set_id} not found")
        if practice_set.student_id != student_id:
            raise ForbiddenScopeError("Student does not own this practice set")

    # Snapshot mastery before
    mastery_before_rows = db.query(Mastery).filter(Mastery.student_id == student_id).all()
    mastery_before = [_to_mastery_schema(m, db) for m in mastery_before_rows]

    # 3. Validate answers and evaluate correctness on server
    if not request.answers:
        raise ValidationError("Answers list cannot be empty")

    evaluated_items: List[QuizResultItem] = []
    affected_outcome_ids = set()
    correct_count = 0
    total_count = len(request.answers)

    # Process each answer inside one transaction
    new_responses: List[Response] = []
    for ans in request.answers:
        q = db.query(Question).filter(Question.id == ans.question_id).first()
        if not q:
            raise ValidationError(f"Question ID {ans.question_id} not found")

        opt = db.query(QuestionOption).filter(
            QuestionOption.id == ans.option_id,
            QuestionOption.question_id == q.id,
        ).first()
        if not opt:
            raise ValidationError(f"Option ID {ans.option_id} does not belong to question {q.id}")

        # Server-evaluated correctness
        is_correct = bool(opt.is_correct)
        if is_correct:
            correct_count += 1

        correct_opt = db.query(QuestionOption).filter(
            QuestionOption.question_id == q.id,
            QuestionOption.is_correct == True,
        ).first()
        correct_option_id = correct_opt.id if correct_opt else opt.id

        resp = Response(
            student_id=student_id,
            question_id=q.id,
            option_id=opt.id,
            session_id=session.id if session else None,
            practice_set_id=practice_set.id if practice_set else None,
            context=request.context,
            is_correct=is_correct,
            duration_ms=ans.duration_ms,
            idempotency_key=request.idempotency_key,
        )
        db.add(resp)
        db.flush()
        new_responses.append(resp)

        # Create learning event
        create_learning_event_for_response(db, resp, is_seeded=False)
        affected_outcome_ids.add(q.learning_outcome_id)

        misc_info = None
        if opt.misconception:
            misc_info = {"tag": opt.misconception.tag, "label": opt.misconception.label}

        evaluated_items.append(
            QuizResultItem(
                question_id=q.id,
                learning_outcome_id=q.learning_outcome_id,
                selected_option_id=opt.id,
                correct_option_id=correct_option_id,
                is_correct=is_correct,
                explanation=q.explanation,
                misconception=misc_info,
            )
        )

    # If Exit Quiz, update participant timestamp and session version
    if session:
        participant = db.query(SessionParticipant).filter(
            SessionParticipant.session_id == session.id,
            SessionParticipant.student_id == student_id,
        ).first()
        if participant:
            from datetime import datetime, timezone
            participant.quiz_submitted_at = datetime.now(timezone.utc)
        session.version += 1

    # If Practice Set, mark completed
    if practice_set:
        practice_set.status = "COMPLETED"

    # 4. Recompute mastery
    updated_mastery = recompute_mastery(student_id, list(affected_outcome_ids), db)

    # 5. Update Derived Skills
    update_derived_skills(student_id, db)

    # 6. Evaluate Recommendations
    refresh_recommendations_for_student(student_id, db)
    if student.section_id:
        refresh_recommendations_for_section(student.section_id, db)

    db.commit()

    # Re-read full mastery for response
    all_mastery = db.query(Mastery).filter(Mastery.student_id == student_id).all()
    mastery_after = [_to_mastery_schema(m, db) for m in all_mastery]

    # Detect gaps for result
    gaps: List[GapItemSchema] = []
    for m in all_mastery:
        if m.status == "WEAK":
            lo = db.query(LearningOutcome).filter(LearningOutcome.id == m.learning_outcome_id).first()
            if lo:
                misc = lo.misconceptions[0] if lo.misconceptions else None
                misc_data = {"tag": misc.tag, "label": misc.label, "description": misc.description} if misc else None
                gaps.append(
                    GapItemSchema(
                        outcome_id=lo.id,
                        code=lo.code,
                        percent=m.percent,
                        status=m.status,
                        misconception=misc_data,
                    )
                )

    return QuizResult(
        duplicate=False,
        context=request.context,
        score=ScoreSummary(correct=correct_count, total=total_count),
        items=evaluated_items,
        mastery_before=mastery_before,
        mastery=mastery_after,
        gaps=gaps,
        provenance="LIVE",
        scripted=scripted,
    )


def _build_stored_result(
    student_id: int,
    responses: List[Response],
    context: str,
    duplicate: bool,
    db: Session,
    scripted: bool = False,
) -> QuizResult:
    evaluated_items = []
    correct_count = 0
    for resp in responses:
        if resp.is_correct:
            correct_count += 1
        q = resp.question
        correct_opt = db.query(QuestionOption).filter(
            QuestionOption.question_id == q.id,
            QuestionOption.is_correct == True,
        ).first()
        misc_info = None
        if resp.option and resp.option.misconception:
            misc_info = {"tag": resp.option.misconception.tag, "label": resp.option.misconception.label}

        evaluated_items.append(
            QuizResultItem(
                question_id=resp.question_id,
                learning_outcome_id=q.learning_outcome_id,
                selected_option_id=resp.option_id,
                correct_option_id=correct_opt.id if correct_opt else resp.option_id,
                is_correct=resp.is_correct,
                explanation=q.explanation,
                misconception=misc_info,
            )
        )

    all_mastery = db.query(Mastery).filter(Mastery.student_id == student_id).all()
    mastery_after = [_to_mastery_schema(m, db) for m in all_mastery]

    gaps = []
    for m in all_mastery:
        if m.status == "WEAK":
            lo = db.query(LearningOutcome).filter(LearningOutcome.id == m.learning_outcome_id).first()
            if lo:
                misc = lo.misconceptions[0] if lo.misconceptions else None
                misc_data = {"tag": misc.tag, "label": misc.label, "description": misc.description} if misc else None
                gaps.append(
                    GapItemSchema(
                        outcome_id=lo.id,
                        code=lo.code,
                        percent=m.percent,
                        status=m.status,
                        misconception=misc_data,
                    )
                )

    return QuizResult(
        duplicate=duplicate,
        context=context,
        score=ScoreSummary(correct=correct_count, total=len(responses)),
        items=evaluated_items,
        mastery=mastery_after,
        gaps=gaps,
        provenance="LIVE",
        scripted=scripted,
    )


def _to_mastery_schema(m: Mastery, db: Session) -> MasteryItemSchema:
    lo = db.query(LearningOutcome).filter(LearningOutcome.id == m.learning_outcome_id).first()
    lo_schema = OutcomeSchema(
        id=lo.id,
        code=lo.code,
        statement=lo.statement,
        kind=lo.kind,
        prerequisite_ids=[],
    )
    return MasteryItemSchema(
        outcome=lo_schema,
        percent=m.percent,
        estimate=m.estimate,
        status=m.status,
        evidence_count=m.evidence_count,
        prior_note="Pre-class diagnostic (sample)",
        provenance=m.provenance,
    )
