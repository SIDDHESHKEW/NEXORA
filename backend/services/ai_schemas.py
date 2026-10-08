"""Pydantic schemas for AI Gateway inputs, outputs, and validation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# 1. Lesson Generation Schemas
class AILessonBlock(BaseModel):
    seq: int
    type: str  # TITLE, OBJECTIVES, EXPLANATION, KEY_CONCEPTS, EXAMPLE, MISCONCEPTION, QUICK_CHECK, SOURCE
    title: Optional[str] = None
    content: Dict[str, Any]
    outcome_ids: List[int] = Field(default_factory=list)
    origin: str = "AI"


class AILessonOutput(BaseModel):
    title: str
    blocks: List[AILessonBlock]


# 2. Explanation / Recap Schemas
class AIRecapOutput(BaseModel):
    recap_text: str
    key_points: List[str] = Field(..., min_length=3, max_length=3)


# 3. Practice Questions Schemas
class AIPracticeOption(BaseModel):
    label: str
    text: str
    is_correct: bool
    misconception: Optional[str] = None


class AIPracticeQuestion(BaseModel):
    stem: str
    options: List[AIPracticeOption]
    explanation: Optional[str] = None


class AIPracticeQuestionsOutput(BaseModel):
    questions: List[AIPracticeQuestion] = Field(..., min_length=3, max_length=3)


# 4. Tutor Response Schemas
class AITutorOutput(BaseModel):
    answer: str
    topic: str = "Backpropagation"
    source: str = "Neural Networks — Course Material"
    label: str = "Grounded in approved course material"
    mode: str = "LIVE"

    @property
    def text(self) -> str:
        return self.answer


# 5. Reteach Segment Schemas
class AIReteachOutline(BaseModel):
    minute_range: str
    activity: str


class AIReteachWorkedExample(BaseModel):
    setup: str
    steps: List[str]
    takeaway: str


class AIReteachCheckItem(BaseModel):
    stem: str
    options: List[str]
    answer: str


class AIReteachOutput(BaseModel):
    title: str
    duration_min: int = 10
    outline: List[AIReteachOutline]
    worked_example: AIReteachWorkedExample
    check_items: List[AIReteachCheckItem] = Field(..., min_length=2, max_length=2)
    generation_mode: str = "LIVE"


# 6. Academic Recommendation Schemas
class AIAcademicOutput(BaseModel):
    text: str
    mode: str = "LIVE"
