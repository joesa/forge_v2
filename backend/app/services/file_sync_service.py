"""File sync service — push file changes to sandbox via Redis pub/sub + HTTP fallback."""
from __future__ import annotations

import json
import logging
import time
import uuid

import httpx

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def _get_sandbox_agent_url(sandbox_id: uuid.UUID) -> str | None:
    """Look up the sandbox's internal URL from the database."""
    from sqlalchemy import select
    from app.core.database import get_read_session
    from app.models.sandbox import Sandbox
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox.sandbox_url).where(Sandbox.id == sandbox_id)
        )
        url = result.scalar_one_or_none()
        return url


async def _http_push_file(sandbox_url: str, path: str, content: str) -> bool:
    """Push a file to the sandbox agent via HTTP /write-file endpoint."""
    agent_url = _derive_agent_url(sandbox_url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{agent_url}/write-file",
                json={"path": path, "content": content},
            )
            if resp.status_code == 200:
                logger.info("HTTP fallback sync: agent=%s path=%s ok", agent_url, path)
                return True
            logger.warning("HTTP fallback failed: agent=%s status=%d body=%s", agent_url, resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.warning("HTTP fallback error: agent=%s error=%s", agent_url, e)
        return False


def _derive_agent_url(sandbox_url: str) -> str:
    """Convert a sandbox app URL to its agent URL (port 9999)."""
    agent_url = sandbox_url.rstrip("/")
    if "//app--" in agent_url:
        agent_url = agent_url.replace("//app--", "//agent--", 1)
    elif ":3000" in agent_url:
        agent_url = agent_url.replace(":3000", ":9999")
    else:
        agent_url = f"{agent_url}:9999"
    return agent_url


async def restart_sandbox(sandbox_id: uuid.UUID) -> bool:
    """Tell the sandbox agent to re-pull files and restart the dev server."""
    sandbox_url = await _get_sandbox_agent_url(sandbox_id)
    if not sandbox_url:
        logger.warning("restart_sandbox: no URL for sandbox %s", sandbox_id)
        return False

    agent_url = _derive_agent_url(sandbox_url)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{agent_url}/restart")
            if resp.status_code in (200, 202):
                logger.info("Sandbox restart triggered: sandbox=%s agent=%s", sandbox_id, agent_url)
                return True
            logger.warning("Sandbox restart failed: status=%d body=%s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.warning("Sandbox restart error: sandbox=%s error=%s", sandbox_id, e)
        return False


async def sync_file(
    sandbox_id: uuid.UUID,
    path: str,
    content: str,
) -> dict:
    """Push a file change to the sandbox via HTTP (primary) + Redis pub/sub (real-time).

    HTTP push is always attempted because it's the only reliable guarantee
    that the file actually lands on the sandbox filesystem.  Redis pub/sub
    is also fired for low-latency HMR triggers but is not trusted alone.

    Args:
        sandbox_id: Target sandbox.
        path: File path within the sandbox.
        content: New file content.

    Returns:
        Dict with publish status and timing.
    """
    start = time.monotonic()

    # 1. Always push via HTTP — this is the reliable path
    http_ok = False
    sandbox_url = await _get_sandbox_agent_url(sandbox_id)
    if sandbox_url:
        http_ok = await _http_push_file(sandbox_url, path, content)
    else:
        logger.warning("File sync: sandbox=%s has no sandbox_url — cannot HTTP push", sandbox_id)

    # 2. Also publish via Redis for real-time HMR notification
    redis_receivers = 0
    if redis_client is not None:
        channel = f"file_sync:{sandbox_id}"
        message = json.dumps({
            "sandbox_id": str(sandbox_id),
            "path": path,
            "content": content,
            "timestamp": time.time(),
        })
        try:
            redis_receivers = await redis_client.publish(channel, message)
        except Exception as e:
            logger.warning("Redis publish failed: %s", e)

    method = "http" if http_ok else ("redis" if redis_receivers > 0 else "none")
    receivers = (1 if http_ok else 0) + redis_receivers

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "File sync: sandbox=%s path=%s method=%s http=%s redis_receivers=%d latency=%.1fms",
        sandbox_id, path, method, http_ok, redis_receivers, elapsed_ms,
    )

    return {
        "sandbox_id": str(sandbox_id),
        "path": path,
        "receivers": receivers,
        "method": method,
        "latency_ms": round(elapsed_ms, 1),
    }
