"""Layer 9 — Rollback Engine: restore last successful build from Supabase Storage."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RollbackResult:
    rolled_back: bool
    snapshot_id: str | None = None
    files_restored: int = 0
    reason: str = ""
    timestamp: str = ""


async def rollback_to_last_success(
    project_id: str,
    pipeline_id: str,
    *,
    storage_client=None,
    db_session=None,
    bucket: str = "forge-snapshots",
) -> RollbackResult:
    """Find last build with status=success in Supabase and restore from Storage.

    Args:
        project_id: Project to roll back.
        pipeline_id: Current failing pipeline for logging.
        storage_client: Supabase storage client (supabase-py).
        db_session: Optional async DB session for querying build history.
        bucket: Storage bucket name.

    Returns:
        RollbackResult with rolled_back=True if restoration succeeded.
    """
    if storage_client is None:
        logger.warning("Rollback engine: no storage client provided")
        return RollbackResult(
            rolled_back=False,
            reason="no_storage_client",
        )

    # Find last successful snapshot
    snapshot_id = await _find_last_success(
        project_id=project_id,
        storage_client=storage_client,
        db_session=db_session,
        bucket=bucket,
    )

    if snapshot_id is None:
        logger.info("Rollback engine: no successful snapshot found for project %s", project_id)
        return RollbackResult(
            rolled_back=False,
            reason="no_successful_snapshot",
        )

    # Restore files from snapshot
    files = await _restore_snapshot(
        snapshot_id=snapshot_id,
        storage_client=storage_client,
        bucket=bucket,
    )

    if not files:
        logger.warning("Rollback engine: snapshot %s contained no files", snapshot_id)
        return RollbackResult(
            rolled_back=False,
            snapshot_id=snapshot_id,
            reason="empty_snapshot",
        )

    logger.info(
        "Rollback engine: restored %d files from snapshot %s for project %s (pipeline %s)",
        len(files), snapshot_id, project_id, pipeline_id,
    )
    return RollbackResult(
        rolled_back=True,
        snapshot_id=snapshot_id,
        files_restored=len(files),
        reason="success",
        timestamp=datetime.utcnow().isoformat(),
    )


async def _find_last_success(
    *,
    project_id: str,
    storage_client,
    db_session=None,
    bucket: str,
) -> str | None:
    """Find the most recent successful snapshot ID for a project."""
    # Strategy 1: Query DB for last successful build
    if db_session is not None:
        try:
            snapshot_id = await _query_db_last_success(project_id, db_session)
            if snapshot_id:
                return snapshot_id
        except Exception as e:
            logger.warning("DB query for last success failed: %s", e)

    # Strategy 2: List snapshots in storage and find latest success marker
    try:
        prefix = f"{project_id}/"
        response = storage_client.from_(bucket).list(prefix)

        if not response:
            return None

        # Snapshots are stored as {project_id}/{snapshot_id}/
        # Each snapshot has a metadata.json with status
        candidates: list[dict] = []
        seen_ids: set[str] = set()

        for item in response:
            name = item.get("name", "")
            if name and name not in seen_ids:
                seen_ids.add(name)
                candidates.append({"id": name, "metadata": item.get("metadata", {})})

        # Check each candidate for success status (newest first)
        for candidate in reversed(candidates):
            snap_id = candidate["id"]
            meta_path = f"{project_id}/{snap_id}/metadata.json"
            try:
                meta_bytes = storage_client.from_(bucket).download(meta_path)
                meta = json.loads(meta_bytes)
                if meta.get("status") == "success":
                    return snap_id
            except Exception:
                continue

    except Exception as e:
        logger.warning("Storage listing failed for rollback: %s", e)

    return None


async def _query_db_last_success(project_id: str, db_session) -> str | None:
    """Query the database for the last successful build snapshot ID."""
    from sqlalchemy import text

    result = await db_session.execute(
        text(
            "SELECT snapshot_id FROM builds "
            "WHERE project_id = :pid AND status = 'success' "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"pid": project_id},
    )
    row = result.first()
    return row[0] if row else None


async def _restore_snapshot(
    *,
    snapshot_id: str,
    storage_client,
    bucket: str,
) -> dict[str, str]:
    """Download all files from a snapshot in Supabase Storage."""
    files: dict[str, str] = {}

    try:
        # List files in snapshot directory
        response = storage_client.from_(bucket).list(snapshot_id)

        if not response:
            return files

        for item in response:
            file_name = item.get("name", "")
            if not file_name or file_name == "metadata.json":
                continue

            file_path = f"{snapshot_id}/{file_name}"
            try:
                content_bytes = storage_client.from_(bucket).download(file_path)
                if isinstance(content_bytes, bytes):
                    files[file_name] = content_bytes.decode("utf-8")
                else:
                    files[file_name] = str(content_bytes)
            except Exception as e:
                logger.warning("Failed to restore file %s: %s", file_path, e)

    except Exception as e:
        logger.warning("Failed to list snapshot %s: %s", snapshot_id, e)

    return files
