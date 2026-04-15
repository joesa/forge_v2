"""Idea generation API — create sessions, trigger generation, fetch results."""
from __future__ import annotations

import uuid
from typing import Any

import inngest
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.idea import Idea
from app.models.idea_session import IdeaSession

router = APIRouter(prefix="/api/v1/ideas", tags=["ideas"])


def _user_id(request: Request) -> uuid.UUID:
    return request.state.user_id


class GenerateRequest(BaseModel):
    answers: dict[str, Any]


class IdeaResponse(BaseModel):
    id: str
    title: str
    tagline: str
    uniqueness: float
    complexity: float
    problem: str
    solution: str
    market: str
    revenue: str
    stack: list[str]
    description: str
    saved: bool


class SessionResponse(BaseModel):
    session_id: str
    status: str
    ideas: list[IdeaResponse]


@router.post("/generate")
async def generate_ideas(body: GenerateRequest, request: Request) -> dict[str, str]:
    """Create an idea session and trigger async AI generation."""
    user_id = _user_id(request)

    # Create session
    session_id = uuid.uuid4()
    async with get_write_session() as db:
        session = IdeaSession(
            id=session_id,
            user_id=user_id,
            questionnaire_answers=body.answers,
            status="generating",
        )
        db.add(session)

    # Trigger Inngest function
    await forge_inngest.send(inngest.Event(
        name="forge/idea.generate",
        data={
            "session_id": str(session_id),
            "user_id": str(user_id),
            "answers": body.answers,
        },
    ))

    return {"session_id": str(session_id), "status": "generating"}


@router.get("/session/{session_id}")
async def get_session(session_id: str, request: Request) -> SessionResponse:
    """Poll a session for status + ideas."""
    user_id = _user_id(request)
    sid = uuid.UUID(session_id)

    async with get_read_session() as db:
        result = await db.execute(
            select(IdeaSession).where(
                IdeaSession.id == sid,
                IdeaSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        ideas: list[IdeaResponse] = []
        if session.completed:
            idea_result = await db.execute(
                select(Idea).where(Idea.idea_session_id == sid).order_by(Idea.created_at)
            )
            for row in idea_result.scalars().all():
                ma = row.market_analysis or {}
                ideas.append(IdeaResponse(
                    id=str(row.id),
                    title=row.title,
                    tagline=ma.get("tagline", row.description[:80]),
                    uniqueness=ma.get("uniqueness", 7.0),
                    complexity=ma.get("complexity", 5.0),
                    problem=ma.get("problem", ""),
                    solution=ma.get("solution", ""),
                    market=ma.get("market", "N/A"),
                    revenue=ma.get("revenue", "N/A"),
                    stack=ma.get("stack", list(row.tech_stack.values())[:4] if isinstance(row.tech_stack, dict) else []),
                    description=row.description,
                    saved=row.saved,
                ))

        return SessionResponse(
            session_id=str(sid),
            status=session.status,
            ideas=ideas,
        )


@router.patch("/{idea_id}/save")
async def toggle_save(idea_id: str, request: Request) -> dict[str, bool]:
    """Toggle saved status of an idea."""
    user_id = _user_id(request)
    iid = uuid.UUID(idea_id)

    async with get_write_session() as db:
        result = await db.execute(
            select(Idea).where(Idea.id == iid, Idea.user_id == user_id)
        )
        idea = result.scalar_one_or_none()
        if not idea:
            raise HTTPException(status_code=404, detail="Idea not found")
        idea.saved = not idea.saved
        return {"saved": idea.saved}


@router.get("/latest")
async def get_latest_session(request: Request) -> SessionResponse:
    """Get the most recent idea session for the current user."""
    user_id = _user_id(request)

    async with get_read_session() as db:
        result = await db.execute(
            select(IdeaSession)
            .where(IdeaSession.user_id == user_id)
            .order_by(IdeaSession.created_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if not session:
            return SessionResponse(session_id="", status="none", ideas=[])

        ideas: list[IdeaResponse] = []
        if session.completed:
            idea_result = await db.execute(
                select(Idea).where(Idea.idea_session_id == session.id).order_by(Idea.created_at)
            )
            for row in idea_result.scalars().all():
                ma = row.market_analysis or {}
                ideas.append(IdeaResponse(
                    id=str(row.id),
                    title=row.title,
                    tagline=ma.get("tagline", row.description[:80]),
                    uniqueness=ma.get("uniqueness", 7.0),
                    complexity=ma.get("complexity", 5.0),
                    problem=ma.get("problem", ""),
                    solution=ma.get("solution", ""),
                    market=ma.get("market", "N/A"),
                    revenue=ma.get("revenue", "N/A"),
                    stack=ma.get("stack", list(row.tech_stack.values())[:4] if isinstance(row.tech_stack, dict) else []),
                    description=row.description,
                    saved=row.saved,
                ))

        return SessionResponse(
            session_id=str(session.id),
            status=session.status,
            ideas=ideas,
        )
