"""Annotation service — point-and-click feedback on preview screenshots."""
from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.database import get_read_session, get_write_session
from app.models.annotation import Annotation

logger = logging.getLogger(__name__)


async def create_annotation(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    css_selector: str,
    route: str,
    comment: str,
    x_pct: float,
    y_pct: float,
    editor_session_id: uuid.UUID | None = None,
) -> dict:
    """Create a new annotation. Validates coordinate percentages."""
    if not (0.0 <= x_pct <= 1.0):
        raise HTTPException(
            status_code=400,
            detail=f"x_pct must be between 0.0 and 1.0, got {x_pct}",
        )
    if not (0.0 <= y_pct <= 1.0):
        raise HTTPException(
            status_code=400,
            detail=f"y_pct must be between 0.0 and 1.0, got {y_pct}",
        )

    async with get_write_session() as session:
        annotation = Annotation(
            project_id=project_id,
            user_id=user_id,
            css_selector=css_selector,
            route=route,
            comment=comment,
            x_pct=x_pct,
            y_pct=y_pct,
            editor_session_id=editor_session_id,
        )
        session.add(annotation)
        await session.flush()
        await session.refresh(annotation)
        return _to_dict(annotation)


async def get_annotations(
    project_id: uuid.UUID,
    resolved: bool | None = None,
) -> list[dict]:
    """Get annotations for a project, optionally filtering by resolved status."""
    async with get_read_session() as session:
        stmt = (
            select(Annotation)
            .where(Annotation.project_id == project_id)
            .order_by(Annotation.created_at.desc())
        )
        if resolved is not None:
            stmt = stmt.where(Annotation.resolved == resolved)
        result = await session.execute(stmt)
        return [_to_dict(a) for a in result.scalars().all()]


async def resolve_annotation(
    annotation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Mark an annotation as resolved."""
    async with get_write_session() as session:
        result = await session.execute(
            select(Annotation).where(
                Annotation.id == annotation_id,
                Annotation.user_id == user_id,
            )
        )
        annotation = result.scalar_one_or_none()
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")

        annotation.resolved = True
        annotation.status = "resolved"
        await session.flush()
        await session.refresh(annotation)
        return _to_dict(annotation)


async def delete_annotation(
    annotation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a single annotation."""
    async with get_write_session() as session:
        result = await session.execute(
            select(Annotation).where(
                Annotation.id == annotation_id,
                Annotation.user_id == user_id,
            )
        )
        annotation = result.scalar_one_or_none()
        if annotation is None:
            raise HTTPException(status_code=404, detail="Annotation not found")
        await session.delete(annotation)


async def clear_annotations(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """Delete all annotations for a project. Returns count deleted."""
    async with get_write_session() as session:
        result = await session.execute(
            select(Annotation).where(
                Annotation.project_id == project_id,
                Annotation.user_id == user_id,
            )
        )
        annotations = result.scalars().all()
        count = len(annotations)
        for a in annotations:
            await session.delete(a)
        return count


async def get_annotations_for_ai_context(project_id: uuid.UUID) -> str:
    """Get unresolved annotations formatted for AI context.

    Returns EMPTY STRING (not None) if no unresolved annotations.
    """
    async with get_read_session() as session:
        result = await session.execute(
            select(Annotation).where(
                Annotation.project_id == project_id,
                Annotation.resolved == False,  # noqa: E712
            ).order_by(Annotation.created_at)
        )
        annotations = result.scalars().all()

    if not annotations:
        return ""

    lines: list[str] = ["User annotations (unresolved):"]
    for a in annotations:
        lines.append(
            f"- [{a.route}] ({a.x_pct:.0%}, {a.y_pct:.0%}) "
            f"selector={a.css_selector}: {a.comment}"
        )
    return "\n".join(lines)


def _to_dict(a: Annotation) -> dict:
    return {
        "id": str(a.id),
        "project_id": str(a.project_id),
        "user_id": str(a.user_id),
        "css_selector": a.css_selector,
        "route": a.route,
        "comment": a.comment,
        "x_pct": a.x_pct,
        "y_pct": a.y_pct,
        "resolved": a.resolved,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
