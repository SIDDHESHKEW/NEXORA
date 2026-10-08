"""Evidence service: creates learning events from question responses."""

from typing import Optional
from sqlalchemy.orm import Session
from backend.core.config import settings
from backend.models.evidence import LearningEvent
from backend.models.assessment import Question, QuestionOption, Response


def create_learning_event_for_response(
    db: Session,
    response: Response,
    is_seeded: bool = False,
) -> LearningEvent:
    """Create a single authoritative learning_event record for a given response."""
    question = db.query(Question).filter(Question.id == response.question_id).first()
    if not question:
        raise ValueError(f"Question {response.question_id} not found")

    option = db.query(QuestionOption).filter(QuestionOption.id == response.option_id).first()
    if not option:
        raise ValueError(f"Option {response.option_id} not found")

    # Determine weight by context
    if response.context == "EXIT_QUIZ":
        weight = settings.W_EXIT_QUIZ  # 0.8
    elif response.context == "LIVE_POLL":
        weight = settings.W_LIVE_POLL  # 0.5
    elif response.context == "PRACTICE":
        weight = settings.W_PRACTICE   # 0.4
    else:
        weight = 0.5

    score = 1.0 if response.is_correct else 0.0
    misconception_id = option.misconception_id if not response.is_correct else None

    event = LearningEvent(
        student_id=response.student_id,
        learning_outcome_id=question.learning_outcome_id,
        question_id=question.id,
        response_id=response.id,
        score=score,
        is_correct=response.is_correct,
        weight=weight,
        source_type=response.context,
        misconception_id=misconception_id,
        duration_ms=response.duration_ms,
        is_seeded=is_seeded,
    )
    db.add(event)
    db.flush()
    return event
