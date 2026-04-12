import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.agents.state import PipelineState
from app.agents.validators import validate_g3, validate_g4
from app.main import app
from app.models.pipeline_run import PipelineRun, PipelineStatus


FAKE_USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
FAKE_PROJECT_ID = uuid.uuid4()
FAKE_PIPELINE_ID = uuid.uuid4()

FAKE_JWT_PAYLOAD = {
    "sub": str(FAKE_USER_ID),
    "aud": "authenticated",
    "role": "authenticated",
}

OTHER_JWT_PAYLOAD = {
    "sub": str(OTHER_USER_ID),
    "aud": "authenticated",
    "role": "authenticated",
}


def _make_pipeline_run(**overrides):
    defaults = {
        "id": FAKE_PIPELINE_ID,
        "project_id": FAKE_PROJECT_ID,
        "user_id": FAKE_USER_ID,
        "status": PipelineStatus.pending,
        "current_stage": 1,
        "idea_spec": {"description": "test app"},
        "errors": None,
    }
    defaults.update(overrides)
    run = MagicMock(spec=PipelineRun)
    for k, v in defaults.items():
        setattr(run, k, v)
    return run


@asynccontextmanager
async def _fake_write_session():
    session = AsyncMock()
    yield session


@asynccontextmanager
async def _fake_read_session():
    session = AsyncMock()
    yield session


@pytest_asyncio.fixture
async def auth_client():
    """Client with a valid JWT that passes auth middleware."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.middleware.auth.jwt") as mock_jwt:
            mock_jwt.decode.return_value = FAKE_JWT_PAYLOAD
            client.headers["Authorization"] = "Bearer fake-token"
            yield client


@pytest_asyncio.fixture
async def other_client():
    """Client with a different user's JWT."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.middleware.auth.jwt") as mock_jwt:
            mock_jwt.decode.return_value = OTHER_JWT_PAYLOAD
            client.headers["Authorization"] = "Bearer other-token"
            yield client


# ── State tests ──────────────────────────────────────────────────

async def test_pipeline_state_has_all_fields():
    state: PipelineState = {
        "idea_spec": {"description": "a todo app"},
        "pipeline_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "current_stage": 1,
        "csuite_outputs": {},
        "comprehensive_plan": {},
        "spec_outputs": {},
        "build_manifest": {},
        "generated_files": {},
        "gate_results": {},
        "errors": [],
        "sandbox_id": None,
    }
    assert "idea_spec" in state
    assert "pipeline_id" in state
    assert "project_id" in state
    assert "user_id" in state
    assert "current_stage" in state
    assert "csuite_outputs" in state
    assert "comprehensive_plan" in state
    assert "spec_outputs" in state
    assert "build_manifest" in state
    assert "generated_files" in state
    assert "gate_results" in state
    assert "errors" in state
    assert "sandbox_id" in state


# ── Gate tests ───────────────────────────────────────────────────

async def test_gate_g3_always_passes():
    state: PipelineState = {"idea_spec": {}, "pipeline_id": "x", "project_id": "x",
                            "user_id": "x", "current_stage": 2}
    result = validate_g3(state)
    assert result["passed"] is True
    assert result["reason"] == "auto-resolved"


async def test_gate_g4_requires_085():
    # Below threshold
    state_low: PipelineState = {
        "idea_spec": {},
        "pipeline_id": "x",
        "project_id": "x",
        "user_id": "x",
        "current_stage": 3,
        "comprehensive_plan": {"coherence_score": 0.80},
    }
    result_low = validate_g4(state_low)
    assert result_low["passed"] is False

    # At threshold
    state_ok: PipelineState = {
        "idea_spec": {},
        "pipeline_id": "x",
        "project_id": "x",
        "user_id": "x",
        "current_stage": 3,
        "comprehensive_plan": {"coherence_score": 0.85},
    }
    result_ok = validate_g4(state_ok)
    assert result_ok["passed"] is True

    # Above threshold
    state_high: PipelineState = {
        "idea_spec": {},
        "pipeline_id": "x",
        "project_id": "x",
        "user_id": "x",
        "current_stage": 3,
        "comprehensive_plan": {"coherence_score": 0.95},
    }
    result_high = validate_g4(state_high)
    assert result_high["passed"] is True


# ── Service tests ────────────────────────────────────────────────

async def test_start_pipeline_nonblocking(auth_client):
    """POST /run must return in < 500ms (non-blocking)."""
    with (
        patch("app.services.pipeline_service.get_write_session", _fake_write_session),
        patch("app.services.pipeline_service.forge_inngest") as mock_inngest,
    ):
        mock_inngest.send = AsyncMock()

        start = time.monotonic()
        resp = await auth_client.post("/api/v1/pipeline/run", json={
            "project_id": str(FAKE_PROJECT_ID),
            "idea_spec": {"description": "test app"},
        })
        elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status_code == 200
    data = resp.json()
    assert "pipeline_id" in data
    assert data["status"] == "pending"
    assert elapsed_ms < 500, f"Took {elapsed_ms:.0f}ms — must be < 500ms"


# ── Ownership tests ──────────────────────────────────────────────

async def test_pipeline_status_wrong_owner(other_client):
    """GET /status with wrong user should return 404."""
    with patch("app.services.pipeline_service.get_read_session") as mock_rs:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # ownership check fails
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        resp = await other_client.get(f"/api/v1/pipeline/{FAKE_PIPELINE_ID}/status")

    assert resp.status_code == 404


# ── WebSocket cleanup test ───────────────────────────────────────

async def test_websocket_cleanup():
    """Verify pubsub is unsubscribed and closed in finally block."""
    mock_pubsub = AsyncMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    # Simulate one message then the stream ends (completed status → break)
    async def _listen():
        yield {"type": "subscribe", "data": None}
        yield {
            "type": "message",
            "data": '{"stage": 6, "status": "completed", "message": "done", "timestamp_ms": 1000}',
        }

    mock_pubsub.listen = _listen

    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    # Test directly with Starlette TestClient (sync) — BaseHTTPMiddleware
    # does not support WebSocket upgrade via httpx, so we bypass it.
    from starlette.testclient import TestClient

    with (
        patch("app.api.v1.pipeline.redis_client", mock_redis),
        patch("app.middleware.auth.jwt") as mock_jwt,
    ):
        mock_jwt.decode.return_value = FAKE_JWT_PAYLOAD
        client = TestClient(app)
        with client.websocket_connect(
            f"/api/v1/pipeline/{FAKE_PIPELINE_ID}/stream",
            headers={"Authorization": "Bearer fake-token"},
        ) as ws:
            msg = ws.receive_json()
            assert msg["status"] == "completed"

    mock_pubsub.unsubscribe.assert_called_once()
    mock_pubsub.close.assert_called_once()
