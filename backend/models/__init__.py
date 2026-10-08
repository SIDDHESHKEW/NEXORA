"""Expose all SQLAlchemy 2.0 models."""

from backend.models.curriculum import (
    User,
    Student,
    Teacher,
    Course,
    ClassSection,
    Topic,
    LearningOutcome,
    PrerequisiteEdge,
    Misconception,
)
from backend.models.content import (
    Source,
    Lesson,
    LessonBlock,
)
from backend.models.classroom import (
    ClassSession,
    SessionParticipant,
    SessionPrompt,
    Poll,
)
from backend.models.assessment import (
    Question,
    QuestionOption,
    Response,
)
from backend.models.evidence import (
    LearningEvent,
)
from backend.models.learner import (
    Mastery,
    SectionOutcomeStats,
)
from backend.models.recommendation import (
    Recommendation,
    PracticeSet,
    PracticeSetQuestion,
)
from backend.models.skills import (
    Skill,
    OutcomeSkill,
    StudentSkill,
)
from backend.models.governance import (
    AIInteraction,
    AuditLog,
    AppSetting,
)

__all__ = [
    "User",
    "Student",
    "Teacher",
    "Course",
    "ClassSection",
    "Topic",
    "LearningOutcome",
    "PrerequisiteEdge",
    "Misconception",
    "Source",
    "Lesson",
    "LessonBlock",
    "ClassSession",
    "SessionParticipant",
    "SessionPrompt",
    "Poll",
    "Question",
    "QuestionOption",
    "Response",
    "LearningEvent",
    "Mastery",
    "SectionOutcomeStats",
    "Recommendation",
    "PracticeSet",
    "PracticeSetQuestion",
    "Skill",
    "OutcomeSkill",
    "StudentSkill",
    "AIInteraction",
    "AuditLog",
    "AppSetting",
]
