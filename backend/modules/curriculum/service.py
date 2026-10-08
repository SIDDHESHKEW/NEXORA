"""Curriculum service: queries courses, topics, learning outcomes, sections, and approved sources."""

from typing import List, Optional
from sqlalchemy.orm import Session
from backend.core.errors import NotFoundError
from backend.models.curriculum import Course, ClassSection, Topic, LearningOutcome, PrerequisiteEdge
from backend.models.content import Source
from backend.schemas.curriculum import (
    CourseSchema,
    CourseDetailSchema,
    SectionSummarySchema,
    TopicSummarySchema,
    TopicDetailSchema,
    OutcomeSchema,
    SourceSchema,
)


def list_courses(db: Session) -> List[CourseSchema]:
    courses = db.query(Course).all()
    result = []
    for c in courses:
        sections = [
            SectionSummarySchema(id=s.id, name=s.name, course_id=s.course_id, enrolled_count=s.enrolled_count)
            for s in c.sections
        ]
        result.append(
            CourseSchema(
                id=c.id,
                code=c.code,
                name=c.name,
                programme=c.programme,
                semester=c.semester,
                sections=sections,
                topic_count=len(c.topics),
            )
        )
    return result


def get_course_detail(course_id: int, db: Session) -> CourseDetailSchema:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise NotFoundError(f"Course {course_id} not found")

    sections = [
        SectionSummarySchema(id=s.id, name=s.name, course_id=s.course_id, enrolled_count=s.enrolled_count)
        for s in course.sections
    ]
    topics = [
        TopicSummarySchema(
            id=t.id,
            seq=t.seq,
            title=t.title,
            outcome_count=len([o for o in t.learning_outcomes if o.kind == "OUTCOME"]),
        )
        for t in course.topics
    ]
    return CourseDetailSchema(
        id=course.id,
        code=course.code,
        name=course.name,
        programme=course.programme,
        semester=course.semester,
        sections=sections,
        topic_count=len(course.topics),
        topics=topics,
    )


def get_topic_detail(topic_id: int, db: Session) -> TopicDetailSchema:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise NotFoundError(f"Topic {topic_id} not found")

    outcomes = []
    prerequisites = []

    for lo in topic.learning_outcomes:
        # Find prerequisite edges
        edges = db.query(PrerequisiteEdge).filter(PrerequisiteEdge.outcome_id == lo.id).all()
        prereq_ids = [e.prerequisite_id for e in edges]
        schema = OutcomeSchema(
            id=lo.id,
            code=lo.code,
            statement=lo.statement,
            kind=lo.kind,
            prerequisite_ids=prereq_ids,
        )
        if lo.kind == "OUTCOME":
            outcomes.append(schema)
        else:
            prerequisites.append(schema)

    return TopicDetailSchema(
        id=topic.id,
        title=topic.title,
        course_id=topic.course_id,
        outcomes=outcomes,
        prerequisites=prerequisites,
    )


def list_learning_outcomes(topic_id: Optional[int], kind: Optional[str], db: Session) -> List[OutcomeSchema]:
    query = db.query(LearningOutcome)
    if topic_id:
        query = query.filter(LearningOutcome.topic_id == topic_id)
    if kind:
        query = query.filter(LearningOutcome.kind == kind)

    results = []
    for lo in query.order_by(LearningOutcome.code.asc()).all():
        edges = db.query(PrerequisiteEdge).filter(PrerequisiteEdge.outcome_id == lo.id).all()
        prereq_ids = [e.prerequisite_id for e in edges]
        results.append(
            OutcomeSchema(
                id=lo.id,
                code=lo.code,
                statement=lo.statement,
                kind=lo.kind,
                prerequisite_ids=prereq_ids,
            )
        )
    return results


def list_sections(course_id: Optional[int], db: Session) -> List[SectionSummarySchema]:
    query = db.query(ClassSection)
    if course_id:
        query = query.filter(ClassSection.course_id == course_id)
    return [
        SectionSummarySchema(id=s.id, name=s.name, course_id=s.course_id, enrolled_count=s.enrolled_count)
        for s in query.all()
    ]


def list_approved_sources(topic_id: Optional[int], db: Session) -> List[SourceSchema]:
    query = db.query(Source).filter(Source.approved == True)
    if topic_id:
        query = query.filter(Source.topic_id == topic_id)
    # Body text is NEVER returned to client
    return [
        SourceSchema(id=s.id, title=s.title, citation=s.citation, approved=s.approved)
        for s in query.all()
    ]
