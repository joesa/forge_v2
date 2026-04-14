from __future__ import annotations

import uuid

import inngest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.pipeline_run import PipelineRun, PipelineStatus


async def start_pipeline(project_id: uuid.UUID, user_id: uuid.UUID, idea_spec: dict) -> str:
    """Create a PipelineRun and fire an Inngest event. Returns pipeline_id in < 200ms."""
    pipeline_id = str(uuid.uuid4())

    async with get_write_session() as session:
        run = PipelineRun(
            id=uuid.UUID(pipeline_id),
            project_id=project_id,
            user_id=user_id,
            status=PipelineStatus.pending,
            current_stage=1,
            idea_spec=idea_spec,
        )
        session.add(run)

    # NON-BLOCKING — send Inngest event, do not await pipeline completion
    await forge_inngest.send(
        inngest.Event(
            name="forge/pipeline.run",
            data={
                "pipeline_id": pipeline_id,
                "project_id": str(project_id),
                "user_id": str(user_id),
                "idea_spec": idea_spec,
            },
        )
    )

    return pipeline_id


async def get_pipeline_status(pipeline_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Get pipeline status — verify ownership."""
    async with get_read_session() as session:
        result = await session.execute(
            select(PipelineRun).where(
                PipelineRun.id == pipeline_id,
                PipelineRun.user_id == user_id,
            )
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return {
        "pipeline_id": str(run.id),
        "status": run.status.value,
        "current_stage": run.current_stage,
        "stage_states": run.stage_states,
        "errors": run.errors,
    }


async def get_pipeline_stages(pipeline_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Get pipeline stages — verify ownership."""
    async with get_read_session() as session:
        result = await session.execute(
            select(PipelineRun).where(
                PipelineRun.id == pipeline_id,
                PipelineRun.user_id == user_id,
            )
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return {
        "pipeline_id": str(run.id),
        "current_stage": run.current_stage,
        "status": run.status.value,
        "stage_states": run.stage_states,
    }


async def retry_pipeline(pipeline_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Retry a failed pipeline by creating a new run with the same idea_spec."""
    async with get_read_session() as session:
        result = await session.execute(
            select(PipelineRun).where(
                PipelineRun.id == pipeline_id,
                PipelineRun.user_id == user_id,
            )
        )
        old_run = result.scalar_one_or_none()

    if not old_run:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return await start_pipeline(
        project_id=old_run.project_id,
        user_id=user_id,
        idea_spec=old_run.idea_spec,
    )
