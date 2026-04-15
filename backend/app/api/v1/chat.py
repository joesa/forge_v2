from __future__ import annotations

import json
import logging
from uuid import UUID

import anthropic
import openai
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
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
# Max output tokens per model family
ANTHROPIC_MAX_TOKENS = 64000  # claude-sonnet-4 limit
OPENAI_MAX_TOKENS = 16384


# ── Schemas ──────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    project_id: UUID
    messages: list[ChatMessage]
    active_file: str | None = None
    active_file_content: str | None = None
    is_auto_build: bool = False


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

    # For auto-build, use a minimal system prompt — the mega-prompt already has all context
    if body.is_auto_build:
        system_prompt = (
            "You are Forge AI, an expert full-stack developer. "
            "Follow the instructions in the user message exactly. "
            "Generate COMPLETE file contents in forge-edit blocks. "
            "NEVER stop early or skip files.\n\n"
            "IMPORTANT vite.config.ts RULE: ALWAYS include server.allowedHosts = true "
            "in the Vite config to prevent blocked-host errors in the preview sandbox.\n"
        )
    else:
        system_prompt = await _build_system_prompt(
            body.project_id, body.active_file, body.active_file_content
        )

    # Convert messages and truncate history to stay within token limits.
    # Anthropic claude-sonnet-4 has 200k context; we aim for ~120k input tokens (~480k chars)
    # to leave room for max_tokens output. Old assistant messages with large forge-edit blocks
    # are the primary cause of overflow.
    MAX_INPUT_CHARS = 400_000  # ~100k tokens, leaves room for max_tokens
    raw_messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Always keep the last user message. Trim from the beginning if over budget.
    total_chars = sum(len(m["content"]) for m in raw_messages) + len(system_prompt)
    messages = list(raw_messages)
    while total_chars > MAX_INPUT_CHARS and len(messages) > 1:
        removed = messages.pop(0)
        total_chars -= len(removed["content"])
        # Ensure messages still start with a user message (Anthropic requirement)
        while messages and messages[0]["role"] == "assistant":
            removed = messages.pop(0)
            total_chars -= len(removed["content"])

    if len(messages) < len(raw_messages):
        trimmed = len(raw_messages) - len(messages)
        logger.info("Chat context trimmed: dropped %d old messages to fit %d chars", trimmed, total_chars)

    async def _stream_anthropic():
        """Try Anthropic models with auto-continuation on max_tokens."""
        import asyncio

        if not settings.ANTHROPIC_API_KEY:
            yield ("fallback", None)
            return

        logger.info(
            "Anthropic stream: system_prompt=%d chars, messages=%d, total_user_chars=%d, is_auto_build=%s",
            len(system_prompt),
            len(messages),
            sum(len(m["content"]) for m in messages if m["role"] == "user"),
            body.is_auto_build,
        )

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        model = ANTHROPIC_MODELS[0]  # Use primary model for continuations
        max_continuations = 3 if body.is_auto_build else 1
        conv_messages = list(messages)  # mutable copy for continuations
        accumulated = ""

        # Dynamically compute max_tokens to stay within 200k context limit
        # Rough estimate: 1 token ≈ 4 chars
        est_input_tokens = (len(system_prompt) + sum(len(m["content"]) for m in conv_messages)) // 4
        effective_max_tokens = min(ANTHROPIC_MAX_TOKENS, max(4096, 195_000 - est_input_tokens))

        for continuation in range(max_continuations + 1):
            if continuation > 0:
                logger.info("Anthropic continuation %d/%d for model=%s", continuation, max_continuations, model)

            succeeded = False
            for m_idx, m in enumerate([model] if continuation > 0 else ANTHROPIC_MODELS):
                for attempt in range(3):
                    try:
                        async with client.messages.stream(
                            model=m,
                            max_tokens=effective_max_tokens,
                            system=system_prompt,
                            messages=conv_messages,
                        ) as stream:
                            async for text in stream.text_stream:
                                accumulated += text
                                yield ("text", text)
                            final_msg = await stream.get_final_message()

                        # Check if model hit output token limit
                        stop_reason = final_msg.stop_reason if final_msg else "end_turn"
                        if stop_reason == "max_tokens" and continuation < max_continuations:
                            logger.warning(
                                "Anthropic hit max_tokens (%d chars so far), continuing...",
                                len(accumulated),
                            )
                            # Append assistant output + continuation prompt
                            conv_messages.append({"role": "assistant", "content": accumulated})
                            conv_messages.append({
                                "role": "user",
                                "content": (
                                    "You were cut off mid-generation. Continue EXACTLY where you stopped. "
                                    "Do NOT repeat any files already generated. "
                                    "Do NOT add any preamble — resume the forge-edit block or start the next one immediately."
                                ),
                            })
                            succeeded = True
                            model = m  # lock model for continuations
                            break  # break attempt loop, continue outer continuation loop
                        else:
                            yield ("done", None)
                            return

                    except anthropic.APIStatusError as e:
                        if e.status_code == 529:
                            logger.warning("Anthropic %s overloaded (attempt %d/3)", m, attempt + 1)
                            await asyncio.sleep(2 ** attempt)
                            continue
                        if e.status_code == 400 and "context limit" in str(e):
                            logger.warning("Anthropic %s context too large, falling back: %s", m, e)
                            yield ("fallback", None)
                            return
                        logger.error("Anthropic APIStatusError (model=%s, status=%s): %s", m, e.status_code, e)
                        break
                    except anthropic.APIError as e:
                        logger.error("Anthropic APIError (model=%s): %s", m, e)
                        break
                    except Exception as e:
                        logger.error("Anthropic unexpected error (model=%s): %s: %s", m, type(e).__name__, e)
                        break
                else:
                    continue  # all attempts exhausted for this model, try next
                if succeeded:
                    break  # model succeeded, proceed to next continuation
                break  # model failed (non-529), stop trying
            else:
                # All models exhausted without success
                break

            if not succeeded:
                break  # Error occurred, fall through to OpenAI

        else:
            # Loop completed all continuations normally (shouldn't reach here without yield done/return)
            yield ("done", None)
            return

        # Signal that anthropic failed — caller should try OpenAI
        yield ("fallback", None)

    async def _stream_openai():
        """Try OpenAI as fallback. Yields (type, content) tuples."""
        if not settings.OPENAI_API_KEY:
            yield ("error", None)
            return

        logger.info("OpenAI fallback: model=%s", OPENAI_MODEL)
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # GPT-4o has 128k context but user may have low TPM limit.
        # Truncate to ~100k chars (~25k tokens) for the OpenAI fallback.
        OAI_MAX_CHARS = 100_000
        oai_msgs = list(messages)
        oai_sys = system_prompt
        total = len(oai_sys) + sum(len(m["content"]) for m in oai_msgs)
        # First: trim system prompt if huge (keep first 40k chars)
        if total > OAI_MAX_CHARS and len(oai_sys) > 40_000:
            oai_sys = oai_sys[:40_000] + "\n... (context truncated for token limits)"
            total = len(oai_sys) + sum(len(m["content"]) for m in oai_msgs)
        # Then trim old messages
        while total > OAI_MAX_CHARS and len(oai_msgs) > 1:
            removed = oai_msgs.pop(0)
            total -= len(removed["content"])
            while oai_msgs and oai_msgs[0]["role"] == "assistant":
                removed = oai_msgs.pop(0)
                total -= len(removed["content"])

        oai_messages = [{"role": "system", "content": oai_sys}] + oai_msgs

        try:
            stream = await client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=OPENAI_MAX_TOKENS,
                messages=oai_messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield ("text", delta.content)
            yield ("done", None)
        except Exception as e:
            logger.error("OpenAI API error (%s): %s: %s", OPENAI_MODEL, type(e).__name__, e)
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


