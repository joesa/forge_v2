from __future__ import annotations

import uuid

import inngest
from sqlalchemy import select

from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.project import Project
from app.models.sandbox import Sandbox, SandboxStatus


async def get_project_sandbox(project_id: uuid.UUID) -> str | None:
    """Return existing sandbox_id for a project, or None if no active sandbox."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox).where(
                Sandbox.project_id == project_id,
                Sandbox.status.in_([SandboxStatus.claimed, SandboxStatus.warm, SandboxStatus.building]),
            ).order_by(Sandbox.created_at.desc())
        )
        existing = result.scalars().first()
        return str(existing.id) if existing else None


async def wait_for_sandbox_ready(sandbox_id: str, timeout: float = 120, poll_interval: float = 3) -> bool:
    """Poll DB until sandbox has northflank_service_id and sandbox_url. Returns True if ready."""
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with get_read_session() as db:
            result = await db.execute(
                select(Sandbox).where(Sandbox.id == uuid.UUID(sandbox_id))
            )
            sandbox = result.scalar_one_or_none()
            if sandbox and sandbox.northflank_service_id and sandbox.sandbox_url:
                return True
        await asyncio.sleep(poll_interval)
    return False


async def claim_or_provision_sandbox(project_id: uuid.UUID) -> str:
    """Claim a warm sandbox or provision a new one. Returns sandbox_id.

    Flow:
      1. Check if project already has an active sandbox → return it
      2. Try to claim a warm sandbox from the pool
      3. If no warm sandbox available, provision a new one
    """
    # 1. Existing sandbox for this project?
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox).where(
                Sandbox.project_id == project_id,
                Sandbox.status.in_([SandboxStatus.claimed, SandboxStatus.warm, SandboxStatus.building]),
            ).order_by(Sandbox.created_at.desc())
        )
        existing = result.scalars().first()
        if existing:
            # Re-trigger provisioning if container was never created
            if not existing.northflank_service_id:
                await forge_inngest.send(
                    inngest.Event(
                        name="forge/sandbox.lifecycle",
                        data={
                            "action": "provision",
                            "sandbox_id": str(existing.id),
                            "project_id": str(project_id),
                        },
                    )
                )
            return str(existing.id)

    # 2. Claim a warm sandbox
    async with get_write_session() as db:
        result = await db.execute(
            select(Sandbox)
            .where(Sandbox.status == SandboxStatus.warm, Sandbox.project_id.is_(None))
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        warm = result.scalar_one_or_none()
        if warm:
            warm.project_id = project_id
            warm.status = SandboxStatus.claimed
            sandbox_id = str(warm.id)

            # Send start event to configure the sandbox with project files
            await forge_inngest.send(
                inngest.Event(
                    name="forge/sandbox.lifecycle",
                    data={
                        "action": "start",
                        "sandbox_id": sandbox_id,
                        "project_id": str(project_id),
                        "northflank_service_id": warm.northflank_service_id,
                    },
                )
            )
            return sandbox_id

    # 3. Provision fresh
    return await provision_sandbox(project_id)


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


async def start_sandbox(sandbox_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire event to start/claim a sandbox. Verifies ownership."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox)
            .join(Project, Sandbox.project_id == Project.id)
            .where(Sandbox.id == sandbox_id, Project.user_id == user_id)
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


async def stop_sandbox(sandbox_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire event to stop a sandbox. Verifies ownership."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox)
            .join(Project, Sandbox.project_id == Project.id)
            .where(Sandbox.id == sandbox_id, Project.user_id == user_id)
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


async def destroy_sandbox(sandbox_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Fire event to destroy a sandbox. Verifies ownership."""
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox)
            .join(Project, Sandbox.project_id == Project.id)
            .where(Sandbox.id == sandbox_id, Project.user_id == user_id)
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
