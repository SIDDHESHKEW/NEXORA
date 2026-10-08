"""Lesson routes (L01 - L08)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.db import get_db
from backend.core.security import get_current_user_claims, require_role
from backend.modules.content.service import (
    list_lessons,
    get_lesson,
    generate_lesson_service,
    patch_lesson_block,
    regenerate_lesson_block,
    review_lesson,
    approve_lesson,
    publish_lesson,
)
from backend.schemas.content import (
    LessonSchema,
    BlockSchema,
    LessonGenerateRequest,
    BlockPatchRequest,
    BlockRegenerateRequest,
)

router = APIRouter(prefix="/api/lessons", tags=["Lessons"])


@router.get("", response_model=List[LessonSchema])
def get_lessons(
    topic_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """L01: List lessons filtered by topic and status."""
    user_id = int(claims["sub"])
    role = claims.get("role", "STUDENT")
    return list_lessons(topic_id, status, role, user_id, db)


@router.get("/{id}", response_model=LessonSchema)
def get_single_lesson(
    id: int,
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """L02: Get lesson with all blocks and source reference."""
    user_id = int(claims["sub"])
    role = claims.get("role", "STUDENT")
    return get_lesson(id, role, user_id, db)


@router.post("/generate", response_model=LessonSchema, status_code=status.HTTP_201_CREATED)
async def generate_lesson(
    request: LessonGenerateRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """L03: Generate structured AI lesson blocks."""
    user_id = int(claims["sub"])
    return await generate_lesson_service(request, user_id, db)


@router.patch("/{id}/blocks/{block_id}", response_model=BlockSchema)
def patch_block(
    id: int,
    block_id: int,
    request: BlockPatchRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """L04: Edit block content before approval."""
    user_id = int(claims["sub"])
    return patch_lesson_block(id, block_id, request, user_id, db)


@router.post("/{id}/blocks/{block_id}/regenerate", response_model=BlockSchema)
async def regenerate_block(
    id: int,
    block_id: int,
    request: BlockRegenerateRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """L05: Regenerate single block content using AI Gateway."""
    user_id = int(claims["sub"])
    return await regenerate_lesson_block(id, block_id, request, user_id, db)


@router.post("/{id}/review", response_model=LessonSchema)
def review_lesson_endpoint(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """L06: Transition lesson to REVIEWED."""
    user_id = int(claims["sub"])
    return review_lesson(id, user_id, db)


@router.post("/{id}/approve", response_model=LessonSchema)
def approve_lesson_endpoint(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """L07: Approve lesson and generate content hash."""
    user_id = int(claims["sub"])
    return approve_lesson(id, user_id, db)


@router.post("/{id}/publish", response_model=LessonSchema)
def publish_lesson_endpoint(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """L08: Publish approved lesson for classroom teaching."""
    user_id = int(claims["sub"])
    return publish_lesson(id, user_id, db)
