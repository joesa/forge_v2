from __future__ import annotations

import uuid

import inngest
from sqlalchemy import select

from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.sandbox import Sandbox, SandboxStatus


async def provision_sandbox(project_id: uuid.UUID | None = None) -> str:
    """Fire forge/sandbox.lifecycle provision event. Returns sandbox_id immediately."""
    sandbox_id = str(uuid.uuid4())
    async with get_write_session() as db:
        sandbox = Sandbox(
            id=uuid.UUID(sandbox_id),
            project_id=project_id,
            status=SandboxStatus.warm,
        )
        db.add(sandbox)

    await forge_inngest.send(
        inngest.Event(
            name="forge/sandbox.lifecycle",
            data={
                "action": "provision",
                "sandbox_id": sandbox_id,
                "project_id": str(project_id) if project_id else None,
            },
        )
    )
    return sandbox_id


async def start_sandbox(sandbox_id: uuid.UUID) -> None:
    """Fire event to start/claim a sandbox."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox).where(Sandbox.id == sandbox_id)
        )
        sandbox = result.scalar_one_or_none()

    if not sandbox:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sandbox not found")

    await forge_inngest.send(
        inngest.Event(
            name="forge/sandbox.lifecycle",
            data={
                "action": "start",
                "sandbox_id": str(sandbox_id),
                "northflank_service_id": sandbox.northflank_service_id,
            },
        )
    )


async def stop_sandbox(sandbox_id: uuid.UUID) -> None:
    """Fire event to stop a sandbox."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox).where(Sandbox.id == sandbox_id)
        )
        sandbox = result.scalar_one_or_none()

    if not sandbox:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sandbox not found")

    await forge_inngest.send(
        inngest.Event(
            name="forge/sandbox.lifecycle",
            data={
                "action": "stop",
                "sandbox_id": str(sandbox_id),
                "northflank_service_id": sandbox.northflank_service_id,
            },
        )
    )


async def destroy_sandbox(sandbox_id: uuid.UUID) -> None:
    """Fire event to destroy a sandbox."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox).where(Sandbox.id == sandbox_id)
        )
        sandbox = result.scalar_one_or_none()

    if not sandbox:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sandbox not found")

    await forge_inngest.send(
        inngest.Event(
            name="forge/sandbox.lifecycle",
            data={
                "action": "destroy",
                "sandbox_id": str(sandbox_id),
                "northflank_service_id": sandbox.northflank_service_id,
            },
        )
    )
