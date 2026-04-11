from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.core.sanitize import sanitize_path
from app.models.project import Project
from app.services import storage_service


_BUCKET = settings.SUPABASE_BUCKET_PROJECTS


async def list_projects(user_id: UUID) -> list[Project]:
    async with get_read_session() as session:
        result = await session.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.updated_at.desc())
        )
        return list(result.scalars().all())


async def create_project(
    user_id: UUID, name: str, framework: str, description: str | None = None
) -> Project:
    async with get_write_session() as session:
        project = Project(
            user_id=user_id,
            name=name,
            framework=framework,
            description=description,
        )
        session.add(project)
        await session.flush()
        await session.refresh(project)
        return project


async def get_project(project_id: UUID, user_id: UUID) -> Project:
    async with get_read_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project


async def update_project(
    project_id: UUID, user_id: UUID, **fields
) -> Project:
    async with get_write_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        for key, value in fields.items():
            if value is not None:
                setattr(project, key, value)
        await session.flush()
        await session.refresh(project)
        return project


async def delete_project(project_id: UUID, user_id: UUID) -> None:
    async with get_write_session() as session:
        result = await session.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        await session.delete(project)


# ── File operations ──────────────────────────────────────────────

def _storage_key(project_id: UUID, path: str) -> str:
    safe = sanitize_path(path)
    return f"{project_id}/{safe}"


async def get_file(project_id: UUID, user_id: UUID, path: str) -> bytes:
    await get_project(project_id, user_id)  # ownership check
    key = _storage_key(project_id, path)
    return await storage_service.download_file(_BUCKET, key)


async def put_file(
    project_id: UUID, user_id: UUID, path: str, content: bytes, content_type: str = "application/octet-stream"
) -> str:
    await get_project(project_id, user_id)  # ownership check
    key = _storage_key(project_id, path)
    return await storage_service.upload_file(_BUCKET, key, content, content_type)


async def delete_file(project_id: UUID, user_id: UUID, path: str) -> None:
    await get_project(project_id, user_id)  # ownership check
    key = _storage_key(project_id, path)
    await storage_service.delete_file(_BUCKET, key)


async def rename_file(
    project_id: UUID, user_id: UUID, old_path: str, new_path: str
) -> str:
    await get_project(project_id, user_id)  # ownership check
    old_key = _storage_key(project_id, old_path)
    new_key = _storage_key(project_id, new_path)
    content = await storage_service.download_file(_BUCKET, old_key)
    url = await storage_service.upload_file(_BUCKET, new_key, content)
    await storage_service.delete_file(_BUCKET, old_key)
    return url
