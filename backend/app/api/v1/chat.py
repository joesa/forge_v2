from __future__ import annotations

import json
import logging
from uuid import UUID

import anthropic
import openai
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.core.database import get_read_session
from app.services import project_service, storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Anthropic models (tried first, in order)
ANTHROPIC_MODELS = ["claude-sonnet-4-20250514", "claude-3-haiku-20240307"]
# OpenAI fallback model
OPENAI_MODEL = "gpt-4o"
MAX_TOKENS = 4096


# ── Schemas ──────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    project_id: UUID
    messages: list[ChatMessage]
    active_file: str | None = None
    active_file_content: str | None = None


class ChatFileEdit(BaseModel):
    path: str
    content: str
    description: str


# ── Helpers ──────────────────────────────────────────────────────

def _user_id(request: Request) -> UUID:
    return request.state.user_id


async def _build_system_prompt(project_id: UUID, active_file: str | None, active_file_content: str | None) -> str:
    """Build context-aware system prompt with project info."""
    # Fetch project details
    async with get_read_session() as db:
        from sqlalchemy import select
        from app.models.project import Project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()

    project_ctx = ""
    if project:
        project_ctx = f"Project: {project.name}\nDescription: {project.description or 'N/A'}\nFramework: {project.framework.value}\n"

    # Fetch file tree for context
    file_tree = ""
    try:
        files = await storage_service.list_files_recursive(
            settings.SUPABASE_BUCKET_PROJECTS, str(project_id)
        )
        if files:
            file_tree = "Project files:\n" + "\n".join(f"  {f}" for f in files[:50])
    except Exception:
        pass

    active_ctx = ""
    if active_file and active_file_content:
        active_ctx = f"\nCurrently open file: {active_file}\n```\n{active_file_content[:3000]}\n```\n"

    return (
        "You are Forge AI, an expert full-stack developer assistant embedded in the Forge IDE. "
        "You help users modify, debug, and improve their web applications.\n\n"
        f"{project_ctx}"
        f"{file_tree}"
        f"{active_ctx}\n"
        "Guidelines:\n"
        "- When suggesting code changes, wrap each file change in a JSON block like:\n"
        '  ```forge-edit\n{"path": "src/file.tsx", "content": "full file content...", "description": "what changed"}\n```\n'
        "- Always provide complete file contents in edits, not partial diffs.\n"
        "- Use modern best practices: ESM imports, TypeScript, Tailwind CSS.\n"
        "- Keep responses concise and actionable.\n"
        "- If the user asks about the project structure, reference the file tree above."
    )


# ── POST /api/v1/chat/message ────────────────────────────────────

@router.post("/message")
async def chat_message(request: Request, body: ChatRequest):
    """Stream a chat response using Anthropic Claude."""
    uid = _user_id(request)

    # Verify user owns the project
    try:
        await project_service.get_project(body.project_id, uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    if not settings.ANTHROPIC_API_KEY and not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Chat service not configured")

    system_prompt = await _build_system_prompt(
        body.project_id, body.active_file, body.active_file_content
    )

    # Convert messages
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def _stream_anthropic():
        """Try Anthropic models. Yields (type, content) tuples."""
        import asyncio

        if not settings.ANTHROPIC_API_KEY:
            yield ("fallback", None)
            return

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        for model in ANTHROPIC_MODELS:
            for attempt in range(3):
                try:
                    async with client.messages.stream(
                        model=model,
                        max_tokens=MAX_TOKENS,
                        system=system_prompt,
                        messages=messages,
                    ) as stream:
                        async for text in stream.text_stream:
                            yield ("text", text)
                    yield ("done", None)
                    return
                except anthropic.APIStatusError as e:
                    if e.status_code == 529:
                        logger.warning("Anthropic %s overloaded (attempt %d/3)", model, attempt + 1)
                        await asyncio.sleep(2 ** attempt)
                        continue
                    logger.error("Anthropic API error (model=%s): %s", model, e)
                    break
                except anthropic.APIError as e:
                    logger.error("Anthropic API error (model=%s): %s", model, e)
                    break
            else:
                continue
            break
        # Signal that anthropic failed — caller should try OpenAI
        yield ("fallback", None)

    async def _stream_openai():
        """Try OpenAI as fallback. Yields (type, content) tuples."""
        if not settings.OPENAI_API_KEY:
            yield ("error", None)
            return

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        oai_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            stream = await client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=MAX_TOKENS,
                messages=oai_messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield ("text", delta.content)
            yield ("done", None)
        except Exception as e:
            logger.error("OpenAI API error: %s", e)
            yield ("error", None)

    async def _stream():
        used_openai = False
        async for event_type, content in _stream_anthropic():
            if event_type == "text":
                yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
            elif event_type == "done":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            elif event_type == "fallback":
                used_openai = True
                break

        # Anthropic exhausted — try OpenAI
        if used_openai or not settings.ANTHROPIC_API_KEY:
            logger.info("Falling back to OpenAI %s", OPENAI_MODEL)
            async for event_type, content in _stream_openai():
                if event_type == "text":
                    yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"
                elif event_type == "done":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return

        # All providers failed
        yield f"data: {json.dumps({'type': 'error', 'content': 'AI service is temporarily unavailable. Please try again in a moment.'})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
