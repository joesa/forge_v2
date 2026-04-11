from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_write_session
from app.models.user import User

_AUTH_BASE = f"{settings.SUPABASE_URL}/auth/v1"

_ADMIN_HEADERS = {
    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

_ANON_HEADERS = {
    "apikey": settings.SUPABASE_ANON_KEY,
    "Content-Type": "application/json",
}


class SupabaseAuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def register_user(email: str, password: str, display_name: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_AUTH_BASE}/signup",
            headers=_ADMIN_HEADERS,
            json={"email": email, "password": password, "data": {"display_name": display_name}},
        )
    if resp.status_code >= 400:
        detail = resp.json().get("msg", resp.json().get("error_description", resp.text))
        raise SupabaseAuthError(resp.status_code, detail)

    data = resp.json()
    supabase_uid = UUID(data["user"]["id"])

    async with get_write_session() as session:
        existing = await session.execute(select(User).where(User.id == supabase_uid))
        if existing.scalar_one_or_none() is None:
            user = User(
                id=supabase_uid,
                email=email,
                display_name=display_name,
                onboarded=False,
                plan="free",
            )
            session.add(user)

    return data


async def get_or_create_user_on_login(supabase_uid: UUID, email: str, display_name: str | None) -> User:
    async with get_write_session() as session:
        result = await session.execute(select(User).where(User.id == supabase_uid))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                id=supabase_uid,
                email=email,
                display_name=display_name,
                onboarded=False,
                plan="free",
            )
            session.add(user)
            await session.flush()
        return user


async def login_user(email: str, password: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_AUTH_BASE}/token",
            params={"grant_type": "password"},
            headers=_ANON_HEADERS,
            json={"email": email, "password": password},
        )
    if resp.status_code >= 400:
        detail = resp.json().get("error_description", resp.text)
        raise SupabaseAuthError(resp.status_code, detail)

    data = resp.json()
    user_data = data.get("user", {})
    await get_or_create_user_on_login(
        supabase_uid=UUID(user_data["id"]),
        email=user_data.get("email", email),
        display_name=user_data.get("user_metadata", {}).get("display_name"),
    )
    return data


async def refresh_tokens(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_AUTH_BASE}/token",
            params={"grant_type": "refresh_token"},
            headers=_ANON_HEADERS,
            json={"refresh_token": refresh_token},
        )
    if resp.status_code >= 400:
        detail = resp.json().get("error_description", resp.text)
        raise SupabaseAuthError(resp.status_code, detail)
    return resp.json()


async def get_current_user(user_id: UUID, session: AsyncSession) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def logout_user(access_token: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_AUTH_BASE}/logout",
            headers={
                **_ADMIN_HEADERS,
                "Authorization": f"Bearer {access_token}",
            },
        )
    # Ignore 401 — user may already be logged out
    if resp.status_code >= 400 and resp.status_code != 401:
        detail = resp.json().get("msg", resp.text)
        raise SupabaseAuthError(resp.status_code, detail)


async def forgot_password(email: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_AUTH_BASE}/recover",
            headers=_ANON_HEADERS,
            json={"email": email},
        )
    # Swallow ALL 4xx to prevent email enumeration; raise on 5xx only
    if resp.status_code >= 500:
        raise SupabaseAuthError(resp.status_code, resp.text)


async def reset_password(token: str, new_password: str) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{_AUTH_BASE}/user",
            headers={
                **_ANON_HEADERS,
                "Authorization": f"Bearer {token}",
            },
            json={"password": new_password},
        )
    if resp.status_code >= 400:
        detail = resp.json().get("msg", resp.json().get("error_description", resp.text))
        raise SupabaseAuthError(resp.status_code, detail)
