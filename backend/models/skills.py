"""Skills and Skill Passport data models."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    is_derived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    outcomes = relationship("OutcomeSkill", back_populates="skill", cascade="all, delete-orphan")
    student_skills = relationship("StudentSkill", back_populates="skill", cascade="all, delete-orphan")


class OutcomeSkill(Base):
    __tablename__ = "outcome_skills"

    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("skill_id", "learning_outcome_id", name="uq_outcome_skill"),
    )

    skill = relationship("Skill", back_populates="outcomes")
    learning_outcome = relationship("LearningOutcome")


class StudentSkill(Base):
    __tablename__ = "student_skills"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False, index=True)
    level = Column(String(30), nullable=False)  # NEEDS_PRACTICE | DEVELOPING | STRONG | RECOMMENDED_NEXT
    source = Column(String(20), default="SEEDED", nullable=False)  # SEEDED | DERIVED
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "skill_id", name="uq_student_skill"),
        CheckConstraint("level IN ('NEEDS_PRACTICE', 'DEVELOPING', 'STRONG', 'RECOMMENDED_NEXT')", name="check_skill_level"),
        CheckConstraint("source IN ('SEEDED', 'DERIVED')", name="check_skill_source"),
    )

    student = relationship("Student", back_populates="student_skills")
    skill = relationship("Skill", back_populates="student_skills")
