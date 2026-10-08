"""Security, JWT tokens, authentication dependencies, and authorization guards."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
from jose import JWTError, jwt
from fastapi import Depends, Header, WebSocket, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.errors import (
    UnauthenticatedError,
    ForbiddenRoleError,
    ForbiddenScopeError,
)
from backend.core.db import get_db


class TokenPayload(BaseModel):
    sub: str
    role: str
    user_id: int
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    section_id: Optional[int] = None
    exp: Optional[Any] = None

    @classmethod
    def from_claims(cls, claims: Dict[str, Any]) -> "TokenPayload":
        return cls(
            sub=str(claims["sub"]),
            role=str(claims.get("role", "")),
            user_id=int(claims["sub"]),
            student_id=claims.get("student_id"),
            teacher_id=claims.get("teacher_id"),
            section_id=claims.get("section_id"),
            exp=claims.get("exp"),
        )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        val = getattr(self, item, None)
        return val if val is not None else default


def create_access_token(
    user_id: int,
    role: str,
    student_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    section_id: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create signed HS256 JWT access token with 8-hour default TTL."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_TTL_HOURS)

    claims: Dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    if student_id is not None:
        claims["student_id"] = student_id
    if teacher_id is not None:
        claims["teacher_id"] = teacher_id
    if section_id is not None:
        claims["section_id"] = section_id

    return jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as err:
        raise UnauthenticatedError("Invalid or expired authentication token") from err


def get_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        raise UnauthenticatedError("Authorization header required")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthenticatedError("Invalid authorization scheme. Use 'Bearer <token>'")
    return parts[1]


def get_current_user_claims(token: str = Depends(get_token_from_header)) -> Dict[str, Any]:
    """Extract claims directly from valid JWT."""
    return decode_token(token)


def get_current_token_payload(token: str = Depends(get_token_from_header)) -> TokenPayload:
    """Extract TokenPayload directly from valid JWT."""
    claims = decode_token(token)
    return TokenPayload.from_claims(claims)


def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[TokenPayload]:
    """Optionally resolve authenticated user if Authorization header is provided."""
    if not authorization:
        return None
    try:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            claims = decode_token(parts[1])
            return TokenPayload.from_claims(claims)
    except Exception:
        pass
    return None


def get_current_user(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
) -> Any:
    """Resolve database User model from JWT claims."""
    from backend.models.curriculum import User
    user_id = int(claims["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UnauthenticatedError("User belonging to token does not exist")
    return user


def require_role(*allowed_roles: Any):
    """Enforce that authenticated user has one of the specified roles."""
    roles = []
    for r in allowed_roles:
        if isinstance(r, (list, tuple, set)):
            roles.extend(r)
        else:
            roles.append(r)
    roles_set = set(roles)

    def role_checker(claims: Dict[str, Any] = Depends(get_current_user_claims)) -> TokenPayload:
        user_role = claims.get("role")
        if user_role not in roles_set:
            raise ForbiddenRoleError(f"Action requires one of roles: {', '.join(roles_set)}")
        return TokenPayload.from_claims(claims)
    return role_checker


def assert_student_self(claims: Union[Dict[str, Any], TokenPayload], target_student_id: int, db: Optional[Session] = None) -> None:
    """Ensure student only accesses their own student resources."""
    role = claims.get("role")
    if role == "STUDENT":
        token_student_id = claims.get("student_id")
        if token_student_id is None or int(token_student_id) != target_student_id:
            raise ForbiddenScopeError("Students may only access their own data")
    elif role == "TEACHER" and db is not None:
        from backend.models.curriculum import Student, ClassSection
        student = db.query(Student).filter(Student.id == target_student_id).first()
        if not student:
            raise ForbiddenScopeError("Target student not found")
        teacher_id = claims.get("teacher_id")
        section = db.query(ClassSection).filter(
            ClassSection.id == student.section_id,
            ClassSection.teacher_id == teacher_id,
        ).first()
        if not section:
            raise ForbiddenScopeError("Teacher does not instruct this student's section")
    elif role != "TEACHER" and role != "ADMIN":
        raise ForbiddenRoleError("Insufficient privileges")


def assert_teacher_owns_session(claims: Union[Dict[str, Any], TokenPayload], session_obj: Any) -> None:
    """Ensure teacher owns the session."""
    if claims.get("role") != "TEACHER":
        raise ForbiddenRoleError("Only teachers may manage classroom sessions")
    teacher_id = claims.get("teacher_id")
    if teacher_id is None or session_obj.teacher_id != int(teacher_id):
        raise ForbiddenScopeError("Teacher does not own this classroom session")


def assert_teacher_owns_section(claims: Union[Dict[str, Any], TokenPayload], section_id: int, db: Session) -> None:
    """Ensure teacher owns the section."""
    if claims.get("role") != "TEACHER":
        raise ForbiddenRoleError("Only teachers may manage sections")
    teacher_id = claims.get("teacher_id")
    from backend.models.curriculum import ClassSection
    section = db.query(ClassSection).filter(
        ClassSection.id == section_id,
        ClassSection.teacher_id == teacher_id,
    ).first()
    if not section:
        raise ForbiddenScopeError("Teacher does not own this class section")
