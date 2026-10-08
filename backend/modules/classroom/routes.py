"""Classroom and Polls endpoints (SE01-SE10, P01-P04, WS)."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from backend.core.db import get_db, SessionLocal
from backend.core.security import require_role, get_current_user_claims, decode_token
from backend.core.errors import NotFoundError, ForbiddenScopeError
from backend.models.classroom import ClassSession
from backend.modules.classroom.state import build_session_state
from backend.modules.classroom.ws import ws_manager
from backend.modules.classroom.service import (
    start_session_service,
    join_session_service,
    change_slide_service,
    post_prompt_service,
    start_quiz_service,
    close_quiz_service,
    end_session_service,
    get_session_report_service,
    get_active_session_for_student_service,
    create_poll_service,
    respond_to_poll_service,
    close_poll_service,
    get_poll_results_service,
)
from backend.schemas.classroom import (
    SessionState,
    SessionStartRequest,
    SessionJoinRequest,
    SlideActionRequest,
    PromptCreateRequest,
    PollCreateRequest,
    PollRespondRequest,
    PollResultsResponse,
)

router = APIRouter(prefix="/api", tags=["Classroom & Polls"])


# --- Session Management (SE01 - SE10) ---
@router.post("/sessions/start", status_code=status.HTTP_201_CREATED)
async def start_session(
    req: SessionStartRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE01: Start classroom session for section."""
    teacher_id = claims.get("teacher_id")
    user_id = int(claims["sub"])
    session_id, join_url, state = await start_session_service(
        lesson_id=req.lesson_id,
        section_id=req.section_id,
        teacher_id=teacher_id,
        teacher_user_id=user_id,
        db=db,
    )
    return {"session_id": session_id, "join_url": join_url, "state": state}


@router.post("/sessions/{id}/join", response_model=SessionState)
async def join_session(
    id: int,
    req: Optional[SessionJoinRequest] = None,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """SE02: Join live classroom session."""
    student_id = int(claims["student_id"])
    user_id = int(claims["sub"])
    display_name = req.display_name if req else None
    return await join_session_service(id, student_id, user_id, display_name, db)


@router.get("/sessions/active")
def get_active_session(
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """SE10: Check if an active session exists for student's section."""
    student_id = int(claims["student_id"])
    return get_active_session_for_student_service(student_id, db)


@router.get("/sessions/{id}", response_model=SessionState)
def get_session(
    id: int,
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """SE03: Get session state (sanitized according to role)."""
    session = db.query(ClassSession).filter(ClassSession.id == id).first()
    if not session:
        raise NotFoundError(f"Session {id} not found")

    role = claims.get("role", "STUDENT")
    user_id = int(claims["sub"])
    return build_session_state(session, role, user_id, db)


@router.post("/sessions/{id}/slide", response_model=SessionState)
async def control_slide(
    id: int,
    action: SlideActionRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE04: Teacher slide navigation command."""
    teacher_id = claims.get("teacher_id")
    user_id = int(claims["sub"])
    return await change_slide_service(id, action, teacher_id, user_id, db)


@router.post("/sessions/{id}/prompts", status_code=status.HTTP_201_CREATED)
async def post_prompt(
    id: int,
    prompt_req: PromptCreateRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE05: Teacher post live class prompt."""
    teacher_id = claims.get("teacher_id")
    user_id = int(claims["sub"])
    return await post_prompt_service(id, prompt_req, teacher_id, user_id, db)


@router.post("/sessions/{id}/quiz/start", response_model=SessionState)
async def start_quiz(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE06: Open exit quiz for student responses."""
    teacher_id = claims.get("teacher_id")
    user_id = int(claims["sub"])
    return await start_quiz_service(id, teacher_id, user_id, db)


@router.post("/sessions/{id}/quiz/close")
async def close_quiz(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE07: Close exit quiz and trigger class aggregation."""
    teacher_id = claims.get("teacher_id")
    user_id = int(claims["sub"])
    return await close_quiz_service(id, teacher_id, user_id, db)


@router.post("/sessions/{id}/end")
async def end_session(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE08: End classroom session."""
    teacher_id = claims.get("teacher_id")
    user_id = int(claims["sub"])
    return await end_session_service(id, teacher_id, user_id, db)


@router.get("/sessions/{id}/report")
def get_session_report(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """SE09: Retrieve post-class session attendance and quiz report."""
    return get_session_report_service(id, db)


# --- Poll Endpoints (P01 - P04) ---
@router.post("/polls", status_code=status.HTTP_201_CREATED)
async def create_poll(
    poll_req: PollCreateRequest,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """P01: Launch a live poll question in classroom."""
    teacher_id = claims.get("teacher_id")
    return await create_poll_service(poll_req, teacher_id, db)


@router.post("/polls/{id}/respond")
async def respond_to_poll(
    id: int,
    req: PollRespondRequest,
    claims: dict = Depends(require_role("STUDENT")),
    db: Session = Depends(get_db),
):
    """P02: Student respond to live concept check poll."""
    student_id = int(claims["student_id"])
    return await respond_to_poll_service(id, req, student_id, db)


@router.post("/polls/{id}/close")
async def close_poll(
    id: int,
    claims: dict = Depends(require_role("TEACHER", "ADMIN")),
    db: Session = Depends(get_db),
):
    """P03: Close active poll."""
    teacher_id = claims.get("teacher_id")
    return await close_poll_service(id, teacher_id, db)


@router.get("/polls/{id}/results", response_model=PollResultsResponse)
def get_poll_results(
    id: int,
    claims: dict = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
):
    """P04: Retrieve poll response counts."""
    role = claims.get("role", "STUDENT")
    user_id = int(claims["sub"])
    return get_poll_results_service(id, role, user_id, db)


# --- WebSocket Route ---
ws_router = APIRouter()


@ws_router.websocket("/ws/sessions/{id}")
async def session_websocket(websocket: WebSocket, id: int, token: Optional[str] = Query(None)):
    """WS: Live classroom state synchronization and push broadcasts."""
    if not token:
        await websocket.close(code=4401)
        return

    try:
        claims = decode_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    user_id = int(claims["sub"])
    role = claims.get("role", "STUDENT")

    db = SessionLocal()
    try:
        session = db.query(ClassSession).filter(ClassSession.id == id).first()
        if not session:
            await websocket.close(code=4404)
            return

        # Scope validation
        if role == "TEACHER" and session.teacher_id != claims.get("teacher_id"):
            await websocket.close(code=4403)
            return
        elif role == "STUDENT":
            student_id = claims.get("student_id")
            if not student_id:
                await websocket.close(code=4403)
                return

        await ws_manager.connect(id, websocket, user_id, role)

        # Send initial state.sync
        state = build_session_state(session, role, user_id, db)
        await websocket.send_json({
            "type": "state.sync",
            "session_id": id,
            "version": session.version,
            "payload": state.model_dump(mode="json"),
        })

        # Server-to-client only: wait for disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(id, websocket)
    except Exception:
        ws_manager.disconnect(id, websocket)
    finally:
        db.close()
