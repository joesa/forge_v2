"""Sandbox API routes — preview, screenshots, snapshots, annotations, console."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from pydantic import BaseModel, Field

from app.config import settings
from app.services import annotation_service, preview_service, snapshot_service

router = APIRouter(prefix="/api/v1/sandbox", tags=["sandbox"])


# ── Schemas ──────────────────────────────────────────────────────

class ScreenshotRequest(BaseModel):
    route: str = "/"


class ShareRequest(BaseModel):
    expires_hours: int = Field(default=24, ge=1, le=720)


class AnnotationCreate(BaseModel):
    css_selector: str
    route: str
    comment: str
    x_pct: float
    y_pct: float
    editor_session_id: uuid.UUID | None = None


# ── Helpers ──────────────────────────────────────────────────────

def _user_id(request: Request) -> uuid.UUID:
    uid = getattr(request.state, "user_id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return uid


async def _sandbox_project_id(sandbox_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    """Get project_id from sandbox after verifying ownership."""
    sandbox = await preview_service._get_sandbox_with_ownership(sandbox_id, user_id)
    return sandbox.project_id


# ── Preview routes ───────────────────────────────────────────────

@router.get("/{sandbox_id}/preview-url")
async def get_preview_url(sandbox_id: uuid.UUID, request: Request):
    return await preview_service.get_preview_url(sandbox_id, _user_id(request))


@router.get("/{sandbox_id}/preview/health")
async def check_preview_health(sandbox_id: uuid.UUID, request: Request):
    # Ownership check
    await preview_service._get_sandbox_with_ownership(sandbox_id, _user_id(request))
    return await preview_service.check_preview_health(sandbox_id)


@router.post("/{sandbox_id}/preview/screenshot")
async def take_screenshot(sandbox_id: uuid.UUID, request: Request, body: ScreenshotRequest):
    await preview_service._get_sandbox_with_ownership(sandbox_id, _user_id(request))
    return await preview_service.take_screenshot(sandbox_id, body.route)


# ── Share routes ─────────────────────────────────────────────────

@router.post("/{sandbox_id}/preview/share")
async def create_share(sandbox_id: uuid.UUID, request: Request, body: ShareRequest):
    return await preview_service.create_share(sandbox_id, _user_id(request), body.expires_hours)


@router.delete("/{sandbox_id}/share/{token}")
async def revoke_share(sandbox_id: uuid.UUID, token: str, request: Request):
    return await preview_service.revoke_share(token, _user_id(request))


# ── Console WebSocket ────────────────────────────────────────────

@router.websocket("/{sandbox_id}/console")
async def console_ws(sandbox_id: uuid.UUID, websocket: WebSocket):
    """WebSocket proxy for sandbox console output.

    Auth token can be passed as a query parameter (?token=...) or as the first message.
    """
    await websocket.accept()
    try:
        # Try query param first, then first message
        token = websocket.query_params.get("token")
        if not token:
            token = await websocket.receive_text()
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            user_id = uuid.UUID(payload["sub"])
        except (JWTError, KeyError, ValueError):
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Verify sandbox ownership
        try:
            await preview_service._get_sandbox_with_ownership(sandbox_id, user_id)
        except HTTPException:
            await websocket.close(code=4003, reason="Sandbox not found")
            return

        await websocket.send_json({"type": "connected", "sandbox_id": str(sandbox_id)})

        while True:
            data = await websocket.receive_text()
            # In production: forward to sandbox via Redis pub/sub
            await websocket.send_json({"type": "ack", "received": len(data)})
    except WebSocketDisconnect:
        pass


# ── Snapshot routes ──────────────────────────────────────────────

@router.get("/{sandbox_id}/snapshots")
async def get_snapshots(
    sandbox_id: uuid.UUID,
    request: Request,
    build_id: uuid.UUID | None = None,
):
    project_id = await _sandbox_project_id(sandbox_id, _user_id(request))
    return await snapshot_service.get_snapshots(project_id, build_id)


# ── Annotation routes ────────────────────────────────────────────

@router.get("/{sandbox_id}/annotations")
async def get_annotations(sandbox_id: uuid.UUID, request: Request):
    project_id = await _sandbox_project_id(sandbox_id, _user_id(request))
    return await annotation_service.get_annotations(project_id)


@router.post("/{sandbox_id}/annotations", status_code=201)
async def create_annotation(
    sandbox_id: uuid.UUID,
    request: Request,
    body: AnnotationCreate,
):
    uid = _user_id(request)
    project_id = await _sandbox_project_id(sandbox_id, uid)
    return await annotation_service.create_annotation(
        project_id=project_id,
        user_id=uid,
        css_selector=body.css_selector,
        route=body.route,
        comment=body.comment,
        x_pct=body.x_pct,
        y_pct=body.y_pct,
        editor_session_id=body.editor_session_id,
    )


@router.delete("/{sandbox_id}/annotation/{annotation_id}", status_code=204)
async def delete_annotation(
    sandbox_id: uuid.UUID,
    annotation_id: uuid.UUID,
    request: Request,
):
    uid = _user_id(request)
    await _sandbox_project_id(sandbox_id, uid)
    await annotation_service.delete_annotation(annotation_id, uid)
    return Response(status_code=204)


@router.delete("/{sandbox_id}/annotations")
async def clear_annotations(sandbox_id: uuid.UUID, request: Request):
    uid = _user_id(request)
    project_id = await _sandbox_project_id(sandbox_id, uid)
    count = await annotation_service.clear_annotations(project_id, uid)
    return {"deleted": count}
