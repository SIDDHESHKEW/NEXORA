"""Classroom models: sessions, participants, prompts, polls."""

from datetime import datetime, timezone
from sqlalchemy import (
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


class ClassSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    status = Column(String(20), default="LIVE", nullable=False, index=True)  # LIVE | ENDED
    version = Column(Integer, default=1, nullable=False)
    current_slide_index = Column(Integer, default=0, nullable=False)
    current_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=True)
    quiz_status = Column(String(20), default="NOT_STARTED", nullable=False)  # NOT_STARTED | OPEN | CLOSED
    active_poll_id = Column(Integer, nullable=True)
    active_prompt_id = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('LIVE', 'ENDED')", name="check_session_status"),
        CheckConstraint("quiz_status IN ('NOT_STARTED', 'OPEN', 'CLOSED')", name="check_session_quiz_status"),
    )

    lesson = relationship("Lesson", back_populates="sessions")
    section = relationship("ClassSection", back_populates="sessions")
    teacher = relationship("Teacher", back_populates="sessions")
    participants = relationship("SessionParticipant", back_populates="session", cascade="all, delete-orphan")
    prompts = relationship("SessionPrompt", back_populates="session", cascade="all, delete-orphan")
    polls = relationship("Poll", back_populates="session", cascade="all, delete-orphan")
    responses = relationship("Response", back_populates="session")


class SessionParticipant(Base):
    __tablename__ = "session_participants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    display_name = Column(String(100), nullable=True)
    joined_at = Column(DateTime, default=utcnow, nullable=False)
    quiz_submitted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_participant"),
    )

    session = relationship("ClassSession", back_populates="participants")
    student = relationship("Student")


class SessionPrompt(Base):
    __tablename__ = "session_prompts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(280), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    session = relationship("ClassSession", back_populates="prompts")


class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    status = Column(String(20), default="OPEN", nullable=False, index=True)  # OPEN | CLOSED
    created_at = Column(DateTime, default=utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="check_poll_status"),
    )

    session = relationship("ClassSession", back_populates="polls")
    question = relationship("Question")
    responses = relationship("Response", back_populates="poll")
