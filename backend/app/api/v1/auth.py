from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, Request

from app.core.database import get_read_session
from app.services.auth_service import (
    SupabaseAuthError,
    forgot_password,
    get_current_user,
    login_user,
    logout_user,
    refresh_tokens,
    register_user,
    reset_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── Request schemas ──────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    turnstile_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Endpoints ────────────────────────────────────────────────────
@router.post("/register")
async def register_endpoint(body: RegisterRequest):
    # TODO: validate body.turnstile_token with Cloudflare Turnstile API
    try:
        data = await register_user(body.email, body.password, body.display_name)
    except SupabaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return {
        "user": data.get("user"),
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
    }


@router.post("/login")
async def login_endpoint(body: LoginRequest):
    try:
        data = await login_user(body.email, body.password)
    except SupabaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return {
        "user": data.get("user"),
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
    }


@router.post("/logout")
async def logout_endpoint(request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ")
    try:
        await logout_user(token)
    except SupabaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return {"detail": "Logged out"}


@router.post("/refresh")
async def refresh_endpoint(body: RefreshRequest):
    try:
        data = await refresh_tokens(body.refresh_token)
    except SupabaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return data


@router.get("/me")
async def me_endpoint(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with get_read_session() as session:
        user = await get_current_user(user_id, session)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "onboarded": user.onboarded,
        "plan": user.plan,
        "token_limit": user.token_limit,
    }


@router.post("/forgot-password")
async def forgot_password_endpoint(body: ForgotPasswordRequest):
    try:
        await forgot_password(body.email)
    except SupabaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return {"detail": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password_endpoint(body: ResetPasswordRequest):
    try:
        await reset_password(body.token, body.new_password)
    except SupabaseAuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return {"detail": "Password reset successfully"}
