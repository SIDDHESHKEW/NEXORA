"""Curriculum schemas: courses, sections, topics, outcomes, sources."""

from typing import List, Optional
from pydantic import BaseModel, Field


class OutcomeSchema(BaseModel):
    id: int
    code: str
    statement: str
    kind: str = "OUTCOME"  # OUTCOME | PREREQUISITE
    prerequisite_ids: List[int] = Field(default_factory=list)


class SectionSummarySchema(BaseModel):
    id: int
    name: str
    course_id: Optional[int] = None
    enrolled_count: int = 57


class TopicSummarySchema(BaseModel):
    id: int
    seq: int
    title: str
    outcome_count: int = 0


class CourseSchema(BaseModel):
    id: int
    code: str
    name: str
    programme: str
    semester: int
    sections: List[SectionSummarySchema] = Field(default_factory=list)
    topic_count: int = 1


class CourseDetailSchema(CourseSchema):
    topics: List[TopicSummarySchema] = Field(default_factory=list)


class TopicDetailSchema(BaseModel):
    id: int
    title: str
    course_id: int
    outcomes: List[OutcomeSchema] = Field(default_factory=list)
    prerequisites: List[OutcomeSchema] = Field(default_factory=list)


class SourceSchema(BaseModel):
    id: int
    title: str
    citation: str
    approved: bool = True
