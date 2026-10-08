"""Evidence Store model: learning_events."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True, index=True)
    response_id = Column(Integer, ForeignKey("responses.id"), nullable=True, index=True)
    score = Column(Float, nullable=False)  # 0.0 or 1.0
    is_correct = Column(Boolean, nullable=True)
    weight = Column(Float, nullable=False)  # 0.8 (exit quiz), 0.5 (poll), 0.4 (practice)
    source_type = Column(String(30), nullable=False, index=True)  # EXIT_QUIZ | LIVE_POLL | PRACTICE
    misconception_id = Column(Integer, ForeignKey("misconceptions.id"), nullable=True, index=True)
    duration_ms = Column(Integer, nullable=True)
    is_seeded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("source_type IN ('EXIT_QUIZ', 'LIVE_POLL', 'PRACTICE')", name="check_event_source_type"),
    )

    student = relationship("Student", back_populates="learning_events")
    learning_outcome = relationship("LearningOutcome", back_populates="learning_events")
    question = relationship("Question", back_populates="learning_events")
    response = relationship("Response", back_populates="learning_events")
    misconception = relationship("Misconception")
