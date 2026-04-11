import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = getattr(request.state, "request_id", "unknown")
        user_id = getattr(request.state, "user_id", None)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            user_id=str(user_id) if user_id else None,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        await logger.ainfo(
            "request_completed",
            status_code=response.status_code,
        )

        return response
