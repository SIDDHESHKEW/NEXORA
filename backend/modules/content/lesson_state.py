"""Lesson workflow state machine: DRAFT -> REVIEWED -> APPROVED -> PUBLISHED."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from backend.core.errors import InvalidStatusTransitionError
from backend.models.content import Lesson


VALID_TRANSITIONS = {
    "DRAFT": ["REVIEWED"],
    "REVIEWED": ["APPROVED", "DRAFT"],
    "APPROVED": ["PUBLISHED"],
    "PUBLISHED": [],
}


def validate_status_transition(current_status: str, new_status: str) -> bool:
    """Check if status transition is allowed."""
    return new_status in VALID_TRANSITIONS.get(current_status, [])


def can_edit_lesson_blocks(status: str) -> bool:
    """Editing blocks is permitted only before approval."""
    return status not in ("APPROVED", "PUBLISHED")


def assert_can_edit(lesson: Lesson) -> None:
    """Editing is forbidden once approved or published."""
    if not can_edit_lesson_blocks(lesson.status):
        raise InvalidStatusTransitionError(
            f"Approved or published lessons cannot be edited (current status: {lesson.status})"
        )


def transition_lesson_status(lesson: Lesson, new_status: str, actor_id: int) -> None:
    if not validate_status_transition(lesson.status, new_status):
        raise InvalidStatusTransitionError(
            f"Cannot transition lesson from '{lesson.status}' to '{new_status}'"
        )

    now = datetime.now(timezone.utc)
    if new_status == "REVIEWED":
        lesson.status = "REVIEWED"

    elif new_status == "APPROVED":
        lesson.status = "APPROVED"
        lesson.approved_by = actor_id
        lesson.approved_at = now
        # Compute sha256 hash of all blocks
        block_representations = [
            {"seq": b.seq, "type": b.type, "title": b.title, "content": b.content}
            for b in lesson.blocks
        ]
        dumped = json.dumps(block_representations, sort_keys=True)
        lesson.content_hash = hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    elif new_status == "PUBLISHED":
        lesson.status = "PUBLISHED"
        lesson.published_at = now
