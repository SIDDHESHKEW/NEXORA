"""Learner and Mastery models: mastery and section_outcome_stats."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Mastery(Base):
    __tablename__ = "mastery"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    estimate = Column(Float, nullable=False)
    percent = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)  # STRONG | DEVELOPING | WEAK
    evidence_count = Column(Integer, default=0, nullable=False)
    prior_estimate = Column(Float, nullable=False)
    prior_weight = Column(Float, default=2.0, nullable=False)
    provenance = Column(String(20), default="SEEDED", nullable=False)  # LIVE | SEEDED | MIXED
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "learning_outcome_id", name="uq_student_outcome_mastery"),
        CheckConstraint("status IN ('STRONG', 'DEVELOPING', 'WEAK')", name="check_mastery_status"),
        CheckConstraint("provenance IN ('LIVE', 'SEEDED', 'MIXED')", name="check_mastery_provenance"),
    )

    student = relationship("Student", back_populates="mastery_records")
    learning_outcome = relationship("LearningOutcome", back_populates="mastery_records")

    @property
    def current_estimate(self) -> float:
        return self.estimate

    @current_estimate.setter
    def current_estimate(self, val: float) -> None:
        self.estimate = val

    @property
    def weight_sum(self) -> float:
        return 0.0

    @weight_sum.setter
    def weight_sum(self, val: float) -> None:
        pass


class SectionOutcomeStats(Base):
    __tablename__ = "section_outcome_stats"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=False, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    class_mastery_percent = Column(Integer, nullable=False)
    weak_count = Column(Integer, nullable=False)
    respondents = Column(Integer, nullable=False)
    strong_count = Column(Integer, default=0, nullable=False)
    developing_count = Column(Integer, default=0, nullable=False)
    top_misconception_id = Column(Integer, ForeignKey("misconceptions.id"), nullable=True)
    top_misconception_count = Column(Integer, default=0, nullable=False)
    is_seeded = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("section_id", "learning_outcome_id", name="uq_section_outcome_stats"),
    )

    section = relationship("ClassSection", back_populates="outcome_stats")
    learning_outcome = relationship("LearningOutcome", back_populates="section_stats")
    top_misconception = relationship("Misconception")