# ── POST /api/v1/chat/auto-build/{project_id}/start ──────────────

@router.post("/auto-build/{project_id}/start")
async def auto_build_start(project_id: UUID, request: Request):
    """Return the assembled auto-build prompt so the frontend can stream it through normal chat."""
    uid = _user_id(request)

    # Verify user owns the project
    try:
        await project_service.get_project(project_id, uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.auto_build_service import (
        build_chat_auto_build_prompt,
        get_auto_build_status,
        set_auto_build_status,
    )

    # Don't start if already running or completed (prevents re-trigger on editor revisit)
    status = await get_auto_build_status(str(project_id))
    if status and status.get("status") in ("running", "completed"):
        return {"status": status["status"]}

    # Build the full auto-build prompt from pipeline context
    prompt = await build_chat_auto_build_prompt(str(project_id))
    if not prompt:
        return {"status": "none", "message": "No pipeline context available"}

    # Mark as running so subsequent calls don't re-trigger
    await set_auto_build_status(str(project_id), "running")
    return {"status": "started", "prompt": prompt}


# ── POST /api/v1/chat/auto-build/{project_id}/complete ────────────

@router.post("/auto-build/{project_id}/complete")
async def auto_build_complete(project_id: UUID, request: Request):
    """Mark auto-build as completed after chat streaming finishes."""
    uid = _user_id(request)

    try:
        await project_service.get_project(project_id, uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.auto_build_service import set_auto_build_status
    await set_auto_build_status(str(project_id), "completed")
    return {"status": "completed"}


# ── GET /api/v1/chat/auto-build/{project_id}/context ──────────────

@router.get("/auto-build/{project_id}/context")
async def auto_build_context(project_id: UUID, request: Request):
    """Return the full auto-build mega-prompt as a downloadable text file."""
    uid = _user_id(request)

    try:
        project = await project_service.get_project(project_id, uid)
    except Exception:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.auto_build_service import build_chat_auto_build_prompt

    prompt = await build_chat_auto_build_prompt(str(project_id))
    if not prompt:
        return Response(status_code=204)

    safe_name = (project.name or "project").replace(" ", "_").lower()
    filename = f"{safe_name}_build_context.md"

    return Response(
        content=prompt,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
