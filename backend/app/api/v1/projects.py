from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.services import project_service

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

@router.get("/{project_id}/files")
async def get_file(project_id: UUID, request: Request, path: str):
    content = await project_service.get_file(project_id, _user_id(request), path)
    return Response(content=content, media_type="application/octet-stream")


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
