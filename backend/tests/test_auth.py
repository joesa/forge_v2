import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.user import User


FAKE_USER_ID = str(uuid.uuid4())
FAKE_EMAIL = "test@example.com"
FAKE_PASSWORD = "SecurePass123!"
FAKE_DISPLAY_NAME = "Test User"


def _make_supabase_signup_response():
    return {
        "user": {
            "id": FAKE_USER_ID,
            "email": FAKE_EMAIL,
            "user_metadata": {"display_name": FAKE_DISPLAY_NAME},
        },
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
    }


def _make_supabase_login_response():
    return {
        "access_token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "user": {
            "id": FAKE_USER_ID,
            "email": FAKE_EMAIL,
            "user_metadata": {"display_name": FAKE_DISPLAY_NAME},
        },
    }


def _make_fake_user():
    user = MagicMock(spec=User)
    user.id = uuid.UUID(FAKE_USER_ID)
    user.email = FAKE_EMAIL
    user.display_name = FAKE_DISPLAY_NAME
    user.avatar_url = None
    user.onboarded = False
    user.plan = "free"
    user.token_limit = 10000
    return user


def _mock_httpx_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = str(json_data)
    return resp


@asynccontextmanager
async def _fake_write_session():
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result
    yield session


@asynccontextmanager
async def _fake_read_session():
    session = AsyncMock()
    yield session


@pytest_asyncio.fixture
async def test_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Registration ─────────────────────────────────────────────────

async def test_register_success(test_client):
    mock_resp = _mock_httpx_response(200, _make_supabase_signup_response())

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.auth_service.get_write_session", _fake_write_session),
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post("/api/v1/auth/register", json={
            "email": FAKE_EMAIL,
            "password": FAKE_PASSWORD,
            "display_name": FAKE_DISPLAY_NAME,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == FAKE_USER_ID


async def test_register_duplicate(test_client):
    error_body = {"msg": "User already registered"}
    mock_resp = _mock_httpx_response(422, error_body)

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post("/api/v1/auth/register", json={
            "email": FAKE_EMAIL,
            "password": FAKE_PASSWORD,
            "display_name": FAKE_DISPLAY_NAME,
        })

    assert resp.status_code == 422


# ── Login ────────────────────────────────────────────────────────

async def test_login_success(test_client):
    mock_resp = _mock_httpx_response(200, _make_supabase_login_response())

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
        patch("app.services.auth_service.get_write_session", _fake_write_session),
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post("/api/v1/auth/login", json={
            "email": FAKE_EMAIL,
            "password": FAKE_PASSWORD,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["id"] == FAKE_USER_ID


async def test_login_wrong_password(test_client):
    error_body = {"error_description": "Invalid login credentials"}
    mock_resp = _mock_httpx_response(400, error_body)

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post("/api/v1/auth/login", json={
            "email": FAKE_EMAIL,
            "password": "wrong-password",
        })

    assert resp.status_code == 400


# ── Refresh ──────────────────────────────────────────────────────

async def test_refresh_tokens(test_client):
    refresh_data = {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
    }
    mock_resp = _mock_httpx_response(200, refresh_data)

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post("/api/v1/auth/refresh", json={
            "refresh_token": "old-refresh-token",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "new-access-token"


# ── Logout ───────────────────────────────────────────────────────

async def test_logout(test_client):
    mock_resp = _mock_httpx_response(204, None)

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
        patch("app.middleware.auth.jwt") as mock_jwt,
    ):
        mock_jwt.decode.return_value = {"sub": FAKE_USER_ID, "aud": "authenticated"}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer fake-access-token"},
        )

    assert resp.status_code == 200
    assert resp.json()["detail"] == "Logged out"


# ── Me ───────────────────────────────────────────────────────────

async def test_me_authenticated(test_client):
    fake_user = _make_fake_user()

    async def _mock_get_current_user(user_id, session):
        return fake_user

    with (
        patch("app.api.v1.auth.get_read_session", _fake_read_session),
        patch("app.api.v1.auth.get_current_user", _mock_get_current_user),
        patch("app.middleware.auth.jwt") as mock_jwt,
    ):
        mock_jwt.decode.return_value = {"sub": FAKE_USER_ID, "aud": "authenticated"}

        resp = await test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer fake-token"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == FAKE_EMAIL
    assert data["id"] == FAKE_USER_ID


async def test_me_unauthenticated(test_client):
    resp = await test_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ── Forgot password ──────────────────────────────────────────────

async def test_forgot_password(test_client):
    mock_resp = _mock_httpx_response(200, {})

    with (
        patch("app.services.auth_service.httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = await test_client.post("/api/v1/auth/forgot-password", json={
            "email": FAKE_EMAIL,
        })

    assert resp.status_code == 200
