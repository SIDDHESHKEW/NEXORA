"""API and security authorization tests."""

import pytest
from httpx import AsyncClient
from backend.models.curriculum import Student


@pytest.mark.asyncio
async def test_auth_unauthenticated_requests(client: AsyncClient):
    """Verify that protected routes return 401 UNAUTHENTICATED."""
    endpoints = [
        "/api/auth/me",
        "/api/lessons",
        "/api/sessions/active",
        "/api/students/1/mastery",
        "/api/admin/overview",
    ]
    for ep in endpoints:
        resp = await client.get(ep)
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_role_enforcement(client: AsyncClient, student_auth, teacher_auth):
    """Verify role-based permission boundaries (403 FORBIDDEN_ROLE)."""
    # Student cannot access admin endpoints
    resp_student_admin = await client.get("/api/admin/overview", headers=student_auth)
    assert resp_student_admin.status_code == 403
    assert resp_student_admin.json()["error"]["code"] == "FORBIDDEN_ROLE"

    # Teacher cannot access admin endpoints
    resp_teacher_admin = await client.get("/api/admin/overview", headers=teacher_auth)
    assert resp_teacher_admin.status_code == 403
    assert resp_teacher_admin.json()["error"]["code"] == "FORBIDDEN_ROLE"


@pytest.mark.asyncio
async def test_student_scope_isolation(client: AsyncClient, student_auth, db_session):
    """Verify student A cannot read student B's data (403 FORBIDDEN_SCOPE)."""
    riya = student_auth.student
    other_student = db_session.query(Student).filter(Student.id != riya.id).first()
    assert other_student is not None

    # Riya tries to read another student's mastery
    resp = await client.get(f"/api/students/{other_student.id}/mastery", headers=student_auth)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN_SCOPE"


@pytest.mark.asyncio
async def test_admin_privacy_no_student_identifiers(client: AsyncClient, admin_auth):
    """Verify admin responses are aggregate-only and contain zero student identifiers or PII."""
    overview_resp = await client.get("/api/admin/overview", headers=admin_auth)
    assert overview_resp.status_code == 200
    ov_data = overview_resp.json()
    assert "student_id" not in ov_data
    assert "name" not in ov_data or ov_data.get("name") is None

    gaps_resp = await client.get("/api/admin/gaps", headers=admin_auth)
    assert gaps_resp.status_code == 200
    gaps_str = str(gaps_resp.json())
    assert "Riya" not in gaps_str
    assert "student_id" not in gaps_str


@pytest.mark.asyncio
async def test_questions_strip_answer_keys_for_students(client: AsyncClient, student_auth):
    """Verify practice questions for students never reveal is_correct."""
    # Generate practice set
    resp = await client.post(
        "/api/practice/generate",
        json={"outcome_id": 4},
        headers=student_auth,
    )
    assert resp.status_code == 201
    data = resp.json()
    for q in data["questions"]:
        for opt in q["options"]:
            assert "is_correct" not in opt
