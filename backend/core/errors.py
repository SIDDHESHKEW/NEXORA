"""Unified error definitions and handlers matching SGSU Platform API contract."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base application exception matching the contract error envelope."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[List[Dict[str, Any]]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.headers = headers or {}


# Standard HTTP / Business Error subclasses
class UnauthenticatedError(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code="UNAUTHENTICATED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenRoleError(AppError):
    def __init__(self, message: str = "User role not permitted for this action"):
        super().__init__(
            code="FORBIDDEN_ROLE",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ForbiddenScopeError(AppError):
    def __init__(self, message: str = "Access to requested resource scope is forbidden"):
        super().__init__(
            code="FORBIDDEN_SCOPE",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class NoActiveSessionError(AppError):
    def __init__(self, message: str = "No active classroom session found for this section"):
        super().__init__(
            code="NO_ACTIVE_SESSION",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class InvalidStatusTransitionError(AppError):
    def __init__(self, message: str = "Invalid workflow status transition"):
        super().__init__(
            code="INVALID_STATUS_TRANSITION",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class LessonNotPublishedError(AppError):
    def __init__(self, message: str = "Lesson must be published before starting a live session"):
        super().__init__(
            code="LESSON_NOT_PUBLISHED",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class SessionNotLiveError(AppError):
    def __init__(self, message: str = "Classroom session is not live"):
        super().__init__(
            code="SESSION_NOT_LIVE",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class QuizNotOpenError(AppError):
    def __init__(self, message: str = "Exit quiz is not currently open"):
        super().__init__(
            code="QUIZ_NOT_OPEN",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class AlreadyAnsweredError(AppError):
    def __init__(self, message: str = "Question or poll has already been answered"):
        super().__init__(
            code="ALREADY_ANSWERED",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class QuizInProgressError(AppError):
    def __init__(self, message: str = "AI Tutor is disabled while exit quiz is in progress"):
        super().__init__(
            code="QUIZ_IN_PROGRESS",
            message=message,
            status_code=423,  # Locked
        )


class RateLimitedError(AppError):
    def __init__(self, retry_after: int = 60, message: str = "Too many requests. Please wait."):
        super().__init__(
            code="RATE_LIMITED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
        )


class InternalServerError(AppError):
    def __init__(self, message: str = "An unexpected error occurred", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            code="INTERNAL",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def make_error_envelope(code: str, message: str, details: Optional[List[Dict[str, Any]]] = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "trace_id": trace_id or uuid.uuid4().hex[:12],
        }
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex[:12])
    content = make_error_envelope(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        trace_id=trace_id,
    )
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex[:12])
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []))
        details.append({"field": loc, "issue": err.get("msg", "Invalid value")})
    content = make_error_envelope(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
        trace_id=trace_id,
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex[:12])
    code = "INTERNAL"
    if exc.status_code == 401:
        code = "UNAUTHENTICATED"
    elif exc.status_code == 403:
        code = "FORBIDDEN_SCOPE"
    elif exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 409:
        code = "INVALID_STATUS_TRANSITION"
    elif exc.status_code == 422:
        code = "VALIDATION_ERROR"
    elif exc.status_code == 429:
        code = "RATE_LIMITED"

    content = make_error_envelope(
        code=code,
        message=str(exc.detail),
        trace_id=trace_id,
    )
    return JSONResponse(status_code=exc.status_code, content=content)
