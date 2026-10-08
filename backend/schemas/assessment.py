"""Assessment schemas: submissions, results, mastery representations."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.schemas.curriculum import OutcomeSchema


class QuizSubmitAnswer(BaseModel):
    question_id: int
    option_id: int
    duration_ms: Optional[int] = None


class QuizSubmitRequest(BaseModel):
    context: str = Field(..., description="EXIT_QUIZ | PRACTICE")
    session_id: Optional[int] = None
    set_id: Optional[int] = None
    idempotency_key: str
    answers: List[QuizSubmitAnswer]


class QuizResultItem(BaseModel):
    question_id: int
    learning_outcome_id: int
    selected_option_id: int
    correct_option_id: int
    is_correct: bool
    explanation: Optional[str] = None
    misconception: Optional[Dict[str, str]] = None


class MasteryItemSchema(BaseModel):
    outcome: OutcomeSchema
    percent: int
    estimate: float
    status: str  # STRONG | DEVELOPING | WEAK
    evidence_count: int
    prior_note: str = "Pre-class diagnostic (sample)"
    provenance: str = "MIXED"  # LIVE | SEEDED | MIXED


class GapItemSchema(BaseModel):
    outcome_id: int
    code: str
    percent: int
    status: str
    misconception: Optional[Dict[str, str]] = None


class ScoreSummary(BaseModel):
    correct: int
    total: int


class QuizResult(BaseModel):
    duplicate: bool = False
    context: str
    score: ScoreSummary
    items: List[QuizResultItem]
    mastery_before: Optional[List[MasteryItemSchema]] = None
    mastery: List[MasteryItemSchema]
    gaps: List[GapItemSchema] = Field(default_factory=list)
    provenance: str = "LIVE"
    scripted: Optional[bool] = None
