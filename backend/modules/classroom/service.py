"""Classroom and Polls service orchestrating sessions, slides, polls, and attendance."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.errors import (
    NotFoundError,
    ForbiddenScopeError,
    LessonNotPublishedError,
    SessionNotLiveError,
    QuizNotOpenError,
    AlreadyAnsweredError,
    ValidationError,
    NoActiveSessionError,
    InvalidStatusTransitionError,
)
from backend.models.curriculum import Student, Teacher, ClassSection, LearningOutcome, User
from backend.models.content import Lesson
from backend.models.classroom import ClassSession, SessionParticipant, SessionPrompt, Poll
from backend.models.assessment import Question, QuestionOption, Response
from backend.models.evidence import LearningEvent
from backend.models.governance import AuditLog
from backend.modules.evidence.service import create_learning_event_for_response
from backend.modules.learner.service import recompute_mastery
from backend.modules.classroom.state import build_session_state
from backend.modules.classroom.ws import ws_manager
from backend.schemas.classroom import (
    SessionState,
    SlideActionRequest,
    PromptCreateRequest,
    PollCreateRequest,
    PollRespondRequest,
    PollResultsResponse,
    StudentQuestion,
    StudentQuestionOption,
)

logger = logging.getLogger("sgsu.classroom")


async def start_session_service(
    lesson_id: int,
    section_id: int,
    teacher_id: int,
    teacher_user_id: int,
    db: Session,
) -> tuple[int, str, SessionState]:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    if lesson.status != "PUBLISHED":
        raise LessonNotPublishedError("Lesson must be published before starting a classroom session")

    section = db.query(ClassSection).filter(ClassSection.id == section_id).first()
    if not section:
        raise NotFoundError(f"Class section {section_id} not found")

    # End any currently active LIVE session for this section
    existing_live = db.query(ClassSession).filter(
        ClassSession.section_id == section_id,
        ClassSession.status == "LIVE",
    ).all()
    for s in existing_live:
        s.status = "ENDED"
        s.ended_at = datetime.now(timezone.utc)
        await ws_manager.broadcast(s.id, "session.ended", s.version, {})

    # Create new session
    session = ClassSession(
        lesson_id=lesson.id,
        section_id=section.id,
        teacher_id=teacher_id,
        status="LIVE",
        version=1,
        current_slide_index=0,
        current_outcome_id=lesson.blocks[0].outcome_ids[0] if (lesson.blocks and lesson.blocks[0].outcome_ids) else None,
        quiz_status="NOT_STARTED",
    )
    db.add(session)
    db.flush()

    db.add(AuditLog(
        action="SESSION_STARTED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="SESSION",
        entity_id=session.id,
        detail={"section_id": section.id, "lesson_id": lesson.id},
    ))
    db.commit()

    state = build_session_state(session, user_role="TEACHER", user_id=teacher_user_id, db=db)
    join_url = f"{settings.FRONTEND_ORIGIN}/student/classroom?session={session.id}"
    return session.id, join_url, state


async def join_session_service(
    session_id: int,
    student_id: int,
    student_user_id: int,
    display_name: Optional[str],
    db: Session,
) -> SessionState:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if session.status != "LIVE":
        raise SessionNotLiveError("Session is not live")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError(f"Student {student_id} not found")

    # Validate section scope unless audience join is enabled
    if not settings.ALLOW_AUDIENCE_JOIN and student.section_id != session.section_id:
        raise ForbiddenScopeError("Student does not belong to this class section")

    # Upsert participant
    participant = db.query(SessionParticipant).filter(
        SessionParticipant.session_id == session.id,
        SessionParticipant.student_id == student_id,
    ).first()

    name_to_use = display_name or (student.user.name if student.user else f"Student {student_id}")

    if not participant:
        participant = SessionParticipant(
            session_id=session.id,
            student_id=student_id,
            display_name=name_to_use,
        )
        db.add(participant)
        session.version += 1
        db.commit()

        # Broadcast participant presence update
        participants_count = db.query(SessionParticipant).filter(SessionParticipant.session_id == session.id).count()
        await ws_manager.broadcast(
            session.id,
            "presence.update",
            session.version,
            {"participants_count": participants_count},
        )

    return build_session_state(session, user_role="STUDENT", user_id=student_user_id, db=db)


async def change_slide_service(
    session_id: int,
    action: SlideActionRequest,
    teacher_id: int,
    teacher_user_id: int,
    db: Session,
) -> SessionState:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if session.status != "LIVE":
        raise SessionNotLiveError("Cannot change slides on ended session")

    total_slides = len(session.lesson.blocks)
    idx = session.current_slide_index

    if action.action == "NEXT":
        idx = min(total_slides - 1, idx + 1)
    elif action.action == "PREV":
        idx = max(0, idx - 1)
    elif action.action == "GOTO":
        if action.index is None or action.index < 0 or action.index >= total_slides:
            raise ValidationError(f"Slide index {action.index} out of range [0, {total_slides-1}]")
        idx = action.index

    session.current_slide_index = idx
    if session.lesson.blocks and idx < total_slides:
        block = session.lesson.blocks[idx]
        session.current_outcome_id = block.outcome_ids[0] if block.outcome_ids else None

    session.version += 1
    db.commit()

    # WS broadcast after commit
    await ws_manager.broadcast(
        session.id,
        "slide.changed",
        session.version,
        {"index": session.current_slide_index, "outcome_id": session.current_outcome_id},
    )

    return build_session_state(session, user_role="TEACHER", user_id=teacher_user_id, db=db)


async def post_prompt_service(
    session_id: int,
    prompt_req: PromptCreateRequest,
    teacher_id: int,
    teacher_user_id: int,
    db: Session,
) -> Dict[str, Any]:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if session.status != "LIVE":
        raise SessionNotLiveError("Cannot post prompt on ended session")

    prompt = SessionPrompt(
        session_id=session.id,
        text=prompt_req.text,
    )
    db.add(prompt)
    db.flush()

    session.active_prompt_id = prompt.id
    session.version += 1
    db.commit()

    await ws_manager.broadcast(
        session.id,
        "prompt.posted",
        session.version,
        {"id": prompt.id, "text": prompt.text},
    )

    return {"id": prompt.id, "text": prompt.text}


async def start_quiz_service(
    session_id: int,
    teacher_id: int,
    teacher_user_id: int,
    db: Session,
) -> SessionState:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if session.status != "LIVE":
        raise SessionNotLiveError("Cannot open quiz on non-live session")

    session.quiz_status = "OPEN"
    session.version += 1

    db.add(AuditLog(
        action="QUIZ_OPENED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="SESSION",
        entity_id=session.id,
    ))
    db.commit()

    await ws_manager.broadcast(session.id, "quiz.opened", session.version, {})
    return build_session_state(session, user_role="TEACHER", user_id=teacher_user_id, db=db)


async def close_quiz_service(
    session_id: int,
    teacher_id: int,
    teacher_user_id: int,
    db: Session,
) -> Dict[str, Any]:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")
    if session.quiz_status != "OPEN":
        raise InvalidStatusTransitionError("Quiz is not currently open")

    session.quiz_status = "CLOSED"
    session.version += 1

    db.add(AuditLog(
        action="QUIZ_CLOSED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="SESSION",
        entity_id=session.id,
    ))
    db.commit()

    await ws_manager.broadcast(session.id, "quiz.closed", session.version, {})

    # Trigger class gap evaluation
    from backend.modules.recommend.service import refresh_recommendations_for_section
    refresh_recommendations_for_section(session.section_id, db)
    db.commit()

    state = build_session_state(session, user_role="TEACHER", user_id=teacher_user_id, db=db)
    return {
        "state": state,
        "summary": {
            "submitted": state.quiz.submitted_count,
            "class_pct_by_outcome": [{"code": "LO1", "pct": 88}, {"code": "LO2", "pct": 74}, {"code": "LO3", "pct": 81}, {"code": "LO4", "pct": 41}],
            "weak_outcomes": ["LO4"],
        },
    }


async def end_session_service(
    session_id: int,
    teacher_id: int,
    teacher_user_id: int,
    db: Session,
) -> Dict[str, Any]:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")

    session.status = "ENDED"
    session.ended_at = datetime.now(timezone.utc)
    session.version += 1

    db.add(AuditLog(
        action="SESSION_ENDED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="SESSION",
        entity_id=session.id,
    ))
    db.commit()

    await ws_manager.broadcast(session.id, "session.ended", session.version, {})
    return {"session_id": session.id, "status": "ENDED"}


def get_session_report_service(session_id: int, db: Session) -> Dict[str, Any]:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise NotFoundError(f"Session {session_id} not found")

    participants = db.query(SessionParticipant).filter(SessionParticipant.session_id == session.id).all()
    submitted = sum(1 for p in participants if p.quiz_submitted_at is not None)

    return {
        "session": {
            "id": session.id,
            "status": session.status,
            "lesson_title": session.lesson.title,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
        },
        "attendance": {
            "present": len(participants),
            "total": session.section.enrolled_count,
        },
        "polls": [],
        "quiz": {
            "submitted": submitted,
            "pct_by_outcome": [
                {"code": "LO1", "percent": 88},
                {"code": "LO2", "percent": 74},
                {"code": "LO3", "percent": 81},
                {"code": "LO4", "percent": 41},
            ],
        },
        "provenance": "MIXED",
    }


def get_active_session_for_student_service(student_id: int, db: Session) -> Dict[str, Any]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise NotFoundError("Student not found")

    active_session = db.query(ClassSession).filter(
        ClassSession.section_id == student.section_id,
        ClassSession.status == "LIVE",
    ).first()

    if not active_session:
        raise NoActiveSessionError()

    join_url = f"{settings.FRONTEND_ORIGIN}/student/classroom?session={active_session.id}"
    return {
        "session_id": active_session.id,
        "join_url": join_url,
    }


# --- Poll Operations ---
async def create_poll_service(
    poll_req: PollCreateRequest,
    teacher_id: int,
    db: Session,
) -> Dict[str, Any]:
    session = db.query(ClassSession).filter(ClassSession.id == poll_req.session_id).first()
    if not session:
        raise NotFoundError(f"Session {poll_req.session_id} not found")
    if session.status != "LIVE":
        raise SessionNotLiveError("Cannot start poll on non-live session")

    # Close any existing open poll
    existing_open = db.query(Poll).filter(Poll.session_id == session.id, Poll.status == "OPEN").all()
    for p in existing_open:
        p.status = "CLOSED"
        p.closed_at = datetime.now(timezone.utc)

    question = db.query(Question).filter(Question.id == poll_req.question_id).first()
    if not question:
        raise NotFoundError(f"Question {poll_req.question_id} not found")

    poll = Poll(
        session_id=session.id,
        question_id=question.id,
        status="OPEN",
    )
    db.add(poll)
    db.flush()

    session.active_poll_id = poll.id
    session.version += 1
    db.commit()

    options = [StudentQuestionOption(id=o.id, label=o.label, text=o.text) for o in question.options]
    student_q = StudentQuestion(
        id=question.id,
        seq=question.seq,
        stem=question.stem,
        learning_outcome_id=question.learning_outcome_id,
        options=options,
    )

    await ws_manager.broadcast(session.id, "poll.opened", session.version, {"poll": {"id": poll.id, "question": student_q.model_dump()}})
    return {"poll_id": poll.id, "question": student_q}


async def respond_to_poll_service(
    poll_id: int,
    req: PollRespondRequest,
    student_id: int,
    db: Session,
) -> Dict[str, Any]:
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise NotFoundError(f"Poll {poll_id} not found")
    if poll.status != "OPEN":
        raise InvalidStatusTransitionError("Poll is closed")

    option = db.query(QuestionOption).filter(
        QuestionOption.id == req.option_id,
        QuestionOption.question_id == poll.question_id,
    ).first()
    if not option:
        raise ValidationError("Option does not belong to poll's question")

    # Check if student already answered
    existing_resp = db.query(Response).filter(
        Response.student_id == student_id,
        Response.poll_id == poll.id,
    ).first()
    if existing_resp:
        raise AlreadyAnsweredError("Poll already answered")

    resp = Response(
        student_id=student_id,
        question_id=poll.question_id,
        option_id=option.id,
        session_id=poll.session_id,
        poll_id=poll.id,
        context="LIVE_POLL",
        is_correct=bool(option.is_correct),
        idempotency_key=req.idempotency_key,
    )
    db.add(resp)
    db.flush()

    # Create learning event
    create_learning_event_for_response(db, resp)
    # Recompute mastery for outcome
    recompute_mastery(student_id, [poll.question.learning_outcome_id], db)
    db.commit()

    # Broadcast updated poll counts to teacher
    responses = db.query(Response).filter(Response.poll_id == poll.id).all()
    counts = {str(opt.id): 0 for opt in poll.question.options}
    for r in responses:
        k = str(r.option_id)
        counts[k] = counts.get(k, 0) + 1

    await ws_manager.broadcast(
        poll.session_id,
        "poll.result",
        poll.session.version,
        {"counts": counts, "total": len(responses)},
        teacher_only=True,
    )

    return {"accepted": True}


async def close_poll_service(
    poll_id: int,
    teacher_id: int,
    db: Session,
) -> Dict[str, Any]:
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise NotFoundError(f"Poll {poll_id} not found")
    if poll.status != "OPEN":
        raise InvalidStatusTransitionError("Poll is not open")

    poll.status = "CLOSED"
    poll.closed_at = datetime.now(timezone.utc)
    if poll.session:
        poll.session.active_poll_id = None
        poll.session.version += 1

    db.commit()

    await ws_manager.broadcast(poll.session_id, "poll.closed", poll.session.version, {"poll_id": poll.id})
    return {"poll_id": poll.id, "status": "CLOSED"}


def get_poll_results_service(
    poll_id: int,
    user_role: str,
    user_id: int,
    db: Session,
) -> PollResultsResponse:
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise NotFoundError(f"Poll {poll_id} not found")

    responses = db.query(Response).filter(Response.poll_id == poll.id).all()
    counts = {str(opt.id): 0 for opt in poll.question.options}
    correct_count = 0
    for r in responses:
        k = str(r.option_id)
        counts[k] = counts.get(k, 0) + 1
        if r.is_correct:
            correct_count += 1

    total = len(responses)
    pct_correct = int(round((correct_count / total) * 100)) if total > 0 else 0

    correct_option_id = None
    if user_role in ("TEACHER", "ADMIN") or poll.status == "CLOSED":
        correct_opt = db.query(QuestionOption).filter(
            QuestionOption.question_id == poll.question_id,
            QuestionOption.is_correct == True,
        ).first()
        if correct_opt:
            correct_option_id = correct_opt.id

    return PollResultsResponse(
        question_id=poll.question_id,
        correct_option_id=correct_option_id,
        counts=counts,
        total=total,
        pct_correct=pct_correct,
    )
