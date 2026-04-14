from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from pydantic import BaseModel

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.core.redis import redis_client
from app.models.editor_session import EditorSession
from app.services import project_service, sandbox_service

router = APIRouter(prefix="/api/v1/editor", tags=["editor"])


# ── Schemas ──────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    project_id: UUID


def _user_id(request: Request) -> UUID:
    return request.state.user_id


# ── POST /api/v1/editor/sessions ─────────────────────────────────

@router.post("/sessions", status_code=201)
async def create_session(request: Request, body: SessionCreate):
    uid = _user_id(request)
    # Verify user owns the project
    await project_service.get_project(body.project_id, uid)

    # Prefer existing sandbox (provisioned by pipeline Stage 6)
    sandbox_id_str = await sandbox_service.get_project_sandbox(body.project_id)
    if not sandbox_id_str:
        # No sandbox yet — user opened editor before build finished; provision one
        sandbox_id_str = await sandbox_service.claim_or_provision_sandbox(body.project_id)
    sandbox_uuid = UUID(sandbox_id_str) if sandbox_id_str else None

    async with get_write_session() as db:
        session = EditorSession(
            project_id=body.project_id,
            user_id=uid,
            sandbox_id=sandbox_uuid,
            last_active_at=datetime.utcnow(),
            status="active",
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return {
            "id": str(session.id),
            "project_id": str(session.project_id),
            "sandbox_id": str(session.sandbox_id) if session.sandbox_id else None,
            "status": session.status,
        }


# ── GET /api/v1/editor/sessions/{id} ─────────────────────────────

@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, request: Request):
    uid = _user_id(request)
    async with get_read_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(EditorSession).where(
                EditorSession.id == session_id,
                EditorSession.user_id == uid,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "id": str(session.id),
            "project_id": str(session.project_id),
            "sandbox_id": str(session.sandbox_id) if session.sandbox_id else None,
            "status": session.status,
        }


# ── WS /api/v1/editor/sessions/{id}/stream ──────────────────────

@router.websocket("/sessions/{session_id}/stream")
async def stream_session(websocket: WebSocket, session_id: UUID):
    await websocket.accept()

    # Auth via first message (JWT)
    auth_msg = await websocket.receive_text()
    try:
        payload = jwt.decode(
            auth_msg,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify ownership
    from sqlalchemy import select
    async with get_read_session() as db:
        result = await db.execute(
            select(EditorSession).where(
                EditorSession.id == session_id,
                EditorSession.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            await websocket.close(code=4003, reason="Session not found")
            return

    if redis_client is None:
        await websocket.close(code=1011, reason="Redis unavailable")
        return

    pubsub = redis_client.pubsub()
    channel = f"editor:{session_id}"

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = json.loads(message["data"])
            await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)


# ── WS /api/v1/editor/autobuild/{project_id}/stream ─────────────

@router.websocket("/autobuild/{project_id}/stream")
async def stream_autobuild(websocket: WebSocket, project_id: UUID):
    """WebSocket for real-time auto-build progress events."""
    await websocket.accept()

    # Auth via first message (JWT)
    auth_msg = await websocket.receive_text()
    try:
        payload = jwt.decode(
            auth_msg,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify user owns this project
    from sqlalchemy import select
    from app.models.project import Project
    async with get_read_session() as db:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            await websocket.close(code=4003, reason="Project not found")
            return

    if redis_client is None:
        await websocket.close(code=1011, reason="Redis unavailable")
        return

    pubsub = redis_client.pubsub()
    channel = f"autobuild:{project_id}"

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = json.loads(message["data"])
            await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
