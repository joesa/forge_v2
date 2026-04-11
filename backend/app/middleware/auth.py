from uuid import UUID

from fastapi import Request, HTTPException
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

_PUBLIC_PATHS = frozenset({
    "/health",
    "/api/inngest",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
})


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")

        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            request.state.user_id = UUID(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc

        return await call_next(request)
