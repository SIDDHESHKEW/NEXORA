"""Pytest fixtures, test database setup, and async HTTP client."""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_nexora.db"
os.environ["JWT_SECRET"] = "test-secret-key-32chars-minimum-length"
os.environ["AI_FORCE_FALLBACK"] = "true"

from backend.core.config import settings
from backend.core.db import Base, get_db
from backend.main import app
from backend.seed.seed_data import seed_database, validate_seed_integrity
from backend.core.security import create_access_token
from backend.models.curriculum import User, Student, Teacher, ClassSection

# Test SQLite Engine
TEST_DB_URL = "sqlite:///./test_nexora.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AuthHeaders(dict):
    def __init__(self, token: str, user=None, student=None, teacher=None):
        super().__init__({"Authorization": f"Bearer {token}"})
        self.token = token
        self.user = user
        self.student = student
        self.teacher = teacher


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables and seed initial database once for tests."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        seed_database(db)
        integrity = validate_seed_integrity(db)
        assert integrity["healthy"], f"Test DB seed integrity failed: {integrity}"
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_nexora.db"):
        try:
            os.remove("./test_nexora.db")
        except Exception:
            pass


@pytest.fixture
def db_session():
    """Provide a fresh DB session for each test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def override_get_db(db_session):
    """Override FastAPI get_db dependency to use test session."""
    def _override():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def client(override_get_db):
    """Async HTTP client for testing API routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def teacher_auth(db_session):
    teacher = db_session.query(Teacher).first()
    user = teacher.user
    token = create_access_token(
        user_id=user.id,
        role="TEACHER",
        teacher_id=teacher.id,
    )
    return AuthHeaders(token=token, teacher=teacher, user=user)


@pytest.fixture
def student_auth(db_session):
    riya = db_session.query(Student).filter(Student.is_live == True).first()
    user = riya.user
    token = create_access_token(
        user_id=user.id,
        role="STUDENT",
        student_id=riya.id,
        section_id=riya.section_id,
    )
    return AuthHeaders(token=token, student=riya, user=user)


@pytest.fixture
def admin_auth(db_session):
    admin_user = db_session.query(User).filter(User.role == "ADMIN").first()
    token = create_access_token(
        user_id=admin_user.id,
        role="ADMIN",
    )
    return AuthHeaders(token=token, user=admin_user)
