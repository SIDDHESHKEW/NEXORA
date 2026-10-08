"""Classroom and polling lifecycle tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_classroom_session_and_polling_lifecycle(client: AsyncClient, teacher_auth, student_auth):
    """Verify classroom lifecycle: session start, slide navigation, prompts, polls, quiz, and report."""
    t_headers = teacher_auth
    s_headers = student_auth

    # Reset state
    await client.post("/api/demo/reset", headers=t_headers)

    # 1. Generate & publish lesson
    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    lesson_id = gen_res.json()["id"]
    await client.post(f"/api/lessons/{lesson_id}/review", headers=t_headers)
    await client.post(f"/api/lessons/{lesson_id}/approve", headers=t_headers)
    await client.post(f"/api/lessons/{lesson_id}/publish", headers=t_headers)

    # 2. Start session (SE01)
    sess_res = await client.post("/api/sessions/start", json={"lesson_id": lesson_id, "section_id": 1}, headers=t_headers)
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 3. Slide navigation (SE04)
    slide_res = await client.post(f"/api/sessions/{session_id}/slide", json={"action": "NEXT"}, headers=t_headers)
    assert slide_res.status_code == 200
    assert slide_res.json()["current_slide_index"] == 1

    # 4. Post prompt (SE05)
    prompt_res = await client.post(
        f"/api/sessions/{session_id}/prompts",
        json={"text": "Consider the chain rule: how does error propagate?"},
        headers=t_headers,
    )
    assert prompt_res.status_code == 201

    # 5. Student active session query (SE10) and Join (SE02)
    active_res = await client.get("/api/sessions/active", headers=s_headers)
    assert active_res.status_code == 200
    assert active_res.json()["session_id"] == session_id

    join_res = await client.post(f"/api/sessions/{session_id}/join", headers=s_headers)
    assert join_res.status_code == 200

    # 6. Open Poll (P01)
    poll_res = await client.post("/api/polls", json={"session_id": session_id, "question_id": 1}, headers=t_headers)
    assert poll_res.status_code == 201
    poll_id = poll_res.json()["poll_id"]

    # 7. Student responds to poll (P02)
    # Get options
    poll_q = poll_res.json()["question"]
    opt_id = poll_q["options"][0]["id"]
    resp_res = await client.post(
        f"/api/polls/{poll_id}/respond",
        json={"option_id": opt_id, "idempotency_key": "poll-sub-1"},
        headers=s_headers,
    )
    assert resp_res.status_code == 200
    assert resp_res.json()["accepted"] is True

    # Duplicate poll answer rejected (409 ALREADY_ANSWERED)
    dup_res = await client.post(
        f"/api/polls/{poll_id}/respond",
        json={"option_id": opt_id, "idempotency_key": "poll-sub-2"},
        headers=s_headers,
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "ALREADY_ANSWERED"

    # 8. Close poll (P03)
    close_poll = await client.post(f"/api/polls/{poll_id}/close", headers=t_headers)
    assert close_poll.status_code == 200

    # 9. Poll results (P04)
    results_res = await client.get(f"/api/polls/{poll_id}/results", headers=t_headers)
    assert results_res.status_code == 200
    assert results_res.json()["total"] == 1

    # 10. End session (SE08) and Session Report (SE09)
    end_res = await client.post(f"/api/sessions/{session_id}/end", headers=t_headers)
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "ENDED"

    report_res = await client.get(f"/api/sessions/{session_id}/report", headers=t_headers)
    assert report_res.status_code == 200
    rep_data = report_res.json()
    assert rep_data["session"]["status"] == "ENDED"
    assert rep_data["attendance"]["present"] >= 1
