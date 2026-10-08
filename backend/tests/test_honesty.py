"""Honesty test (Section 41): alternate answer path proving dynamic computation."""

import pytest
from httpx import AsyncClient
from backend.models.assessment import Question


@pytest.mark.asyncio
async def test_honesty_alternate_answer_path(client: AsyncClient, db_session):
    """Run alternate path: Q1-Q3 correct, Q4 correct, Q5 wrong.

    Expected:
    - LO4 = 63 DEVELOPING
    - 5-A weak count = 34
    - 5-A weak share = 60%
    - Student GAP_SUPPORT recommendation NOT created
    - Teacher LO4 warning remains TRUE (60% >= 40%)
    """
    # 1. Reset demo state
    t_login = await client.post("/api/auth/demo-login", json={"role": "TEACHER"})
    t_token = t_login.json()["access_token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}
    await client.post("/api/demo/reset", headers=t_headers)

    # 2. Setup lesson and live session
    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    lesson_id = gen_res.json()["id"]
    await client.post(f"/api/lessons/{lesson_id}/review", headers=t_headers)
    await client.post(f"/api/lessons/{lesson_id}/approve", headers=t_headers)
    await client.post(f"/api/lessons/{lesson_id}/publish", headers=t_headers)

    sess_res = await client.post("/api/sessions/start", json={"lesson_id": lesson_id, "section_id": 1}, headers=t_headers)
    session_id = sess_res.json()["session_id"]
    await client.post(f"/api/sessions/{session_id}/quiz/start", headers=t_headers)

    # 3. Student joins
    s_login = await client.post("/api/auth/demo-login", json={"role": "STUDENT"})
    s_token = s_login.json()["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}
    student_id = s_login.json()["user"]["student_id"]
    await client.post(f"/api/sessions/{session_id}/join", headers=s_headers)

    # 4. Formulate answers: Q1, Q2, Q3 correct, Q4 CORRECT, Q5 wrong
    questions = db_session.query(Question).filter(Question.purpose == "EXIT_QUIZ").order_by(Question.seq.asc()).all()
    answers = []
    for q in questions[:5]:
        if q.seq in [1, 2, 3, 4]:
            correct_opt = next(o for o in q.options if o.is_correct)
            answers.append({"question_id": q.id, "option_id": correct_opt.id})
        else:
            wrong_opt = next(o for o in q.options if not o.is_correct)
            answers.append({"question_id": q.id, "option_id": wrong_opt.id})

    # Submit quiz
    sub_res = await client.post(
        "/api/quiz/submit",
        json={
            "context": "EXIT_QUIZ",
            "session_id": session_id,
            "idempotency_key": "honesty-test-submission",
            "answers": answers,
        },
        headers=s_headers,
    )
    assert sub_res.status_code == 200

    # 5. Check live student mastery
    mastery_res = await client.get(f"/api/students/{student_id}/mastery", headers=s_headers)
    assert mastery_res.status_code == 200
    lo_map = {item["outcome"]["code"]: item for item in mastery_res.json()["items"]}
    assert lo_map["LO4"]["percent"] == 63
    assert lo_map["LO4"]["status"] == "DEVELOPING"

    # 6. Check student recommendations: GAP_SUPPORT should NOT exist for LO4
    recs_res = await client.get(f"/api/students/{student_id}/recommendations", headers=s_headers)
    assert recs_res.status_code == 200
    recs = recs_res.json()
    lo4_rec = next((r for r in recs if r["outcome"]["code"] == "LO4" and r["type"] == "GAP_SUPPORT"), None)
    assert lo4_rec is None, "Student gap should not exist when LO4 is DEVELOPING"

    # 7. Check teacher insights: weak count remains 34, weak share is 60%, warning remains TRUE
    insights_res = await client.get("/api/classes/1/insights", headers=t_headers)
    assert insights_res.status_code == 200
    t_insights = insights_res.json()
    lo4_insight = next(o for o in t_insights["outcomes"] if o["code"] == "LO4")
    assert lo4_insight["weak_count"] == 34
    assert lo4_insight["weak_share_pct"] == 60
    assert lo4_insight["warning"] is True
