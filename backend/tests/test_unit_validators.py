"""Unit tests for content validators and lesson state machine."""

import pytest
from backend.services.ai_validators import (
    validate_lesson_structure,
    validate_academic_facts,
    AIValidationError,
)
from backend.services.ai_schemas import (
    AILessonOutput,
    AILessonBlock,
    AIAcademicOutput,
)
from backend.modules.content.lesson_state import validate_status_transition, can_edit_lesson_blocks


def test_lesson_output_validation_success():
    """Verify standard valid lesson structure."""
    blocks = [
        AILessonBlock(seq=1, type="TITLE", title="Neural Networks", content={"text": "Intro"}),
        AILessonBlock(seq=2, type="OBJECTIVES", title="Objectives", content={"items": ["LO1", "LO2", "LO3", "LO4"]}),
        AILessonBlock(seq=3, type="EXPLANATION", outcome_ids=[1], content={"text": "LO1"}),
        AILessonBlock(seq=4, type="EXPLANATION", outcome_ids=[2], content={"text": "LO2"}),
        AILessonBlock(seq=5, type="EXPLANATION", outcome_ids=[3], content={"text": "LO3"}),
        AILessonBlock(seq=6, type="EXPLANATION", outcome_ids=[4], content={"text": "LO4"}),
        AILessonBlock(seq=7, type="KEY_CONCEPTS", content={"items": ["Weights", "Biases"]}),
        AILessonBlock(seq=8, type="EXAMPLE", outcome_ids=[4], content={"text": "Backprop example"}),
        AILessonBlock(seq=9, type="MISCONCEPTION", outcome_ids=[4], content={"text": "output error vs hidden-layer weight update"}),
        AILessonBlock(seq=10, type="QUICK_CHECK", outcome_ids=[4], content={"question": "What is it?", "answer": "Chain rule"}),
        AILessonBlock(seq=11, type="SOURCE", content={"citation": "Goodfellow et al. Deep Learning, MIT Press, 2016."}),
    ]
    lesson = AILessonOutput(title="Neural Networks", blocks=blocks)
    # Should not raise
    validate_lesson_structure(
        lesson,
        expected_outcome_ids=[1, 2, 3, 4],
        expected_citation="Goodfellow et al. Deep Learning, MIT Press, 2016.",
    )


def test_lesson_output_validation_wrong_citation():
    """Verify citation mismatch is rejected."""
    blocks = [
        AILessonBlock(seq=1, type="TITLE", content={"text": "Title"}),
        AILessonBlock(seq=2, type="OBJECTIVES", content={"items": []}),
        AILessonBlock(seq=3, type="EXPLANATION", outcome_ids=[1], content={"text": "E"}),
        AILessonBlock(seq=4, type="EXPLANATION", outcome_ids=[2], content={"text": "E"}),
        AILessonBlock(seq=5, type="EXPLANATION", outcome_ids=[3], content={"text": "E"}),
        AILessonBlock(seq=6, type="EXPLANATION", outcome_ids=[4], content={"text": "E"}),
        AILessonBlock(seq=7, type="KEY_CONCEPTS", content={"items": []}),
        AILessonBlock(seq=8, type="EXAMPLE", outcome_ids=[4], content={"text": "E"}),
        AILessonBlock(seq=9, type="MISCONCEPTION", outcome_ids=[4], content={"text": "output error vs hidden-layer weight update"}),
        AILessonBlock(seq=10, type="QUICK_CHECK", outcome_ids=[4], content={"question": "Q", "answer": "A"}),
        AILessonBlock(seq=11, type="SOURCE", content={"citation": "Wrong Random Citation"}),
    ]
    lesson = AILessonOutput(title="Title", blocks=blocks)
    with pytest.raises(AIValidationError) as exc_info:
        validate_lesson_structure(
            lesson,
            expected_outcome_ids=[1, 2, 3, 4],
            expected_citation="Official SGSU Textbook",
        )
    assert "citation mismatch" in str(exc_info.value).lower()


def test_academic_numbers_validation():
    """Verify that numbers in academic output must be grounded in facts."""
    facts = {
        "course": "AI",
        "combined_weak_share_pct": 58,
        "total_respondents": 114,
        "prerequisite_chain_rule_pct": 52,
    }

    # Case 1: valid output using only numbers 58, 114, 52
    rec_valid = AIAcademicOutput(
        text="Across 114 students, 58 percent showed weakness in backpropagation, with 52 percent chain rule readiness."
    )
    validate_academic_facts(rec_valid, facts)

    # Case 2: hallucinated number 95 appears
    rec_hallucinated = AIAcademicOutput(
        text="Across 114 students, 95 percent showed unexpected anomalies."
    )
    with pytest.raises(AIValidationError) as exc_info:
        validate_academic_facts(rec_hallucinated, facts)
    assert "95" in str(exc_info.value)


def test_lesson_state_machine_transitions():
    """Verify DRAFT -> REVIEWED -> APPROVED -> PUBLISHED transitions."""
    assert validate_status_transition("DRAFT", "REVIEWED") is True
    assert validate_status_transition("REVIEWED", "APPROVED") is True
    assert validate_status_transition("APPROVED", "PUBLISHED") is True

    # Invalid skips
    assert validate_status_transition("DRAFT", "APPROVED") is False
    assert validate_status_transition("DRAFT", "PUBLISHED") is False
    assert validate_status_transition("REVIEWED", "PUBLISHED") is False

    # Editing lock
    assert can_edit_lesson_blocks("DRAFT") is True
    assert can_edit_lesson_blocks("REVIEWED") is True
    assert can_edit_lesson_blocks("APPROVED") is False
    assert can_edit_lesson_blocks("PUBLISHED") is False
