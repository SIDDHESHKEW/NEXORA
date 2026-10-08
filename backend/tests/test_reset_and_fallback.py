"""Reset idempotency test (Section 44) and AI fallback test (Section 43)."""

import pytest
from httpx import AsyncClient
from backend.seed.seed_data import validate_seed_integrity
from backend.models.curriculum import User, Course
from backend.models.assessment import Question
from backend.models.evidence import LearningEvent
from backend.models.recommendation import Recommendation
from backend.models.governance import AIInteraction


@pytest.mark.asyncio
async def test_demo_reset_three_consecutive_times(client: AsyncClient, db_session, teacher_auth):
    """Execute DEMO RESET 3 times consecutively and verify seed integrity and zero duplication."""
    for i in range(3):
        res = await client.post("/api/demo/reset", headers=teacher_auth)
        assert res.status_code == 200
        assert res.json()["reset"] is True

        # 1. Verify seed integrity
        integrity = validate_seed_integrity(db_session)
        assert integrity["healthy"] is True, f"Integrity failed on iteration {i+1}: {integrity['checks']}"

        # 2. Verify no duplication of core entities
        assert db_session.query(Course).count() == 1
        assert db_session.query(User).count() == 116  # 114 students + 1 teacher + 1 admin
        assert db_session.query(Question).count() >= 5

        # 3. Verify dynamic tables are clean
        assert db_session.query(LearningEvent).count() == 0
        assert db_session.query(Recommendation).count() == 0
        assert db_session.query(AIInteraction).count() == 0


@pytest.mark.asyncio
async def test_fallback_mode_resilience(client: AsyncClient, teacher_auth, student_auth):
    """Verify that with AI_FORCE_FALLBACK=true all AI endpoints return robust fallback content."""
    # 1. Generate lesson
    lesson_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=teacher_auth)
    assert lesson_res.status_code == 201
    assert lesson_res.json()["generation_mode"] == "FALLBACK"

    # 2. Ask Tutor
    tutor_res = await client.post(
        "/api/tutor/ask",
        json={"question": "What is backpropagation?"},
        headers=student_auth,
    )
    assert tutor_res.status_code == 200
    assert tutor_res.json()["mode"] == "FALLBACK"

    # 3. Teacher Reteach Segment
    reteach_res = await client.post(
        "/api/classes/1/reteach",
        json={"outcome_id": 4},
        headers=teacher_auth,
    )
    assert reteach_res.status_code == 200
    assert reteach_res.json()["generation_mode"] == "FALLBACK"
