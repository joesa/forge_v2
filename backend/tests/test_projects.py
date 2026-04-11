import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.project import Project, ProjectStatus, Framework


FAKE_USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
FAKE_PROJECT_ID = uuid.uuid4()

FAKE_JWT_PAYLOAD = {
    "sub": str(FAKE_USER_ID),
    "aud": "authenticated",
    "role": "authenticated",
}


def _make_project(**overrides):
    defaults = {
        "id": FAKE_PROJECT_ID,
        "user_id": FAKE_USER_ID,
        "name": "My App",
        "description": "A test app",
        "status": ProjectStatus.draft,
        "framework": Framework.vite_react,
        "created_at": MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00")),
        "updated_at": MagicMock(isoformat=MagicMock(return_value="2026-01-01T00:00:00")),
    }
    defaults.update(overrides)
    p = MagicMock(spec=Project)
    for k, v in defaults.items():
        setattr(p, k, v)
    return p


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


# ── List projects ────────────────────────────────────────────────

async def test_list_projects(auth_client):
    projects = [_make_project()]
    with patch("app.services.project_service.get_read_session") as mock_rs:
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = projects
        result.scalars.return_value = scalars
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        resp = await auth_client.get("/api/v1/projects")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "My App"


# ── Create project ───────────────────────────────────────────────

async def test_create_project(auth_client):
    project = _make_project()
    with patch("app.services.project_service.get_write_session") as mock_ws:
        session = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()

        @asynccontextmanager
        async def _ws():
            yield session

        mock_ws.side_effect = _ws

        # Capture the project object added to session and set its mock attributes
        def _capture_add(obj):
            obj.id = FAKE_PROJECT_ID
            obj.status = ProjectStatus.draft
            obj.framework = Framework.vite_react
            obj.created_at = None
            obj.updated_at = None

        session.add.side_effect = _capture_add

        resp = await auth_client.post("/api/v1/projects", json={
            "name": "My App",
            "framework": "vite_react",
            "description": "A test app",
        })

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My App"
    assert data["framework"] == "vite_react"


# ── Get project ──────────────────────────────────────────────────

async def test_get_project(auth_client):
    project = _make_project()
    with patch("app.services.project_service.get_read_session") as mock_rs:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = project
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        resp = await auth_client.get(f"/api/v1/projects/{FAKE_PROJECT_ID}")

    assert resp.status_code == 200
    assert resp.json()["id"] == str(FAKE_PROJECT_ID)


# ── Get project wrong owner → 404 ───────────────────────────────

async def test_get_project_wrong_owner(auth_client):
    """Project exists but belongs to a different user → 404, not the project data."""
    with patch("app.services.project_service.get_read_session") as mock_rs:
        session = AsyncMock()
        result = MagicMock()
        # WHERE user_id=<our user> won't match → None
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        resp = await auth_client.get(f"/api/v1/projects/{FAKE_PROJECT_ID}")

    assert resp.status_code == 404


# ── Update project ───────────────────────────────────────────────

async def test_update_project(auth_client):
    project = _make_project()
    with patch("app.services.project_service.get_write_session") as mock_ws:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = project
        session.execute.return_value = result
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        @asynccontextmanager
        async def _ws():
            yield session

        mock_ws.side_effect = _ws

        resp = await auth_client.put(
            f"/api/v1/projects/{FAKE_PROJECT_ID}",
            json={"name": "Renamed"},
        )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


# ── Delete project ───────────────────────────────────────────────

async def test_delete_project(auth_client):
    project = _make_project()
    with patch("app.services.project_service.get_write_session") as mock_ws:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = project
        session.execute.return_value = result
        session.delete = AsyncMock()

        @asynccontextmanager
        async def _ws():
            yield session

        mock_ws.side_effect = _ws

        resp = await auth_client.delete(f"/api/v1/projects/{FAKE_PROJECT_ID}")

    assert resp.status_code == 204


# ── Path traversal → 400 ────────────────────────────────────────

async def test_path_traversal(auth_client):
    """Attempting ../../etc/passwd must return 400, never reach storage."""
    project = _make_project()

    with patch("app.services.project_service.get_read_session") as mock_rs:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = project
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        resp = await auth_client.get(
            f"/api/v1/projects/{FAKE_PROJECT_ID}/files",
            params={"path": "../../etc/passwd"},
        )

    assert resp.status_code == 400
    assert "traversal" in resp.json()["detail"].lower()


# ── Path starting with / → 400 ──────────────────────────────────

async def test_absolute_path_rejected(auth_client):
    project = _make_project()

    with patch("app.services.project_service.get_read_session") as mock_rs:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = project
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        resp = await auth_client.get(
            f"/api/v1/projects/{FAKE_PROJECT_ID}/files",
            params={"path": "/etc/passwd"},
        )

    assert resp.status_code == 400


# ── File rename ──────────────────────────────────────────────────

async def test_rename_file(auth_client):
    project = _make_project()

    with (
        patch("app.services.project_service.get_read_session") as mock_rs,
        patch("app.services.project_service.storage_service") as mock_storage,
    ):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = project
        session.execute.return_value = result

        @asynccontextmanager
        async def _rs():
            yield session

        mock_rs.side_effect = _rs

        mock_storage.download_file = AsyncMock(return_value=b"file-content")
        mock_storage.upload_file = AsyncMock(return_value="https://example.com/new")
        mock_storage.delete_file = AsyncMock()

        resp = await auth_client.post(
            f"/api/v1/projects/{FAKE_PROJECT_ID}/files/rename",
            json={"old_path": "src/old.ts", "new_path": "src/new.ts"},
        )

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://example.com/new"
