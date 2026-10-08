"""Classroom WebSocket manager: server-to-client broadcasts and heartbeats."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("sgsu.classroom.ws")


class SessionConnection:
    def __init__(self, websocket: WebSocket, user_id: int, role: str):
        self.websocket = websocket
        self.user_id = user_id
        self.role = role


class ClassroomWSManager:
    def __init__(self):
        # session_id -> List[SessionConnection]
        self._rooms: Dict[int, List[SessionConnection]] = {}
        self._heartbeat_tasks: Dict[int, asyncio.Task] = {}

    async def connect(self, session_id: int, websocket: WebSocket, user_id: int, role: str) -> None:
        await websocket.accept()
        if session_id not in self._rooms:
            self._rooms[session_id] = []
            # Start background heartbeat ping task
            self._heartbeat_tasks[session_id] = asyncio.create_task(self._heartbeat_loop(session_id))

        self._rooms[session_id].append(SessionConnection(websocket, user_id, role))
        logger.info(f"User {user_id} ({role}) connected to session {session_id} WS. Total: {len(self._rooms[session_id])}")

    def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        if session_id in self._rooms:
            self._rooms[session_id] = [c for c in self._rooms[session_id] if c.websocket != websocket]
            if not self._rooms[session_id]:
                del self._rooms[session_id]
                task = self._heartbeat_tasks.pop(session_id, None)
                if task:
                    task.cancel()
        logger.info(f"WS disconnected from session {session_id}")

    async def broadcast(
        self,
        session_id: int,
        msg_type: str,
        version: int,
        payload: Any,
        teacher_only: bool = False,
    ) -> None:
        """Broadcast message to all connected clients in the session."""
        if session_id not in self._rooms:
            return

        message = {
            "type": msg_type,
            "session_id": session_id,
            "version": version,
            "ts": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        raw_msg = json.dumps(message)

        dead_connections = []
        for conn in list(self._rooms[session_id]):
            if teacher_only and conn.role not in ("TEACHER", "ADMIN"):
                continue
            try:
                await conn.websocket.send_text(raw_msg)
            except Exception as e:
                logger.warning(f"Error sending WS message to client: {e}")
                dead_connections.append(conn)

        for dead in dead_connections:
            if dead in self._rooms.get(session_id, []):
                self._rooms[session_id].remove(dead)

    async def _heartbeat_loop(self, session_id: int) -> None:
        """Send periodic ping every 20 seconds to maintain connection health."""
        try:
            while True:
                await asyncio.sleep(20)
                if session_id in self._rooms:
                    ping_msg = json.dumps({
                        "type": "ping",
                        "session_id": session_id,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                    for conn in list(self._rooms[session_id]):
                        try:
                            await conn.websocket.send_text(ping_msg)
                        except Exception:
                            pass
        except asyncio.CancelledError:
            pass


ws_manager = ClassroomWSManager()
