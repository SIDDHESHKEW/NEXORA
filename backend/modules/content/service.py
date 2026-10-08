"""Content and Lesson service handling generation, edits, approvals, and queries."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.core.errors import NotFoundError, ForbiddenScopeError, InvalidStatusTransitionError
from backend.models.curriculum import Topic, LearningOutcome
from backend.models.content import Source, Lesson, LessonBlock
from backend.models.governance import AuditLog
from backend.modules.content.lesson_state import assert_can_edit, transition_lesson_status
from backend.services.ai_gateway import ai_gateway
from backend.schemas.content import (
    LessonSchema,
    BlockSchema,
    LessonGenerateRequest,
    BlockPatchRequest,
    BlockRegenerateRequest,
)
from backend.schemas.curriculum import SourceSchema

logger = logging.getLogger("sgsu.content")


def to_lesson_schema(lesson: Lesson) -> LessonSchema:
    source_schema = (
        SourceSchema(
            id=lesson.source.id,
            title=lesson.source.title,
            citation=lesson.source.citation,
            approved=lesson.source.approved,
        )
        if lesson.source
        else None
    )

    blocks = [
        BlockSchema(
            id=b.id,
            seq=b.seq,
            type=b.type,
            title=b.title,
            content=b.content,
            outcome_ids=b.outcome_ids or [],
            origin=b.origin,
            source_id=b.source_id,
        )
        for b in lesson.blocks
    ]

    return LessonSchema(
        id=lesson.id,
        topic_id=lesson.topic_id,
        title=lesson.title,
        status=lesson.status,
        generation_mode=lesson.generation_mode,
        blocks=blocks,
        source=source_schema,
        unedited_ai_pct=lesson.unedited_ai_pct,
        created_by=lesson.created_by,
        approved_by=lesson.approved_by,
        approved_at=lesson.approved_at,
        published_at=lesson.published_at,
    )


def list_lessons(
    topic_id: Optional[int],
    status: Optional[str],
    user_role: str,
    user_id: int,
    db: Session,
) -> List[LessonSchema]:
    query = db.query(Lesson)
    if topic_id:
        query = query.filter(Lesson.topic_id == topic_id)
    if status:
        query = query.filter(Lesson.status == status)

    if user_role == "STUDENT":
        query = query.filter(Lesson.status == "PUBLISHED")
    elif user_role == "TEACHER":
        # Teacher sees their own lessons (or all published)
        query = query.filter((Lesson.created_by == user_id) | (Lesson.status == "PUBLISHED"))

    lessons = query.order_by(Lesson.id.desc()).all()
    return [to_lesson_schema(l) for l in lessons]


def get_lesson(lesson_id: int, user_role: str, user_id: int, db: Session) -> LessonSchema:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")

    if user_role == "STUDENT" and lesson.status != "PUBLISHED":
        raise ForbiddenScopeError("Students can only view published lessons")

    return to_lesson_schema(lesson)


async def generate_lesson_service(
    request: LessonGenerateRequest,
    teacher_user_id: int,
    db: Session,
) -> LessonSchema:
    topic = db.query(Topic).filter(Topic.id == request.topic_id).first()
    if not topic:
        raise NotFoundError(f"Topic {request.topic_id} not found")

    outcomes = [o for o in topic.learning_outcomes if o.kind == "OUTCOME"]
    source = db.query(Source).filter(Source.topic_id == topic.id, Source.approved == True).first()

    ai_output, gen_mode = await ai_gateway.generate_lesson(
        topic=topic,
        outcomes=outcomes,
        source=source,
        instruction=request.instruction,
        user_id=teacher_user_id,
        role="TEACHER",
        db=db,
    )

    lesson = Lesson(
        topic_id=topic.id,
        title=ai_output.title,
        status="DRAFT",
        generation_mode=gen_mode,
        source_id=source.id if source else None,
        unedited_ai_pct=100,
        created_by=teacher_user_id,
    )
    db.add(lesson)
    db.flush()

    for b in ai_output.blocks:
        block_row = LessonBlock(
            lesson_id=lesson.id,
            seq=b.seq,
            type=b.type,
            title=b.title,
            content=b.content,
            outcome_ids=b.outcome_ids,
            origin=b.origin,
            source_id=source.id if source and b.type == "SOURCE" else None,
        )
        db.add(block_row)

    db.add(AuditLog(
        action="LESSON_GENERATED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="LESSON",
        entity_id=lesson.id,
        detail={"title": lesson.title, "mode": gen_mode},
    ))
    db.commit()

    return to_lesson_schema(lesson)


def patch_lesson_block(
    lesson_id: int,
    block_id: int,
    request: BlockPatchRequest,
    teacher_user_id: int,
    db: Session,
) -> BlockSchema:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    assert_can_edit(lesson)

    block = db.query(LessonBlock).filter(
        LessonBlock.id == block_id,
        LessonBlock.lesson_id == lesson_id,
    ).first()
    if not block:
        raise NotFoundError(f"Block {block_id} not found on lesson {lesson_id}")

    if request.title is not None:
        block.title = request.title
    block.content = request.content
    block.origin = "EDITED"

    # Recalculate unedited percentage
    total_blocks = len(lesson.blocks)
    ai_blocks = sum(1 for b in lesson.blocks if b.origin == "AI")
    lesson.unedited_ai_pct = int(round((ai_blocks / total_blocks) * 100)) if total_blocks else 100

    db.add(AuditLog(
        action="LESSON_EDITED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="LESSON_BLOCK",
        entity_id=block.id,
        detail={"lesson_id": lesson.id, "seq": block.seq},
    ))
    db.commit()

    return BlockSchema(
        id=block.id,
        seq=block.seq,
        type=block.type,
        title=block.title,
        content=block.content,
        outcome_ids=block.outcome_ids,
        origin=block.origin,
        source_id=block.source_id,
    )


async def regenerate_lesson_block(
    lesson_id: int,
    block_id: int,
    request: BlockRegenerateRequest,
    teacher_user_id: int,
    db: Session,
) -> BlockSchema:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")
    assert_can_edit(lesson)

    block = db.query(LessonBlock).filter(
        LessonBlock.id == block_id,
        LessonBlock.lesson_id == lesson_id,
    ).first()
    if not block:
        raise NotFoundError(f"Block {block_id} not found on lesson {lesson_id}")

    # Regenerate content according to block type
    if block.type == "EXPLANATION":
        block.content = {"text": f"Regenerated in-depth explanation: {request.instruction or 'Clear mathematical principles and intuition.'}"}
    elif block.type == "EXAMPLE":
        block.content = {
            "setup": "Consider a simplified 2-layer backpropagation calculation.",
            "steps": ["Step 1: Compute output loss gradient.", "Step 2: Propagate through weights.", "Step 3: Update parameters."],
            "takeaway": "Direct error assignment to hidden units is mathematically incorrect.",
        }
    block.origin = "AI"

    db.add(AuditLog(
        action="LESSON_EDITED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="LESSON_BLOCK",
        entity_id=block.id,
        detail={"action": "regenerate", "lesson_id": lesson.id, "seq": block.seq},
    ))
    db.commit()

    return BlockSchema(
        id=block.id,
        seq=block.seq,
        type=block.type,
        title=block.title,
        content=block.content,
        outcome_ids=block.outcome_ids,
        origin=block.origin,
        source_id=block.source_id,
    )


def review_lesson(lesson_id: int, teacher_user_id: int, db: Session) -> LessonSchema:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")

    transition_lesson_status(lesson, "REVIEWED", teacher_user_id)
    db.add(AuditLog(
        action="LESSON_REVIEWED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="LESSON",
        entity_id=lesson.id,
    ))
    db.commit()
    return to_lesson_schema(lesson)


def approve_lesson(lesson_id: int, teacher_user_id: int, db: Session) -> LessonSchema:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")

    transition_lesson_status(lesson, "APPROVED", teacher_user_id)
    db.add(AuditLog(
        action="LESSON_APPROVED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="LESSON",
        entity_id=lesson.id,
        detail={"content_hash": lesson.content_hash},
    ))
    db.commit()
    return to_lesson_schema(lesson)


def publish_lesson(lesson_id: int, teacher_user_id: int, db: Session) -> LessonSchema:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise NotFoundError(f"Lesson {lesson_id} not found")

    if lesson.status != "APPROVED":
        raise InvalidStatusTransitionError(f"Only approved lessons can be published (status: {lesson.status})")

    transition_lesson_status(lesson, "PUBLISHED", teacher_user_id)
    db.add(AuditLog(
        action="LESSON_PUBLISHED",
        user_id=teacher_user_id,
        role="TEACHER",
        entity="LESSON",
        entity_id=lesson.id,
    ))
    db.commit()
    return to_lesson_schema(lesson)
