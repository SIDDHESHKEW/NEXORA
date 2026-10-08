"""Identity and Curriculum data models: users, students, teachers, courses, sections, topics, outcomes, prerequisites, misconceptions."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.core.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    role = Column(String(20), nullable=False, index=True)  # STUDENT, TEACHER, ADMIN
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('STUDENT', 'TEACHER', 'ADMIN')", name="check_user_role"),
    )

    # Relationships
    student = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher = relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_no = Column(String(50), unique=True, nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=False, index=True)
    is_live = Column(Boolean, default=False, nullable=False)
    is_named = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="student")
    section = relationship("ClassSection", back_populates="students")
    responses = relationship("Response", back_populates="student")
    learning_events = relationship("LearningEvent", back_populates="student")
    mastery_records = relationship("Mastery", back_populates="student")
    recommendations = relationship("Recommendation", back_populates="student")
    practice_sets = relationship("PracticeSet", back_populates="student")
    student_skills = relationship("StudentSkill", back_populates="student")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    department = Column(String(100), nullable=False, default="Computer Science & Engineering")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="teacher")
    sections = relationship("ClassSection", back_populates="teacher")
    sessions = relationship("ClassSession", back_populates="teacher")


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # e.g. CS-501
    name = Column(String(150), nullable=False)  # e.g. Artificial Intelligence
    programme = Column(String(100), nullable=False, default="B.Tech CSE")
    semester = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    sections = relationship("ClassSection", back_populates="course", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="course", cascade="all, delete-orphan")


class ClassSection(Base):
    __tablename__ = "class_sections"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)  # e.g. 5-A, 5-B
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True, index=True)
    enrolled_count = Column(Integer, default=57, nullable=False)

    course = relationship("Course", back_populates="sections")
    teacher = relationship("Teacher", back_populates="sections")
    students = relationship("Student", back_populates="section")
    sessions = relationship("ClassSession", back_populates="section")
    outcome_stats = relationship("SectionOutcomeStats", back_populates="section")

    __table_args__ = (
        UniqueConstraint("course_id", "name", name="uq_course_section_name"),
    )


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    seq = Column(Integer, default=1, nullable=False)
    title = Column(String(150), nullable=False)  # e.g. Neural Networks
    created_at = Column(DateTime, default=utcnow, nullable=False)

    course = relationship("Course", back_populates="topics")
    learning_outcomes = relationship("LearningOutcome", back_populates="topic", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="topic")
    sources = relationship("Source", back_populates="topic")
    questions = relationship("Question", back_populates="topic")


class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    code = Column(String(20), nullable=False, index=True)  # e.g. LO1, LO2, LO3, LO4, P1, P2
    statement = Column(String(255), nullable=False)
    kind = Column(String(20), default="OUTCOME", nullable=False)  # OUTCOME or PREREQUISITE
    created_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("topic_id", "code", name="uq_topic_outcome_code"),
        CheckConstraint("kind IN ('OUTCOME', 'PREREQUISITE')", name="check_outcome_kind"),
    )

    topic = relationship("Topic", back_populates="learning_outcomes")
    misconceptions = relationship("Misconception", back_populates="learning_outcome", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="learning_outcome")
    mastery_records = relationship("Mastery", back_populates="learning_outcome")
    learning_events = relationship("LearningEvent", back_populates="learning_outcome")
    section_stats = relationship("SectionOutcomeStats", back_populates="learning_outcome")


class PrerequisiteEdge(Base):
    __tablename__ = "prerequisites"

    id = Column(Integer, primary_key=True, index=True)
    outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    prerequisite_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("outcome_id", "prerequisite_id", name="uq_prerequisite_edge"),
    )


class Misconception(Base):
    __tablename__ = "misconceptions"

    id = Column(Integer, primary_key=True, index=True)
    learning_outcome_id = Column(Integer, ForeignKey("learning_outcomes.id"), nullable=False, index=True)
    tag = Column(String(80), unique=True, nullable=False, index=True)
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    learning_outcome = relationship("LearningOutcome", back_populates="misconceptions")
    options = relationship("QuestionOption", back_populates="misconception")
