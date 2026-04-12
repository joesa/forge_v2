from __future__ import annotations

import uuid

import inngest
from sqlalchemy import select

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.build import Build, BuildStatus


async def start_build(project_id: uuid.UUID, user_id: uuid.UUID, pipeline_run_id: uuid.UUID | None = None) -> str:
    """Create a Build record and fire forge/build.run. Returns build_id immediately."""
    build_id = str(uuid.uuid4())
    async with get_write_session() as db:
        build = Build(
            id=uuid.UUID(build_id),
            project_id=project_id,
            user_id=user_id,
            pipeline_run_id=pipeline_run_id,
            status=BuildStatus.pending,
        )
        db.add(build)

    await forge_inngest.send(
        inngest.Event(
            name="forge/build.run",
            data={
                "build_id": build_id,
                "project_id": str(project_id),
            },
        )
    )
    return build_id


async def get_build_status(build_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    async with get_read_session() as db:
        result = await db.execute(
            select(Build).where(Build.id == build_id, Build.user_id == user_id)
        )
        build = result.scalar_one_or_none()
    if not build:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Build not found")
    return {
        "build_id": str(build.id),
        "status": build.status.value,
    }
