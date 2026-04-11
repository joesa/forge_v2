import time

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.redis import redis_client

_STRICT_PREFIXES = ("/api/v1/pipeline", "/api/v1/ai")
_STANDARD_LIMIT = 100
_STRICT_LIMIT = 10
_WINDOW = 60  # seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if redis_client is None:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        is_strict = any(path.startswith(p) for p in _STRICT_PREFIXES)
        limit = _STRICT_LIMIT if is_strict else _STANDARD_LIMIT
        bucket = f"rl:{'strict' if is_strict else 'std'}:{client_ip}"

        now = time.time()
        window_start = now - _WINDOW

        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(bucket, 0, window_start)
        pipe.zadd(bucket, {str(now): now})
        pipe.zcard(bucket)
        pipe.expire(bucket, _WINDOW)
        results = await pipe.execute()

        count = results[2]
        if count > limit:
            retry_after = int(_WINDOW - (now - window_start))
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        return await call_next(request)
