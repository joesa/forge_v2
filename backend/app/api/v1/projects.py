from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel

from app.services import project_service, storage_service, file_sync_service
from app.config import settings

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ── Schemas ──────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    framework: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    framework: str | None = None


class FileRename(BaseModel):
    old_path: str
    new_path: str


def _user_id(request: Request) -> UUID:
    return request.state.user_id


def _is_service(request: Request) -> bool:
    return getattr(request.state, "is_service", False)


async def _get_project_sandbox_id(project_id: UUID, user_id: UUID) -> UUID | None:
    """Find an active sandbox for this project (if any)."""
    from sqlalchemy import select
    from app.core.database import get_read_session
    from app.models.sandbox import Sandbox, SandboxStatus
    async with get_read_session() as db:
        result = await db.execute(
            select(Sandbox.id).where(
                Sandbox.project_id == project_id,
                Sandbox.status.in_([SandboxStatus.warm, SandboxStatus.claimed, SandboxStatus.building]),
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        return row


# ── Project CRUD ─────────────────────────────────────────────────

@router.get("")
async def list_projects(request: Request):
    projects = await project_service.list_projects(_user_id(request))
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "status": p.status.value if p.status else None,
            "framework": p.framework.value if p.framework else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in projects
    ]


@router.post("", status_code=201)
async def create_project(request: Request, body: ProjectCreate):
    project = await project_service.create_project(
        _user_id(request), body.name, body.framework, body.description
    )
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status.value if project.status else None,
        "framework": project.framework.value if project.framework else None,
    }


@router.get("/{project_id}")
async def get_project(project_id: UUID, request: Request):
    project = await project_service.get_project(project_id, _user_id(request))
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status.value if project.status else None,
        "framework": project.framework.value if project.framework else None,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.put("/{project_id}")
async def update_project(project_id: UUID, request: Request, body: ProjectUpdate):
    fields = body.model_dump(exclude_unset=True)
    project = await project_service.update_project(project_id, _user_id(request), **fields)
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status.value if project.status else None,
        "framework": project.framework.value if project.framework else None,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID, request: Request):
    await project_service.delete_project(project_id, _user_id(request))
    return Response(status_code=204)


# ── File operations ──────────────────────────────────────────────

def _build_tree(paths: list[str]) -> list[dict]:
    """Convert flat file paths into a nested FileNode tree."""
    root: dict[str, dict] = {}
    for p in paths:
        parts = p.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {"_children": {}})["_children"]
        node[parts[-1]] = {"_leaf": True}

    def _to_nodes(tree: dict, parent_path: str = "") -> list[dict]:
        nodes: list[dict] = []
        for name, value in sorted(tree.items()):
            if name.startswith("_"):
                continue
            full = f"{parent_path}/{name}" if parent_path else name
            if value.get("_leaf"):
                nodes.append({"path": full, "name": name, "type": "file"})
            else:
                children = _to_nodes(value.get("_children", {}), full)
                nodes.append({"path": full, "name": name, "type": "dir", "children": children})
        return nodes

    return _to_nodes(root)


@router.get("/{project_id}/files")
async def get_files(
    project_id: UUID,
    request: Request,
    path: str | None = Query(default=None),
    flat: bool = Query(default=False),
):
    if not _is_service(request):
        uid = _user_id(request)
        if path is None:
            await project_service.get_project(project_id, uid)  # ownership check
    if path is None:
        raw = await storage_service.list_files_recursive(settings.SUPABASE_BUCKET_PROJECTS, str(project_id))
        # Filter out build snapshot directories (UUID-named dirs containing build.json)
        import re
        _uuid_dir = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/", re.I)
        raw = [p for p in raw if not _uuid_dir.match(p)]
        if flat:
            return [{"name": p.rsplit("/", 1)[-1], "type": "file", "path": p} for p in raw]
        return _build_tree(raw)
    # Single file download (raw bytes)
    if _is_service(request):
        content = await storage_service.download_file(settings.SUPABASE_BUCKET_PROJECTS, f"{project_id}/{path}")
    else:
        content = await project_service.get_file(project_id, _user_id(request), path)
    return Response(content=content, media_type="application/octet-stream")


class FileContentUpdate(BaseModel):
    path: str
    content: str


@router.get("/{project_id}/files/content")
async def get_file_content(project_id: UUID, request: Request, path: str = Query()):
    if _is_service(request):
        content = await storage_service.download_file(settings.SUPABASE_BUCKET_PROJECTS, f"{project_id}/{path}")
    else:
        content = await project_service.get_file(project_id, _user_id(request), path)
    return {"content": content.decode("utf-8", errors="replace")}


@router.put("/{project_id}/files/content")
async def put_file_content(project_id: UUID, request: Request, body: FileContentUpdate):
    uid = _user_id(request)
    url = await project_service.put_file(
        project_id, uid, body.path, body.content.encode("utf-8"), "text/plain"
    )
    # Sync to sandbox
    sync_result = None
    sandbox_id = await _get_project_sandbox_id(project_id, uid)
    if sandbox_id:
        sync_result = await file_sync_service.sync_file(sandbox_id, body.path, body.content)
    else:
        import logging
        logging.getLogger(__name__).warning(
            "put_file_content: no active sandbox for project=%s — file saved but not synced", project_id
        )
    synced = sync_result.get("receivers", 0) > 0 if sync_result else False
    return {
        "url": url,
        "synced": synced,
        "sync_method": sync_result.get("method") if sync_result else None,
    }


@router.put("/{project_id}/files")
async def put_file(project_id: UUID, request: Request, path: str):
    body = await request.body()
    url = await project_service.put_file(project_id, _user_id(request), path, body)
    return {"url": url}


@router.delete("/{project_id}/files", status_code=204)
async def delete_file(project_id: UUID, request: Request, path: str):
    await project_service.delete_file(project_id, _user_id(request), path)
    return Response(status_code=204)


@router.post("/{project_id}/files/rename")
async def rename_file(project_id: UUID, request: Request, body: FileRename):
    url = await project_service.rename_file(
        project_id, _user_id(request), body.old_path, body.new_path
    )
    return {"url": url}
