"""Unit tests for the centralized AI Gateway and deterministic fallbacks."""

import pytest
from backend.services.ai_gateway import ai_gateway
from backend.models.governance import AIInteraction
from backend.models.curriculum import LearningOutcome
from backend.models.content import Source


@pytest.mark.asyncio
async def test_ai_gateway_all_six_functions_fallback(db_session):
    """Verify all six AI functions execute seamlessly with deterministic fallbacks."""
    lo4 = db_session.query(LearningOutcome).filter(LearningOutcome.code == "LO4").first()
    source = db_session.query(Source).first()

    # 1. generate_lesson
    lesson_out, mode_l = await ai_gateway.generate_lesson(
        topic="Neural Networks",
        outcomes=["LO1", "LO2", "LO3", "LO4"],
        source=source.content if source else "Course content",
        scope="FULL",
        user_id=1,
        role="TEACHER",
        db=db_session,
    )
    assert mode_l == "FALLBACK"
    assert len(lesson_out.blocks) >= 10

    # 2. generate_explanation (recap)
    recap_out, mode_r = await ai_gateway.generate_explanation(
        outcome=lo4.statement,
        misconception="Applying output error directly to hidden layer weights",
        source=source.content if source else "Course content",
        user_id=1,
        role="STUDENT",
        db=db_session,
    )
    assert mode_r == "FALLBACK"
    assert len(recap_out.key_points) == 3

    # 3. generate_practice_questions
    practice_out, mode_p = await ai_gateway.generate_practice_questions(
        outcome=lo4,
        misconceptions=["mc_output_error_hidden_weights"],
        source=source.content if source else "Course content",
        n=3,
        user_id=1,
        role="STUDENT",
        db=db_session,
    )
    assert mode_p == "FALLBACK"
    assert len(practice_out.questions) == 3

    # 4. generate_tutor_response
    tutor_out, mode_t = await ai_gateway.generate_tutor_response(
        question="Why can we not update hidden weights using output error directly?",
        outcome=lo4.statement,
        source=source.content if source else "Course content",
        user_id=1,
        role="STUDENT",
        db=db_session,
    )
    assert mode_t == "FALLBACK"
    assert len(tutor_out.text.split()) <= 220

    # 5. generate_reteach_segment
    facts_reteach = {
        "weak_count": 35,
        "weak_share_pct": 61,
        "top_misconception": "Direct output error attribution",
    }
    reteach_out, mode_ret = await ai_gateway.generate_reteach_segment(
        outcome=lo4.statement,
        facts=facts_reteach,
        source=source.content if source else "Course content",
        user_id=1,
        role="TEACHER",
        db=db_session,
    )
    assert mode_ret == "FALLBACK"
    assert reteach_out.duration_min == 10
    assert len(reteach_out.check_items) == 2

    # 6. generate_academic_recommendation
    facts_admin = {
        "course": "Artificial Intelligence",
        "combined_weak_share_pct": 58,
        "total_respondents": 114,
        "prerequisite_chain_rule_pct": 52,
    }
    admin_out, mode_a = await ai_gateway.generate_academic_recommendation(
        facts=facts_admin,
        user_id=1,
        role="ADMIN",
        db=db_session,
    )
    assert mode_a == "FALLBACK"
    assert "58" in admin_out.text

    # Verify AI interactions logged
    logs = db_session.query(AIInteraction).all()
    assert len(logs) >= 6
    assert all(log.status == "FALLBACK" for log in logs)
