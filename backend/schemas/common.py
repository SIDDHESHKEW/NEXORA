"""Common schemas: errors, users, config, health."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    issue: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: List[ErrorDetail] = Field(default_factory=list)
    trace_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    student_id: Optional[int] = None
    teacher_id: Optional[int] = None
    section_id: Optional[int] = None


class LoginRequest(BaseModel):
    role: str = Field(..., description="STUDENT | TEACHER | ADMIN")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ConfigResponse(BaseModel):
    thresholds: Dict[str, int] = Field(default_factory=lambda: {"strong": 70, "developing": 50})
    status_labels: Dict[str, Dict[str, str]] = Field(
        default_factory=lambda: {
            "student": {"STRONG": "Strong", "DEVELOPING": "Developing", "WEAK": "Needs Attention"},
            "staff": {"STRONG": "Strong", "DEVELOPING": "Developing", "WEAK": "Weak"},
        }
    )
    demo: Dict[str, Any] = Field(
        default_factory=lambda: {
            "allow_audience_join": False,
            "ai_mode": "Academic Assistant",
        }
    )
    university: str = "Scope Global Skills University (SGSU)"


class HealthResponse(BaseModel):
    status: str = "ok"
    db: bool = True
    ai: str = "fallback"  # configured | fallback
    seed_health: Dict[str, Any] = Field(default_factory=dict)
