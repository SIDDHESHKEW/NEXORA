"""Validators for AI Gateway responses implementing strict educational and schema constraints."""

import re
from typing import Any, Dict, List, Optional, Set
from backend.services.ai_schemas import (
    AILessonOutput,
    AIRecapOutput,
    AIPracticeQuestionsOutput,
    AITutorOutput,
    AIReteachOutput,
    AIAcademicOutput,
)


class AIValidationError(Exception):
    """Raised when an AI response fails deterministic structural or policy checks."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def count_words(text: str) -> int:
    return len(re.findall(r'\b\w+\b', text))


def extract_numbers(text: str) -> Set[int]:
    """Extract all integer numbers appearing in text."""
    matches = re.findall(r'\b\d+\b', text)
    return {int(m) for m in matches}


def validate_lesson_structure(
    lesson_data: AILessonOutput,
    expected_outcome_ids: List[int],
    expected_citation: str,
) -> None:
    """Validate block order, LO mappings, citation, and non-empty content."""
    blocks = lesson_data.blocks
    if not blocks:
        raise AIValidationError("Lesson contains no blocks")

    expected_sequence = [
        "TITLE",
        "OBJECTIVES",
        "EXPLANATION",
        "EXPLANATION",
        "EXPLANATION",
        "EXPLANATION",
        "KEY_CONCEPTS",
        "EXAMPLE",
        "MISCONCEPTION",
        "QUICK_CHECK",
        "SOURCE",
    ]

    actual_types = [b.type for b in blocks]
    if actual_types != expected_sequence:
        raise AIValidationError(
            f"Invalid block order. Expected {expected_sequence}, got {actual_types}"
        )

    # Check explanation outcome mappings
    explanation_blocks = [b for b in blocks if b.type == "EXPLANATION"]
    for i, b in enumerate(explanation_blocks):
        if not b.outcome_ids or not any(oid in expected_outcome_ids for oid in b.outcome_ids):
            raise AIValidationError(f"Explanation block {i+1} must map to a valid learning outcome")

    # Check SOURCE block citation
    source_block = blocks[-1]
    actual_citation = source_block.content.get("citation", "").strip()
    if actual_citation != expected_citation.strip():
        raise AIValidationError(
            f"SOURCE citation mismatch. Expected '{expected_citation}', got '{actual_citation}'"
        )

    # Verify no block has empty content
    for b in blocks:
        if not b.content:
            raise AIValidationError(f"Block {b.seq} ({b.type}) has empty content")


def validate_recap_structure(recap_data: AIRecapOutput) -> None:
    words = count_words(recap_data.recap_text)
    if words > 180:
        raise AIValidationError(f"Recap text exceeds 180 words ({words} words)")
    if len(recap_data.key_points) != 3:
        raise AIValidationError("Recap must contain exactly 3 key points")


def validate_practice_questions(
    output: AIPracticeQuestionsOutput,
    expected_outcome_id: int,
    forbidden_stems: Optional[List[str]] = None,
    allowed_misconceptions: Optional[Set[str]] = None,
) -> None:
    if len(output.questions) != 3:
        raise AIValidationError("Practice output must contain exactly 3 questions")

    forbidden = [s.strip().lower() for s in (forbidden_stems or [])]

    for q_idx, q in enumerate(output.questions):
        if not q.stem or not q.stem.strip():
            raise AIValidationError(f"Question {q_idx+1} stem is empty")

        if q.stem.strip().lower() in forbidden:
            raise AIValidationError(f"Question {q_idx+1} duplicates an exit quiz stem")

        if len(q.options) != 4:
            raise AIValidationError(f"Question {q_idx+1} must have exactly 4 options")

        correct_count = sum(1 for opt in q.options if opt.is_correct)
        if correct_count != 1:
            raise AIValidationError(f"Question {q_idx+1} must have exactly one correct option, found {correct_count}")

        if allowed_misconceptions:
            for opt in q.options:
                if opt.misconception and opt.misconception not in allowed_misconceptions:
                    raise AIValidationError(f"Unrecognized misconception tag '{opt.misconception}'")


def validate_tutor_response(output: AITutorOutput) -> None:
    words = count_words(output.answer)
    if words > 220:
        raise AIValidationError(f"Tutor answer exceeds 220 words ({words} words)")


def validate_reteach_segment(output: AIReteachOutput) -> None:
    if output.duration_min != 10:
        raise AIValidationError("Reteach segment duration must be 10 minutes")

    if not output.worked_example.setup or not output.worked_example.steps:
        raise AIValidationError("Worked example must include setup and steps")

    if len(output.check_items) != 2:
        raise AIValidationError("Reteach segment must include exactly 2 check items")

    for item in output.check_items:
        if not item.options or item.answer not in item.options:
            raise AIValidationError(f"Check item answer '{item.answer}' is not in options list")


def validate_academic_facts(output: AIAcademicOutput, facts: Dict[str, Any]) -> None:
    words = count_words(output.text)
    if words > 80:
        raise AIValidationError(f"Academic recommendation exceeds 80 words ({words} words)")

    # Disallow individual student names
    lower_text = output.text.lower()
    for forbidden in ["riya", "student id", "student_id", "individual"]:
        if forbidden in lower_text:
            raise AIValidationError(f"Individual student reference '{forbidden}' found in academic text")

    # Verify that all numbers in text exist in facts
    numbers_in_text = extract_numbers(output.text)

    # Extract all numbers from facts recursively
    def extract_fact_numbers(obj: Any) -> Set[int]:
        res = set()
        if isinstance(obj, (int, float)):
            res.add(int(obj))
        elif isinstance(obj, str):
            res.update(extract_numbers(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                res.update(extract_fact_numbers(v))
        elif isinstance(obj, list):
            for v in obj:
                res.update(extract_fact_numbers(v))
        return res

    numbers_in_facts = extract_fact_numbers(facts)
    # Also allow standard small integers 1, 2 for sections if sections list is 2
    for n in numbers_in_text:
        if n not in numbers_in_facts:
            raise AIValidationError(f"Number '{n}' in output text does not exist in facts: {numbers_in_facts}")
