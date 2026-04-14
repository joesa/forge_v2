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
MAX_TOKENS = 16384


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
    """Build context-aware system prompt with project info and file contents."""
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
    files: list[str] = []
    file_tree = ""
    try:
        files = await storage_service.list_files_recursive(
            settings.SUPABASE_BUCKET_PROJECTS, str(project_id)
        )
        if files:
            tree_lines = [f"  {f}" for f in sorted(files[:100])]
            file_tree = f"Project files ({len(files)} total):\n" + "\n".join(tree_lines)
            if len(files) > 100:
                file_tree += f"\n  ... and {len(files) - 100} more files"
    except Exception:
        pass

    # Fetch contents of key source files so the AI can read them without asking the user
    SOURCE_EXTS = {
        ".ts", ".tsx", ".js", ".jsx", ".json", ".css", ".html",
        ".md", ".mjs", ".cjs", ".env.example",
    }
    SKIP_PATTERNS = {"node_modules/", "dist/", ".next/", "build/", ".git/", "lock"}
    MAX_FILE_SIZE = 8_000  # chars per file
    MAX_TOTAL_CONTEXT = 80_000  # total chars for all file contents
    bucket = settings.SUPABASE_BUCKET_PROJECTS
    prefix = str(project_id)

    file_contents_ctx = ""
    total_chars = 0
    files_included = 0

    # Prioritize: config/route files first, then components/pages, then the rest
    def _priority(path: str) -> int:
        lower = path.lower()
        if any(k in lower for k in ("route", "app.tsx", "app.jsx", "main.ts", "main.tsx", "index.ts", "index.tsx", "package.json", "tsconfig")):
            return 0
        if any(k in lower for k in ("layout", "config", "vite")):
            return 1
        if any(k in lower for k in ("page", "component", "hook")):
            return 2
        return 3

    source_files = [
        f for f in sorted(files)
        if any(f.endswith(ext) for ext in SOURCE_EXTS)
        and not any(skip in f for skip in SKIP_PATTERNS)
    ]
    source_files.sort(key=_priority)

    contents_parts: list[str] = []
    for rel_path in source_files:
        if total_chars >= MAX_TOTAL_CONTEXT:
            break
        try:
            raw = await storage_service.download_file(bucket, f"{prefix}/{rel_path}")
            text = raw.decode("utf-8", errors="replace")
            if len(text) > MAX_FILE_SIZE:
                text = text[:MAX_FILE_SIZE] + f"\n... (truncated, {len(raw)} bytes total)"
            contents_parts.append(f"### {rel_path}\n```\n{text}\n```\n")
            total_chars += len(text)
            files_included += 1
        except Exception:
            continue

    if contents_parts:
        file_contents_ctx = (
            f"\n## Project Source Files ({files_included} files loaded)\n"
            "You have access to all the source files below. "
            "Do NOT ask the user to open or share files — read them here.\n\n"
            + "\n".join(contents_parts)
        )

    active_ctx = ""
    if active_file and active_file_content:
        active_ctx = f"\nCurrently open file (user is viewing): {active_file}\n```\n{active_file_content[:5000]}\n```\n"

    return (
        "You are Forge AI, an expert full-stack developer assistant embedded in the Forge IDE. "
        "You help users modify, debug, and improve their web applications.\n\n"
        f"{project_ctx}"
        f"{file_tree}"
        f"{file_contents_ctx}"
        f"{active_ctx}\n"
        "## Code Edit Rules\n"
        "When making code changes, wrap EACH file change in a JSON block like:\n"
        '```forge-edit\n{"path": "src/file.tsx", "content": "full file content...", "description": "what changed"}\n```\n\n'
        "CRITICAL edit rules:\n"
        "1. Always provide the COMPLETE file content — never partial diffs or snippets.\n"
        "2. The 'path' must be relative to project root (e.g. 'src/routes.tsx', not '/app/src/routes.tsx').\n"
        "3. Before editing a file, consider its IMPORTS and EXPORTS. If you rename or move an export, "
        "you MUST also update every file that imports it. Check the file tree and file contents above.\n"
        "4. If your change adds a new import, verify the imported file/module exists in the file tree.\n"
        "5. Preserve ALL existing functionality unless the user explicitly asked to remove it.\n"
        "6. Use modern best practices: ESM imports, TypeScript, Tailwind CSS.\n"
        "7. Keep responses concise. Explain what you changed BEFORE the forge-edit block.\n"
        "8. If the user asks about the project structure, reference the file tree and source files above.\n"
        "9. You have full access to all project source files — NEVER ask the user to open or share a file. "
        "Read the contents from the context above and make your edits directly.\n"
        "10. When adding routes, components, or pages — ensure they are properly imported AND "
        "registered in the router/layout that renders them.\n"
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


# ── GET /api/v1/chat/auto-build/{project_id}/status ──────────────

@router.get("/auto-build/{project_id}/status")
async def auto_build_status(project_id: UUID, request: Request):
    """Check whether auto-build is running/completed for a project."""
    uid = _user_id(request)

    # Verify user owns the project
    try:
        await project_service.get_project(project_id, uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.auto_build_service import get_auto_build_status
    status = await get_auto_build_status(str(project_id))
    if status is None:
        return {"status": "none"}
    return status
