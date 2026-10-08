"""Assessment models: questions, question_options, responses."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    seq = Column(Integer, default=1, nullable=False)
    stem = Column(Text, nullable=False)
    purpose = Column(String(30), default="EXIT_QUIZ", nullable=False, index=True)  # EXIT_QUIZ | POLL | PRACTICE
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("purpose IN ('EXIT_QUIZ', 'POLL', 'PRACTICE')", name="check_question_purpose"),
    )

    topic = relationship("Topic", back_populates="questions")
    learning_outcome = relationship("LearningOutcome", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.label")
    responses = relationship("Response", back_populates="question")
    learning_events = relationship("LearningEvent", back_populates="question")


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(5), nullable=False)  # A, B, C, D
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    misconception_id = Column(Integer, ForeignKey("misconceptions.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("question_id", "label", name="uq_question_option_label"),
    )

    question = relationship("Question", back_populates="options")
    misconception = relationship("Misconception", back_populates="options")
    responses = relationship("Response", back_populates="option")


class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    option_id = Column(Integer, ForeignKey("question_options.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    practice_set_id = Column(Integer, ForeignKey("practice_sets.id"), nullable=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), nullable=True, index=True)
    context = Column(String(30), nullable=False, index=True)  # EXIT_QUIZ | LIVE_POLL | PRACTICE
    is_correct = Column(Boolean, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    idempotency_key = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("context IN ('EXIT_QUIZ', 'LIVE_POLL', 'PRACTICE')", name="check_response_context"),
    )

    student = relationship("Student", back_populates="responses")
    question = relationship("Question", back_populates="responses")
    option = relationship("QuestionOption", back_populates="responses")
    session = relationship("ClassSession", back_populates="responses")
    poll = relationship("Poll", back_populates="responses")
    practice_set = relationship("PracticeSet", back_populates="responses")
    learning_events = relationship("LearningEvent", back_populates="response")
