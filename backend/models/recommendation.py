"""Recommendations and Practice sets models."""

from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=True, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    type = Column(String(30), nullable=False, index=True)  # GAP_SUPPORT | RETEACH | ACADEMIC | PRACTICE_ASSIGNED
    title = Column(String(200), nullable=False)
    why = Column(Text, nullable=True)
    what_happened = Column(Text, nullable=True)
    why_seen = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    suggested_approach = Column(Text, nullable=True)
    facts = Column(JSON, nullable=True)
    payload = Column(JSON, nullable=True)
    recap_status = Column(String(20), nullable=True)  # PENDING | READY | READY_FALLBACK
    recap_text = Column(Text, nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE | RESOLVED
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("type IN ('GAP_SUPPORT', 'RETEACH', 'ACADEMIC', 'PRACTICE_ASSIGNED')", name="check_recommendation_type"),
    )

    student = relationship("Student", back_populates="recommendations")
    section = relationship("ClassSection")
    learning_outcome = relationship("LearningOutcome")


class PracticeSet(Base):
    __tablename__ = "practice_sets"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="NEW", nullable=False)  # NEW | COMPLETED | ASSIGNED
    generation_mode = Column(String(20), default="FALLBACK", nullable=False)  # LIVE | FALLBACK
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('NEW', 'COMPLETED', 'ASSIGNED')", name="check_practice_set_status"),
    )

    student = relationship("Student", back_populates="practice_sets")
    learning_outcome = relationship("LearningOutcome")
    questions = relationship("PracticeSetQuestion", back_populates="practice_set", cascade="all, delete-orphan", order_by="PracticeSetQuestion.seq")
    responses = relationship("Response", back_populates="practice_set")


class PracticeSetQuestion(Base):
    __tablename__ = "practice_set_questions"

    id = Column(Integer, primary_key=True, index=True)
    practice_set_id = Column(Integer, ForeignKey("practice_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    seq = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        UniqueConstraint("practice_set_id", "question_id", name="uq_practice_set_question"),
    )

    practice_set = relationship("PracticeSet", back_populates="questions")
    question = relationship("Question")
