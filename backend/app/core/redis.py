import redis.asyncio as redis

from app.config import settings

redis_client: redis.Redis = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
) if settings.REDIS_URL else None  # type: ignore[assignment]
