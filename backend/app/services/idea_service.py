from __future__ import annotations

import uuid

import inngest
from sqlalchemy import select

from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.idea import Idea
from app.models.idea_session import IdeaSession


async def start_idea_generation(
    session_id: uuid.UUID, user_id: uuid.UUID, answers: dict
) -> str:
    """Create an IdeaSession and fire forge/idea.generate. Returns session_id immediately."""
    async with get_write_session() as db:
        idea_session = IdeaSession(
            id=session_id,
            user_id=user_id,
            questionnaire_answers=answers,
            status="generating",
        )
        db.add(idea_session)

    await forge_inngest.send(
        inngest.Event(
            name="forge/idea.generate",
            data={
                "session_id": str(session_id),
                "user_id": str(user_id),
                "answers": answers,
            },
        )
    )
    return str(session_id)


async def get_ideas_for_session(session_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    async with get_read_session() as db:
        result = await db.execute(
            select(Idea).where(
                Idea.idea_session_id == session_id,
                Idea.user_id == user_id,
            )
        )
        ideas = result.scalars().all()
    return [
        {
            "id": str(idea.id),
            "title": idea.title,
            "description": idea.description,
            "tech_stack": idea.tech_stack,
            "market_analysis": idea.market_analysis,
            "status": idea.status,
        }
        for idea in ideas
    ]
