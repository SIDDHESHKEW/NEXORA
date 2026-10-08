"""Edge case tests: duplicate idempotency, foreign questions, tutor lock, and lesson editing locks."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_quiz_submission_idempotency(client: AsyncClient, teacher_auth, student_auth):
    """Verify duplicate submission with same idempotency key returns stored result with duplicate=true."""
    t_headers = teacher_auth
    s_headers = student_auth

    # Reset
    await client.post("/api/demo/reset", headers=t_headers)

    # Setup lesson & session
    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    lid = gen_res.json()["id"]
    await client.post(f"/api/lessons/{lid}/review", headers=t_headers)
    await client.post(f"/api/lessons/{lid}/approve", headers=t_headers)
    await client.post(f"/api/lessons/{lid}/publish", headers=t_headers)

    sess_res = await client.post("/api/sessions/start", json={"lesson_id": lid, "section_id": 1}, headers=t_headers)
    sid = sess_res.json()["session_id"]
    await client.post(f"/api/sessions/{sid}/quiz/start", headers=t_headers)
    await client.post(f"/api/sessions/{sid}/join", headers=s_headers)

    # First submission via autofill
    res1 = await client.post("/api/demo/autofill-quiz", json={"session_id": sid}, headers=s_headers)
    assert res1.status_code == 200
    assert res1.json()["duplicate"] is False

    # Second submission with same idempotency key directly
    res2 = await client.post(
        "/api/quiz/submit",
        json={
            "context": "EXIT_QUIZ",
            "session_id": sid,
            "idempotency_key": f"demo-autofill-{sid}-{s_headers.student.id}",
            "answers": [
                {"question_id": 1, "option_id": 1},
                {"question_id": 2, "option_id": 5},
                {"question_id": 3, "option_id": 9},
                {"question_id": 4, "option_id": 13},
                {"question_id": 5, "option_id": 17},
            ],
        },
        headers=s_headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate"] is True


@pytest.mark.asyncio
async def test_tutor_lock_during_open_quiz(client: AsyncClient, teacher_auth, student_auth):
    """Verify tutor returns 423 QUIZ_IN_PROGRESS while student's exit quiz is OPEN."""
    t_headers = teacher_auth
    s_headers = student_auth

    await client.post("/api/demo/reset", headers=t_headers)

    # Start session and open quiz
    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    lid = gen_res.json()["id"]
    await client.post(f"/api/lessons/{lid}/review", headers=t_headers)
    await client.post(f"/api/lessons/{lid}/approve", headers=t_headers)
    await client.post(f"/api/lessons/{lid}/publish", headers=t_headers)

    sess_res = await client.post("/api/sessions/start", json={"lesson_id": lid, "section_id": 1}, headers=t_headers)
    sid = sess_res.json()["session_id"]
    await client.post(f"/api/sessions/{sid}/quiz/start", headers=t_headers)
    await client.post(f"/api/sessions/{sid}/join", headers=s_headers)

    # Student attempts to ask AI Tutor during active quiz
    tutor_res = await client.post(
        "/api/tutor/ask",
        json={"question": "What is the answer to question 4?"},
        headers=s_headers,
    )
    assert tutor_res.status_code == 423
    assert tutor_res.json()["error"]["code"] == "QUIZ_IN_PROGRESS"


@pytest.mark.asyncio
async def test_cannot_edit_approved_lesson(client: AsyncClient, teacher_auth):
    """Verify editing a block in an APPROVED lesson returns 409 INVALID_STATUS_TRANSITION."""
    t_headers = teacher_auth

    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    lid = gen_res.json()["id"]
    await client.post(f"/api/lessons/{lid}/review", headers=t_headers)
    await client.post(f"/api/lessons/{lid}/approve", headers=t_headers)

    # Attempt to edit block after approval
    patch_res = await client.patch(
        f"/api/lessons/{lid}/blocks/1",
        json={"title": "Unauthorized Title Edit"},
        headers=t_headers,
    )
    assert patch_res.status_code == 409
    assert patch_res.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_foreign_option_rejected(client: AsyncClient, teacher_auth, student_auth):
    """Verify submitting an option that does not belong to the question returns 422."""
    t_headers = teacher_auth
    s_headers = student_auth

    sess_res = await client.post("/api/sessions/start", json={"lesson_id": 1, "section_id": 1}, headers=t_headers)
    sid = sess_res.json()["session_id"]
    await client.post(f"/api/sessions/{sid}/quiz/start", headers=t_headers)
    await client.post(f"/api/sessions/{sid}/join", headers=s_headers)

    # Submit question 1 with option 99999
    res = await client.post(
        "/api/quiz/submit",
        json={
            "context": "EXIT_QUIZ",
            "session_id": sid,
            "idempotency_key": "bad-option-test",
            "answers": [
                {"question_id": 1, "option_id": 99999},
            ],
        },
        headers=s_headers,
    )
    assert res.status_code in [422, 404]
