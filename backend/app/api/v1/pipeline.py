from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from pydantic import BaseModel

from app.config import settings
from app.core.redis import redis_client
from app.services import pipeline_service

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


# ── Schemas ──────────────────────────────────────────────────────

class PipelineRunRequest(BaseModel):
    project_id: UUID
    idea_spec: dict


# ── Helpers ──────────────────────────────────────────────────────

def _user_id(request: Request) -> UUID:
    return request.state.user_id


# ── POST /api/v1/pipeline/run ────────────────────────────────────

@router.post("/run")
async def run_pipeline(request: Request, body: PipelineRunRequest):
    uid = _user_id(request)
    pipeline_id = await pipeline_service.start_pipeline(
        project_id=body.project_id,
        user_id=uid,
        idea_spec=body.idea_spec,
    )
    return {"pipeline_id": pipeline_id, "status": "pending"}


# ── GET /api/v1/pipeline/{id}/status ─────────────────────────────

@router.get("/{pipeline_id}/status")
async def get_status(request: Request, pipeline_id: UUID):
    return await pipeline_service.get_pipeline_status(pipeline_id, _user_id(request))


# ── GET /api/v1/pipeline/{id}/stages ─────────────────────────────

@router.get("/{pipeline_id}/stages")
async def get_stages(request: Request, pipeline_id: UUID):
    return await pipeline_service.get_pipeline_stages(pipeline_id, _user_id(request))


# ── POST /api/v1/pipeline/{id}/retry ────────────────────────────

@router.post("/{pipeline_id}/retry")
async def retry_pipeline(request: Request, pipeline_id: UUID):
    uid = _user_id(request)
    new_pipeline_id = await pipeline_service.retry_pipeline(pipeline_id, uid)
    return {"pipeline_id": new_pipeline_id, "status": "pending"}


# ── WS /api/v1/pipeline/{id}/stream ─────────────────────────────

@router.websocket("/{pipeline_id}/stream")
async def stream_pipeline(websocket: WebSocket, pipeline_id: UUID):
    await websocket.accept()

    # First message must be a valid JWT — HTTP middleware doesn't cover WS
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

    # Verify the user owns this pipeline run
    await pipeline_service.get_pipeline_status(pipeline_id, user_id)

    if redis_client is None:
        await websocket.close(code=1011, reason="Redis unavailable")
        return

    pubsub = redis_client.pubsub()
    channel = f"pipeline:{pipeline_id}"

    try:
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = json.loads(message["data"])
            await websocket.send_json(data)

            # Close only on pipeline-level completion (not individual stage completions)
            if data.get("type") == "pipeline_complete":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
