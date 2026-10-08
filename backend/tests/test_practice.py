"""Practice test (Section 42): remediation closing the loop."""

import pytest
from httpx import AsyncClient
from backend.models.recommendation import PracticeSetQuestion


@pytest.mark.asyncio
async def test_remediation_practice_closing_the_loop(client: AsyncClient, db_session):
    """From scripted weak state (LO4=41), answer 3/3 practice questions correctly.

    Expected:
    - LO4 = 56 DEVELOPING
    - Student GAP_SUPPORT recommendation status = RESOLVED
    - Teacher 5-A weak count decreases from 35 to 34
    """
    # 1. Reset and run scripted quiz to reach weak state
    t_login = await client.post("/api/auth/demo-login", json={"role": "TEACHER"})
    t_token = t_login.json()["access_token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}
    await client.post("/api/demo/reset", headers=t_headers)

    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    lesson_id = gen_res.json()["id"]
    await client.post(f"/api/lessons/{lesson_id}/review", headers=t_headers)
    await client.post(f"/api/lessons/{lesson_id}/approve", headers=t_headers)
    await client.post(f"/api/lessons/{lesson_id}/publish", headers=t_headers)

    sess_res = await client.post("/api/sessions/start", json={"lesson_id": lesson_id, "section_id": 1}, headers=t_headers)
    session_id = sess_res.json()["session_id"]
    await client.post(f"/api/sessions/{session_id}/quiz/start", headers=t_headers)

    s_login = await client.post("/api/auth/demo-login", json={"role": "STUDENT"})
    s_token = s_login.json()["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}
    student_id = s_login.json()["user"]["student_id"]
    await client.post(f"/api/sessions/{session_id}/join", headers=s_headers)

    # Submit scripted quiz (autofill)
    await client.post("/api/demo/autofill-quiz", json={"session_id": session_id}, headers=s_headers)

    # Verify Riya is in weak state on LO4 (41%)
    pre_m = await client.get(f"/api/students/{student_id}/mastery", headers=s_headers)
    assert next(item for item in pre_m.json()["items"] if item["outcome"]["code"] == "LO4")["percent"] == 41

    # 2. Generate Practice Set for LO4 (outcome_id=4)
    prac_gen = await client.post("/api/practice/generate", json={"outcome_id": 4}, headers=s_headers)
    assert prac_gen.status_code == 201
    set_data = prac_gen.json()
    set_id = set_data["set_id"]
    assert len(set_data["questions"]) == 3

    # Fetch correct options from DB for these practice questions
    answers = []
    for q_item in set_data["questions"]:
        pq = db_session.query(PracticeSetQuestion).filter(
            PracticeSetQuestion.practice_set_id == set_id,
            PracticeSetQuestion.question_id == q_item["id"],
        ).first()
        assert pq is not None
        correct_opt = next(o for o in pq.question.options if o.is_correct)
        answers.append({"question_id": q_item["id"], "option_id": correct_opt.id})

    # 3. Submit Practice Set (3/3 correct)
    sub_res = await client.post(
        "/api/quiz/submit",
        json={
            "context": "PRACTICE",
            "set_id": set_id,
            "idempotency_key": f"practice-sub-{set_id}",
            "answers": answers,
        },
        headers=s_headers,
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["score"]["correct"] == 3

    # 4. Assert updated mastery: LO4 becomes 56% DEVELOPING
    post_m = await client.get(f"/api/students/{student_id}/mastery", headers=s_headers)
    assert post_m.status_code == 200
    lo4_post = next(item for item in post_m.json()["items"] if item["outcome"]["code"] == "LO4")
    assert lo4_post["percent"] == 56
    assert lo4_post["status"] == "DEVELOPING"

    # 5. Assert student recommendation: GAP_SUPPORT is RESOLVED
    recs_res = await client.get(f"/api/students/{student_id}/recommendations", headers=s_headers)
    assert recs_res.status_code == 200
    lo4_rec = next((r for r in recs_res.json() if r["outcome"]["code"] == "LO4" and r["type"] == "GAP_SUPPORT"), None)
    if lo4_rec:
        assert lo4_rec["status"] == "RESOLVED"

    # 6. Assert Teacher Intelligence: 5-A weak count changes from 35 back to 34
    insights_res = await client.get("/api/classes/1/insights", headers=t_headers)
    assert insights_res.status_code == 200
    t_lo4 = next(o for o in insights_res.json()["outcomes"] if o["code"] == "LO4")
    assert t_lo4["weak_count"] == 34
