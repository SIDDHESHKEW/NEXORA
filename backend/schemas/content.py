"""Content schemas: lessons, blocks, generation, edits."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.schemas.curriculum import SourceSchema


class BlockSchema(BaseModel):
    id: int
    seq: int
    type: str  # TITLE, OBJECTIVES, EXPLANATION, KEY_CONCEPTS, EXAMPLE, MISCONCEPTION, QUICK_CHECK, SOURCE
    title: Optional[str] = None
    content: Dict[str, Any]
    outcome_ids: List[int] = Field(default_factory=list)
    origin: str = "AI"  # AI | EDITED
    source_id: Optional[int] = None


class LessonSchema(BaseModel):
    id: int
    topic_id: int
    title: str
    status: str  # DRAFT | REVIEWED | APPROVED | PUBLISHED
    generation_mode: str  # LIVE | FALLBACK
    blocks: List[BlockSchema] = Field(default_factory=list)
    source: Optional[SourceSchema] = None
    unedited_ai_pct: int = 100
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None


class LessonGenerateRequest(BaseModel):
    topic_id: int
    duration_min: int = Field(default=50)
    style: Optional[List[str]] = None
    instruction: Optional[str] = None


class BlockPatchRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class BlockRegenerateRequest(BaseModel):
    instruction: Optional[str] = None
