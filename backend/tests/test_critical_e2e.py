"""Authoritative Critical End-to-End Acceptance Test (Section 40)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_conference_demonstrator_loop(client: AsyncClient):
    """Execute the full 8-step conference intelligence loop and verify exact computed metrics."""

    # 1. Reset demo state
    # First login as teacher
    t_login = await client.post("/api/auth/demo-login", json={"role": "TEACHER"})
    assert t_login.status_code == 200
    t_token = t_login.json()["access_token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}

    reset_res = await client.post("/api/demo/reset", headers=t_headers)
    assert reset_res.status_code == 200

    # 2. Teacher generates lesson for Neural Networks (topic_id=1)
    gen_res = await client.post("/api/lessons/generate", json={"topic_id": 1}, headers=t_headers)
    assert gen_res.status_code == 201
    lesson_data = gen_res.json()
    lesson_id = lesson_data["id"]
    assert lesson_data["status"] == "DRAFT"

    # 3. Review lesson
    rev_res = await client.post(f"/api/lessons/{lesson_id}/review", headers=t_headers)
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "REVIEWED"

    # 4. Approve lesson
    app_res = await client.post(f"/api/lessons/{lesson_id}/approve", headers=t_headers)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # 5. Publish lesson
    pub_res = await client.post(f"/api/lessons/{lesson_id}/publish", headers=t_headers)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "PUBLISHED"

    # 6. Start Classroom Session (section_id=1, 5-A)
    sess_res = await client.post("/api/sessions/start", json={"lesson_id": lesson_id, "section_id": 1}, headers=t_headers)
    assert sess_res.status_code == 201
    session_data = sess_res.json()
    session_id = session_data["session_id"]

    # Advance slides
    slide_res = await client.post(f"/api/sessions/{session_id}/slide", json={"action": "NEXT"}, headers=t_headers)
    assert slide_res.status_code == 200

    # 7. Student Login (Riya)
    s_login = await client.post("/api/auth/demo-login", json={"role": "STUDENT"})
    assert s_login.status_code == 200
    s_token = s_login.json()["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}
    student_id = s_login.json()["user"]["student_id"]

    # 8. Student Joins Session
    join_res = await client.post(f"/api/sessions/{session_id}/join", headers=s_headers)
    assert join_res.status_code == 200

    # 9. Teacher starts exit quiz
    quiz_start_res = await client.post(f"/api/sessions/{session_id}/quiz/start", headers=t_headers)
    assert quiz_start_res.status_code == 200
    assert quiz_start_res.json()["quiz"]["status"] == "OPEN"

    # 10. Student submits quiz answers (autofill scripted path: Q1-Q3 correct, Q4-Q5 wrong)
    autofill_res = await client.post("/api/demo/autofill-quiz", json={"session_id": session_id}, headers=s_headers)
    assert autofill_res.status_code == 200
    quiz_result = autofill_res.json()
    assert quiz_result["score"]["correct"] == 3
    assert quiz_result["score"]["total"] == 5

    # 11. Teacher closes exit quiz
    quiz_close_res = await client.post(f"/api/sessions/{session_id}/quiz/close", headers=t_headers)
    assert quiz_close_res.status_code == 200

    # 12. ASSERTIONS:
    # A. Live Student Mastery
    mastery_res = await client.get(f"/api/students/{student_id}/mastery", headers=s_headers)
    assert mastery_res.status_code == 200
    mastery_data = mastery_res.json()

    lo_map = {item["outcome"]["code"]: item for item in mastery_data["items"]}
    assert lo_map["LO1"]["percent"] == 88
    assert lo_map["LO1"]["status"] == "STRONG"
    assert lo_map["LO2"]["percent"] == 74
    assert lo_map["LO2"]["status"] == "STRONG"
    assert lo_map["LO3"]["percent"] == 81
    assert lo_map["LO3"]["status"] == "STRONG"
    assert lo_map["LO4"]["percent"] == 41
    assert lo_map["LO4"]["status"] == "WEAK"
    assert mastery_data["overall_percent"] == 71

    # B. Student Recommendations (GAP_SUPPORT on LO4)
    rec_res = await client.get(f"/api/students/{student_id}/recommendations", headers=s_headers)
    assert rec_res.status_code == 200
    recs = rec_res.json()
    assert len(recs) >= 1
    lo4_rec = next((r for r in recs if r["outcome"]["code"] == "LO4"), None)
    assert lo4_rec is not None
    assert lo4_rec["type"] == "GAP_SUPPORT"

    # C. Student Skill Passport
    skill_res = await client.get(f"/api/students/{student_id}/skills", headers=s_headers)
    assert skill_res.status_code == 200
    skills_map = {s["name"]: s for s in skill_res.json()["skills"]}
    assert skills_map["Neural Networks"]["level"] == "DEVELOPING"
    assert skills_map["Deep Learning"]["level"] == "RECOMMENDED_NEXT"

    # D. Teacher Intelligence Insights for Section 5-A (section_id=1)
    teacher_insights_res = await client.get("/api/classes/1/insights", headers=t_headers)
    assert teacher_insights_res.status_code == 200
    t_insights = teacher_insights_res.json()
    lo4_insight = next(o for o in t_insights["outcomes"] if o["code"] == "LO4")
    assert lo4_insight["warning"] is True
    assert lo4_insight["weak_count"] == 35
    assert lo4_insight["weak_share_pct"] == 61
    assert t_insights["support_summary"]["students_needing_support"] == 35

    # E. Admin Recurring Gaps
    a_login = await client.post("/api/auth/demo-login", json={"role": "ADMIN"})
    assert a_login.status_code == 200
    a_token = a_login.json()["access_token"]
    a_headers = {"Authorization": f"Bearer {a_token}"}

    admin_gaps_res = await client.get("/api/admin/gaps", headers=a_headers)
    assert admin_gaps_res.status_code == 200
    admin_gaps = admin_gaps_res.json()
    assert len(admin_gaps) >= 1
    lo4_gap = next(g for g in admin_gaps if g["outcome"]["code"] == "LO4")
    assert lo4_gap["recurring"] is True
    sec_map = {s["name"]: s["weak_share_pct"] for s in lo4_gap["sections"]}
    assert sec_map["5-A"] == 61
    assert sec_map["5-B"] == 54
    assert lo4_gap["combined_weak_share_pct"] == 58

    # F. Demo Intelligence Loop State
    demo_state_res = await client.get("/api/demo/state")
    assert demo_state_res.status_code == 200
    loop_data = demo_state_res.json()["loop"]
    assert loop_data["teach"] is True
    assert loop_data["learn"] is True
    assert loop_data["assess"] is True
    assert loop_data["understand"] is True
    assert loop_data["personalize"] is True
    assert loop_data["support_teacher"] is True
    assert loop_data["inform_university"] is True
