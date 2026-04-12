"""Snapshot service — Playwright screenshot → WebP → Supabase Storage + DB record."""
from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import select

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.core.redis import redis_client
from app.models.build_snapshot import BuildSnapshot
from app.services.storage_service import upload_file

logger = logging.getLogger(__name__)


async def capture_snapshot(
    build_id: uuid.UUID,
    project_id: uuid.UUID,
    agent_number: int,
    agent_type: str,
    generated_files: dict[str, str],
    *,
    screenshot_bytes: bytes | None = None,
) -> dict:
    """Capture a screenshot snapshot after a build agent.

    Playwright → WebP → Supabase SUPABASE_BUCKET_SNAPSHOTS.
    Path: snapshots/{project_id}/{build_id}/{agent_number:02d}_{agent_type}.webp
    Stores build_snapshots record and publishes Redis event.

    Args:
        build_id: Build this snapshot belongs to.
        project_id: Project ID for storage path.
        agent_number: Which build agent produced this state.
        agent_type: Agent name (e.g. "scaffold", "ui", "api").
        generated_files: Current state of generated files (for JSON backup).
        screenshot_bytes: Pre-captured screenshot bytes (for testing/injection).

    Returns:
        Dict with storage_key, screenshot_url, and snapshot_id.
    """
    storage_key = (
        f"snapshots/{project_id}/{build_id}/"
        f"{agent_number:02d}_{agent_type}.webp"
    )

    # Use provided screenshot or generate placeholder
    if screenshot_bytes is None:
        # In production, Playwright captures here. For now, store JSON manifest.
        screenshot_bytes = json.dumps(
            {
                "agent_number": agent_number,
                "agent_type": agent_type,
                "file_count": len(generated_files),
                "files": list(generated_files.keys()),
            },
            sort_keys=True,
        ).encode()
        content_type = "application/json"
    else:
        content_type = "image/webp"

    screenshot_url = await upload_file(
        bucket=settings.SUPABASE_BUCKET_SNAPSHOTS,
        path=storage_key,
        content=screenshot_bytes,
        content_type=content_type,
    )

    # Store build_snapshots record
    async with get_write_session() as session:
        snapshot = BuildSnapshot(
            build_id=build_id,
            project_id=project_id,
            agent_number=agent_number,
            agent_type=agent_type,
            screenshot_url=screenshot_url,
            storage_key=storage_key,
        )
        session.add(snapshot)
        await session.flush()
        snapshot_id = snapshot.id

    # Publish Redis event
    if redis_client is not None:
        await redis_client.publish(
            f"build:snapshot:{build_id}",
            json.dumps({
                "snapshot_id": str(snapshot_id),
                "agent_number": agent_number,
                "agent_type": agent_type,
                "screenshot_url": screenshot_url,
            }),
        )

    logger.info(
        "Snapshot captured: agent=%d/%s key=%s",
        agent_number, agent_type, storage_key,
    )
    return {
        "snapshot_id": str(snapshot_id),
        "storage_key": storage_key,
        "screenshot_url": screenshot_url,
    }


async def get_snapshots(
    project_id: uuid.UUID,
    build_id: uuid.UUID | None = None,
) -> list[dict]:
    """Get snapshots ordered by agent_number.

    Args:
        project_id: Filter by project.
        build_id: Optional filter by specific build.

    Returns:
        List of snapshot dicts ordered by agent_number.
    """
    async with get_read_session() as session:
        stmt = (
            select(BuildSnapshot)
            .where(BuildSnapshot.project_id == project_id)
            .order_by(BuildSnapshot.agent_number)
        )
        if build_id is not None:
            stmt = stmt.where(BuildSnapshot.build_id == build_id)

        result = await session.execute(stmt)
        snapshots = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "build_id": str(s.build_id),
            "agent_number": s.agent_number,
            "agent_type": s.agent_type,
            "screenshot_url": s.screenshot_url,
            "storage_key": s.storage_key,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in snapshots
    ]
