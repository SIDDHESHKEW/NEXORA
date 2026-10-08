"""Content and Lesson models: sources, lessons, lesson_blocks."""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
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


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    citation = Column(String(255), nullable=False)
    body_text = Column(Text, nullable=False)
    approved = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    topic = relationship("Topic", back_populates="sources")
    lessons = relationship("Lesson", back_populates="source")
    blocks = relationship("LessonBlock", back_populates="source")

    @property
    def content(self) -> str:
        return self.body_text

    @content.setter
    def content(self, val: str) -> None:
        self.body_text = val


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    status = Column(String(20), default="DRAFT", nullable=False, index=True)
    generation_mode = Column(String(20), default="FALLBACK", nullable=False)  # LIVE | FALLBACK
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    unedited_ai_pct = Column(Integer, default=100, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    content_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'REVIEWED', 'APPROVED', 'PUBLISHED')", name="check_lesson_status"),
        CheckConstraint("generation_mode IN ('LIVE', 'FALLBACK')", name="check_lesson_gen_mode"),
    )

    topic = relationship("Topic", back_populates="lessons")
    source = relationship("Source", back_populates="lessons")
    blocks = relationship("LessonBlock", back_populates="lesson", cascade="all, delete-orphan", order_by="LessonBlock.seq")
    sessions = relationship("ClassSession", back_populates="lesson")


class LessonBlock(Base):
    __tablename__ = "lesson_blocks"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    type = Column(String(30), nullable=False)  # TITLE, OBJECTIVES, EXPLANATION, KEY_CONCEPTS, EXAMPLE, MISCONCEPTION, QUICK_CHECK, SOURCE
    title = Column(String(200), nullable=True)
    content = Column(JSON, nullable=False)  # dictionary / list
    outcome_ids = Column(JSON, default=list, nullable=False)  # list of int outcome IDs
    origin = Column(String(20), default="AI", nullable=False)  # AI | EDITED
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    __table_args__ = (
        CheckConstraint("origin IN ('AI', 'EDITED')", name="check_block_origin"),
        UniqueConstraint("lesson_id", "seq", name="uq_lesson_block_seq"),
    )

    lesson = relationship("Lesson", back_populates="blocks")
    source = relationship("Source", back_populates="blocks")
