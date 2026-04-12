"""File sync service — push file changes to sandbox via Redis pub/sub."""
from __future__ import annotations

import json
import logging
import time
import uuid

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def sync_file(
    sandbox_id: uuid.UUID,
    path: str,
    content: str,
) -> dict:
    """Publish a file change to the sandbox via Redis. Target < 300ms.

    Args:
        sandbox_id: Target sandbox.
        path: File path within the sandbox.
        content: New file content.

    Returns:
        Dict with publish status and timing.
    """
    channel = f"file_sync:{sandbox_id}"
    start = time.monotonic()

    message = json.dumps({
        "sandbox_id": str(sandbox_id),
        "path": path,
        "content": content,
        "timestamp": time.time(),
    })

    receivers = 0
    if redis_client is not None:
        receivers = await redis_client.publish(channel, message)

    elapsed_ms = (time.monotonic() - start) * 1000

    logger.info(
        "File sync: sandbox=%s path=%s receivers=%d latency=%.1fms",
        sandbox_id, path, receivers, elapsed_ms,
    )

    return {
        "sandbox_id": str(sandbox_id),
        "path": path,
        "receivers": receivers,
        "latency_ms": round(elapsed_ms, 1),
    }
