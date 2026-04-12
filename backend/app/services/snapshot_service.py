"""Snapshot service — captures build state after each agent."""
from __future__ import annotations

import json
import logging
import uuid

from app.config import settings
from app.services.storage_service import upload_file

logger = logging.getLogger(__name__)


async def capture_snapshot(
    build_id: uuid.UUID,
    project_id: uuid.UUID,
    agent_number: int,
    agent_type: str,
    generated_files: dict[str, str],
) -> dict:
    """Capture a point-in-time snapshot of generated_files to Supabase Storage.

    Returns dict with storage_key and url.
    """
    storage_key = f"{project_id}/{build_id}/snapshots/agent_{agent_number}_{agent_type}.json"

    payload = json.dumps(
        {
            "agent_number": agent_number,
            "agent_type": agent_type,
            "file_count": len(generated_files),
            "files": generated_files,
        },
        sort_keys=True,
    ).encode()

    url = await upload_file(
        bucket=settings.SUPABASE_BUCKET_SNAPSHOTS,
        path=storage_key,
        content=payload,
        content_type="application/json",
    )

    logger.info(
        "Snapshot captured: agent=%d/%s files=%d key=%s",
        agent_number,
        agent_type,
        len(generated_files),
        storage_key,
    )

    return {"storage_key": storage_key, "url": url}
