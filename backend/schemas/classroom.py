"""Classroom schemas: sessions, slides, polls, prompts, student vs teacher views."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.schemas.content import BlockSchema


class StudentQuestionOption(BaseModel):
    id: int
    label: str
    text: str


class TeacherQuestionOption(BaseModel):
    id: int
    label: str
    text: str
    is_correct: bool
    misconception: Optional[Dict[str, str]] = None


class StudentQuestion(BaseModel):
    id: int
    seq: int
    stem: str
    learning_outcome_id: int
    options: List[StudentQuestionOption]


class TeacherQuestion(BaseModel):
    id: int
    seq: int
    stem: str
    learning_outcome_id: int
    purpose: str
    options: List[TeacherQuestionOption]
    explanation: Optional[str] = None


class SessionLessonSummary(BaseModel):
    id: int
    title: str
    slides: List[BlockSchema] = Field(default_factory=list)


class QuizStateSummary(BaseModel):
    status: str = "NOT_STARTED"  # NOT_STARTED | OPEN | CLOSED
    submitted_count: int = 0
    total_participants: int = 0


class ActivePollSummary(BaseModel):
    id: int
    status: str  # OPEN | CLOSED
    question: StudentQuestion
    counts: Optional[Dict[str, int]] = None  # Populated only for teacher or after close


class ActivePromptSummary(BaseModel):
    id: int
    text: str


class ParticipantSummary(BaseModel):
    id: int
    name: str
    joined_at: datetime
    quiz_submitted: bool = False


class SessionState(BaseModel):
    id: int
    status: str  # LIVE | ENDED
    version: int
    lesson: SessionLessonSummary
    section_id: int
    current_slide_index: int = 0
    current_outcome_id: Optional[int] = None
    quiz: QuizStateSummary
    active_poll: Optional[ActivePollSummary] = None
    active_prompt: Optional[ActivePromptSummary] = None
    participants_count: int = 0
    join_url: str
    participants: Optional[List[ParticipantSummary]] = None  # Teacher view only


class SessionStartRequest(BaseModel):
    lesson_id: int
    section_id: int


class SessionJoinRequest(BaseModel):
    display_name: Optional[str] = None


class SlideActionRequest(BaseModel):
    action: str = Field(..., description="NEXT | PREV | GOTO")
    index: Optional[int] = None


class PromptCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=280)


class PollCreateRequest(BaseModel):
    session_id: int
    question_id: int


class PollRespondRequest(BaseModel):
    option_id: int
    idempotency_key: str


class PollResultsResponse(BaseModel):
    question_id: int
    correct_option_id: Optional[int] = None
    counts: Dict[str, int]
    total: int
    pct_correct: int
