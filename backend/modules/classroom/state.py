"""Session state builder: generates sanitized student and teacher views."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.curriculum import Student, User, LearningOutcome
from backend.models.content import LessonBlock
from backend.models.classroom import ClassSession, SessionParticipant, SessionPrompt, Poll
from backend.models.assessment import Question, QuestionOption, Response
from backend.schemas.content import BlockSchema
from backend.schemas.classroom import (
    SessionState,
    SessionLessonSummary,
    QuizStateSummary,
    ActivePollSummary,
    ActivePromptSummary,
    ParticipantSummary,
    StudentQuestion,
    StudentQuestionOption,
)


def build_session_state(
    session: ClassSession,
    user_role: str,
    user_id: int,
    db: Session,
) -> SessionState:
    """Build unified SessionState. Answers and keys are stripped for students."""
    # 1. Lesson and slides
    slides = [
        BlockSchema(
            id=b.id,
            seq=b.seq,
            type=b.type,
            title=b.title,
            content=b.content,
            outcome_ids=b.outcome_ids or [],
            origin=b.origin,
            source_id=b.source_id,
        )
        for b in session.lesson.blocks
    ]
    lesson_summary = SessionLessonSummary(
        id=session.lesson.id,
        title=session.lesson.title,
        slides=slides,
    )

    # 2. Participants count and list
    participants = db.query(SessionParticipant).filter(SessionParticipant.session_id == session.id).all()
    participants_count = len(participants)

    teacher_participants_list = None
    if user_role in ("TEACHER", "ADMIN"):
        teacher_participants_list = []
        for p in participants:
            u = p.student.user if (p.student and p.student.user) else None
            teacher_participants_list.append(
                ParticipantSummary(
                    id=p.student_id,
                    name=p.display_name or (u.name if u else f"Student {p.student_id}"),
                    joined_at=p.joined_at,
                    quiz_submitted=p.quiz_submitted_at is not None,
                )
            )

    # 3. Quiz State
    submitted_count = sum(1 for p in participants if p.quiz_submitted_at is not None)
    quiz_summary = QuizStateSummary(
        status=session.quiz_status,
        submitted_count=submitted_count,
        total_participants=participants_count,
    )

    # 4. Active Poll
    active_poll_summary = None
    if session.active_poll_id:
        poll = db.query(Poll).filter(Poll.id == session.active_poll_id).first()
        if poll:
            q = poll.question
            # Build student question (stripping is_correct)
            options = [
                StudentQuestionOption(id=opt.id, label=opt.label, text=opt.text)
                for opt in q.options
            ]
            student_q = StudentQuestion(
                id=q.id,
                seq=q.seq,
                stem=q.stem,
                learning_outcome_id=q.learning_outcome_id,
                options=options,
            )

            # Option counts
            poll_counts = None
            if user_role in ("TEACHER", "ADMIN") or poll.status == "CLOSED":
                responses = db.query(Response).filter(Response.poll_id == poll.id).all()
                counts: Dict[str, int] = {str(opt.id): 0 for opt in q.options}
                for r in responses:
                    key = str(r.option_id)
                    counts[key] = counts.get(key, 0) + 1
                poll_counts = counts

            active_poll_summary = ActivePollSummary(
                id=poll.id,
                status=poll.status,
                question=student_q,
                counts=poll_counts,
            )

    # 5. Active Prompt
    active_prompt_summary = None
    if session.active_prompt_id:
        p_row = db.query(SessionPrompt).filter(SessionPrompt.id == session.active_prompt_id).first()
        if p_row:
            active_prompt_summary = ActivePromptSummary(id=p_row.id, text=p_row.text)

    join_url = f"{settings.FRONTEND_ORIGIN}/student/classroom?session={session.id}"

    return SessionState(
        id=session.id,
        status=session.status,
        version=session.version,
        lesson=lesson_summary,
        section_id=session.section_id,
        current_slide_index=session.current_slide_index,
        current_outcome_id=session.current_outcome_id,
        quiz=quiz_summary,
        active_poll=active_poll_summary,
        active_prompt=active_prompt_summary,
        participants_count=participants_count,
        join_url=join_url,
        participants=teacher_participants_list,
    )
