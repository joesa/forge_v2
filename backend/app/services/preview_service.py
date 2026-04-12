"""Preview service — URL resolution, health checks, screenshots, share links."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.core.redis import redis_client
from app.models.preview_share import PreviewShare
from app.models.sandbox import Sandbox
from app.models.project import Project
from app.services import storage_service

logger = logging.getLogger(__name__)

_HEALTH_CACHE_TTL = 10  # seconds


async def _get_sandbox_with_ownership(
    sandbox_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Sandbox:
    """Fetch sandbox and verify the user owns the associated project."""
    async with get_read_session() as session:
        result = await session.execute(
            select(Sandbox, Project)
            .join(Project, Sandbox.project_id == Project.id)
            .where(Sandbox.id == sandbox_id, Project.user_id == user_id)
        )
        row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return row[0]


async def get_preview_url(
    sandbox_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Get the preview URL for a sandbox after verifying ownership."""
    sandbox = await _get_sandbox_with_ownership(sandbox_id, user_id)
    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}"
    return {
        "sandbox_id": str(sandbox.id),
        "preview_url": preview_url,
        "status": sandbox.status.value,
    }


async def check_preview_health(sandbox_id: uuid.UUID) -> dict:
    """HTTP health check to sandbox, cached in Redis with 10s TTL."""
    cache_key = f"preview:health:{sandbox_id}"

    # Check Redis cache
    if redis_client is not None:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)

    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}"
    health: dict = {
        "sandbox_id": str(sandbox_id),
        "healthy": False,
        "status_code": None,
        "latency_ms": None,
    }

    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{preview_url}/health")
        elapsed = (time.monotonic() - start) * 1000
        health["healthy"] = resp.status_code == 200
        health["status_code"] = resp.status_code
        health["latency_ms"] = round(elapsed, 1)
    except httpx.HTTPError as e:
        logger.warning("Preview health check failed for %s: %s", sandbox_id, e)
        health["error"] = str(e)

    # Cache result in Redis
    if redis_client is not None:
        await redis_client.set(cache_key, json.dumps(health), ex=_HEALTH_CACHE_TTL)

    return health


async def take_screenshot(
    sandbox_id: uuid.UUID,
    route: str = "/",
    *,
    playwright_page=None,
) -> dict:
    """Take a screenshot via Playwright → WebP → Supabase Storage.

    Args:
        sandbox_id: Sandbox to screenshot.
        route: Route within the preview to capture.
        playwright_page: Optional injected Playwright page (for testing).

    Returns:
        Dict with storage_key and screenshot_url.
    """
    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}"
    target = f"{preview_url}{route}"

    # Capture screenshot
    if playwright_page is not None:
        page = playwright_page
        await page.goto(target, wait_until="networkidle")
        screenshot_bytes = await page.screenshot(type="png")
    else:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 720})
                await page.goto(target, wait_until="networkidle")
                screenshot_bytes = await page.screenshot(type="png")
                await browser.close()
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="Playwright not available for screenshots",
            )

    # Upload to Supabase Storage
    safe_route = route.strip("/").replace("/", "_") or "index"
    storage_key = f"screenshots/{sandbox_id}/{safe_route}.webp"

    screenshot_url = await storage_service.upload_file(
        bucket=settings.SUPABASE_BUCKET_SCREENSHOTS,
        path=storage_key,
        content=screenshot_bytes,
        content_type="image/webp",
    )

    logger.info("Screenshot captured: sandbox=%s route=%s key=%s", sandbox_id, route, storage_key)
    return {
        "storage_key": storage_key,
        "screenshot_url": screenshot_url,
    }


def _generate_share_token(sandbox_id: uuid.UUID, expires_at_unix: int) -> str:
    """Generate HMAC-SHA256 share token."""
    message = f"{sandbox_id}:{expires_at_unix}"
    return hmac.new(
        settings.FORGE_HMAC_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


async def create_share(
    sandbox_id: uuid.UUID,
    user_id: uuid.UUID,
    expires_hours: int = 24,
) -> dict:
    """Create a share link for a sandbox preview.

    Token = HMAC-SHA256("{sandbox_id}:{expires_at_unix}", FORGE_HMAC_SECRET).
    Stored in Redis (TTL) + preview_shares table.
    """
    # Verify ownership
    await _get_sandbox_with_ownership(sandbox_id, user_id)

    now = datetime.now(timezone.utc)
    expires_at_unix = int(now.timestamp()) + (expires_hours * 3600)
    expires_at = datetime.fromtimestamp(expires_at_unix, tz=timezone.utc)
    token = _generate_share_token(sandbox_id, expires_at_unix)

    # Store in DB
    async with get_write_session() as session:
        share = PreviewShare(
            sandbox_id=sandbox_id,
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        session.add(share)
        await session.flush()
        share_id = share.id

    # Cache in Redis with TTL
    if redis_client is not None:
        redis_key = f"share:{token}"
        share_data = json.dumps({
            "sandbox_id": str(sandbox_id),
            "user_id": str(user_id),
            "expires_at": expires_at.isoformat(),
        })
        await redis_client.set(redis_key, share_data, ex=expires_hours * 3600)

    preview_url = f"https://{sandbox_id}.{settings.PREVIEW_DOMAIN}?share={token}"

    logger.info(
        "Share created: sandbox=%s user=%s expires=%s",
        sandbox_id, user_id, expires_at.isoformat(),
    )
    return {
        "share_id": str(share_id),
        "token": token,
        "preview_url": preview_url,
        "expires_at": expires_at.isoformat(),
    }


async def revoke_share(token: str, user_id: uuid.UUID) -> dict:
    """Revoke a share link. Verify ownership — 403 if not owner."""
    async with get_write_session() as session:
        result = await session.execute(
            select(PreviewShare).where(PreviewShare.token == token)
        )
        share = result.scalar_one_or_none()

        if share is None:
            raise HTTPException(status_code=404, detail="Share not found")

        if share.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not the owner of this share")

        share.revoked = True
        share.status = "revoked"

    # Remove from Redis
    if redis_client is not None:
        await redis_client.delete(f"share:{token}")

    logger.info("Share revoked: token=%s user=%s", token[:8], user_id)
    return {"revoked": True, "token": token}
