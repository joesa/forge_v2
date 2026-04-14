"""Auto-build service — builds the full application via AI Editor after pipeline completes.

After the pipeline produces a solid foundation (scaffold), this service assembles
ALL pipeline context (C-Suite analysis, synthesis, spec, bootstrap, build manifest)
into a rich prompt and sends it to the AI to generate the complete, production-quality
application. Files are written directly to Supabase Storage and synced to the sandbox
so the user sees them streaming when they open the Editor.
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

import anthropic
import openai

from app.config import settings
from app.core.database import get_read_session
from app.core.redis import redis_client
from app.services import storage_service
from app.services.file_sync_service import sync_file

logger = logging.getLogger(__name__)

ANTHROPIC_MODELS = ["claude-sonnet-4-20250514", "claude-3-haiku-20240307"]
OPENAI_MODEL = "gpt-4o"
ANTHROPIC_MAX_TOKENS = 64000  # claude-sonnet-4 limit
OPENAI_MAX_TOKENS = 16384


# ── Status tracking via Redis ────────────────────────────────────

async def set_auto_build_status(project_id: str, status: str, *, detail: dict | None = None) -> None:
    """Store auto-build status in Redis for frontend polling."""
    if redis_client is None:
        return
    data: dict[str, Any] = {"status": status, "timestamp_ms": int(time.time() * 1000)}
    if detail:
        data.update(detail)
    await redis_client.set(f"autobuild:{project_id}", json.dumps(data), ex=3600)


async def get_auto_build_status(project_id: str) -> dict | None:
    """Read auto-build status from Redis."""
    if redis_client is None:
        return None
    raw = await redis_client.get(f"autobuild:{project_id}")
    if raw:
        return json.loads(raw)
    return None


async def _publish_progress(project_id: str, event: dict) -> None:
    """Publish auto-build progress to the editor channel."""
    if redis_client is None:
        return
    event["timestamp_ms"] = int(time.time() * 1000)
    await redis_client.publish(f"autobuild:{project_id}", json.dumps(event))


# ── Context assembly ─────────────────────────────────────────────

async def _load_pipeline_context(project_id: str) -> dict | None:
    """Load pipeline_context.json from Supabase Storage."""
    try:
        raw = await storage_service.download_file(
            settings.SUPABASE_BUCKET_PROJECTS,
            f"{project_id}/pipeline_context.json",
        )
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        logger.error("Failed to load pipeline context for %s: %s", project_id, e)
        return None


async def _load_current_files(project_id: str) -> dict[str, str]:
    """Load all current source files from storage so AI knows the scaffold."""
    files: dict[str, str] = {}
    try:
        all_paths = await storage_service.list_files_recursive(
            settings.SUPABASE_BUCKET_PROJECTS, project_id
        )
        SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".json", ".css", ".html", ".md", ".mjs"}
        SKIP = {"node_modules/", "dist/", ".next/", "build/", "pipeline_context.json", "/build.json"}

        for path in sorted(all_paths):
            if any(s in path for s in SKIP):
                continue
            if not any(path.endswith(ext) for ext in SOURCE_EXTS):
                continue
            try:
                raw = await storage_service.download_file(
                    settings.SUPABASE_BUCKET_PROJECTS,
                    f"{project_id}/{path}",
                )
                text = raw.decode("utf-8", errors="replace")
                if len(text) < 10_000:
                    files[path] = text
            except Exception:
                continue
    except Exception as e:
        logger.warning("Failed to list files for %s: %s", project_id, e)
    return files


def _build_auto_build_prompt(ctx: dict, current_files: dict[str, str]) -> str:
    """Assemble the rich mega-prompt from pipeline context."""
    idea = ctx.get("idea_spec", {})
    design = ctx.get("design_architecture", {})
    csuite = ctx.get("csuite_outputs", {})
    plan = ctx.get("comprehensive_plan", {})
    spec = ctx.get("spec_outputs", {})
    manifest = ctx.get("build_manifest", {})

    sections: list[str] = []

    # App identity
    sections.append(f"# Application: {idea.get('name', 'App')}")
    sections.append(f"**Description**: {idea.get('description', '')}")
    if idea.get("product_type"):
        sections.append(f"**Type**: {idea['product_type']}")
    if idea.get("target_audience"):
        sections.append(f"**Target Audience**: {idea['target_audience']}")

    # Design Architecture
    if design:
        sections.append("\n## Design Architecture")
        if design.get("product_overview"):
            sections.append(f"**Product Overview**: {json.dumps(design['product_overview'], indent=2)}")
        if design.get("design_framework"):
            sections.append(f"**Design Framework**: {json.dumps(design['design_framework'], indent=2)}")
        if design.get("design_tokens"):
            sections.append(f"**Design Tokens**: {json.dumps(design['design_tokens'], indent=2)}")
        if design.get("layout"):
            sections.append(f"**Layout**: {json.dumps(design['layout'], indent=2)}")
        if design.get("pages"):
            sections.append(f"**Pages**: {json.dumps(design['pages'], indent=2)}")
        if design.get("component_library"):
            sections.append(f"**Components**: {json.dumps(design['component_library'], indent=2)}")
        if design.get("entities"):
            sections.append(f"**Entities**: {json.dumps(design['entities'], indent=2)}")
        if design.get("interactions"):
            sections.append(f"**Interactions**: {json.dumps(design['interactions'], indent=2)}")
        if design.get("builder_prompt"):
            sections.append(f"\n**Builder Prompt**:\n{design['builder_prompt']}")

    # C-Suite Analysis
    if csuite:
        sections.append("\n## C-Suite Executive Analysis")
        for role, output in csuite.items():
            sections.append(f"\n### {role.upper()}")
            if isinstance(output, dict):
                for k, v in output.items():
                    if v and k != "_error":
                        sections.append(f"**{k}**: {json.dumps(v, indent=2) if isinstance(v, (dict, list)) else v}")

    # Comprehensive Plan (synthesis output)
    if plan:
        sections.append("\n## Comprehensive Build Plan")
        for key in ["pages", "entities", "features", "components", "api_routes"]:
            val = plan.get(key)
            if val:
                sections.append(f"**{key}**: {json.dumps(val, indent=2)}")

    # Spec Layer
    if spec:
        sections.append("\n## Technical Specifications")
        if spec.get("openapi_spec"):
            sections.append(f"**OpenAPI Spec**: {json.dumps(spec['openapi_spec'], indent=2)}")
        if spec.get("ts_interfaces"):
            sections.append(f"**TypeScript Interfaces**:\n```typescript\n{spec['ts_interfaces']}\n```")
        if spec.get("zod_schemas"):
            sections.append(f"**Zod Schemas**:\n```typescript\n{spec['zod_schemas']}\n```")

    # Build Manifest
    if manifest:
        sections.append("\n## Build Manifest")
        if manifest.get("dependencies"):
            sections.append(f"**Dependencies**: {json.dumps(manifest['dependencies'], indent=2)}")
        if manifest.get("file_tree"):
            sections.append(f"**File Tree**: {json.dumps(manifest['file_tree'], indent=2)}")

    # Current scaffold files
    if current_files:
        sections.append("\n## Current Scaffold Files (generated by pipeline)")
        sections.append("These files exist but are minimal/generic. You must COMPLETELY REWRITE them")
        sections.append("with full, production-quality implementations based on the specs above.")
        for path, content in sorted(current_files.items()):
            sections.append(f"\n### {path}\n```\n{content}\n```")

    return "\n".join(sections)


SYSTEM_PROMPT = """\
You are Forge AI, an expert full-stack developer. You are performing an automatic build \
of a complete web application based on the detailed analysis and specifications provided below.

Your job is to transform the minimal scaffold into a FULL, PRODUCTION-QUALITY application \
that matches ALL the specifications from the C-Suite analysis, design architecture, and build plan.

## CRITICAL RULES
1. Wrap EACH file in a forge-edit block:
```forge-edit
{"path": "src/file.tsx", "content": "full file content...", "description": "what this file does"}
```
2. ALWAYS provide COMPLETE file content — never partial or placeholder.
3. Paths must be relative to project root (e.g. 'src/App.tsx').
4. Build a RICH, VISUALLY STUNNING application — not a generic template.
5. Use the design tokens (colors, typography, spacing) from the Design Architecture.
6. Implement ALL pages, components, entities, and features from the Build Plan.
7. Use the exact dependencies listed in the Build Manifest.
8. Make the app feel like a real product — loading states, animations, proper layouts.
9. Use Tailwind CSS classes matching the design tokens.
10. Implement proper routing with react-router-dom.
11. Add real data types matching the entity definitions.
12. Create actual UI components — not "Coming Soon" placeholders.

## OUTPUT ORDER
Generate files in this order:
1. package.json (with ALL dependencies from manifest)
2. Config files (vite, tailwind, tsconfig, postcss)
3. Type definitions / interfaces
4. Utility files and helpers
5. Layout components (header, footer, sidebar)
6. Shared UI components
7. Page components (with full content, not placeholders)
8. Main app entry (App.tsx with routes, main.tsx)
9. CSS / style files (index.css with proper theming)

START GENERATING NOW. Output each file as a forge-edit block.
"""


async def build_chat_auto_build_prompt(project_id: str) -> str | None:
    """Build the full auto-build prompt (instructions + pipeline context) for chat submission."""
    ctx = await _load_pipeline_context(project_id)

    # Fallback: if pipeline_context.json is missing, build minimal context from DB
    if not ctx:
        ctx = await _fallback_context_from_db(project_id)

    if not ctx:
        return None
    current_files = await _load_current_files(project_id)
    context_prompt = _build_auto_build_prompt(ctx, current_files)
    return f"{SYSTEM_PROMPT}\n\n{context_prompt}"


async def _fallback_context_from_db(project_id: str) -> dict | None:
    """Build a minimal pipeline context from the DB when the storage file is missing."""
    try:
        from app.models.pipeline_run import PipelineRun, PipelineStatus
        from sqlalchemy import select

        async with get_read_session() as db:
            result = await db.execute(
                select(PipelineRun).where(
                    PipelineRun.project_id == project_id,
                    PipelineRun.status == PipelineStatus.completed,
                ).order_by(PipelineRun.created_at.desc()).limit(1)
            )
            run = result.scalar_one_or_none()
            if not run or not run.idea_spec:
                return None

            logger.info("Using fallback DB context for project %s (pipeline %s)", project_id, run.id)
            return {
                "idea_spec": run.idea_spec,
                "design_architecture": {},
                "csuite_outputs": {},
                "comprehensive_plan": {},
                "spec_outputs": {},
                "build_manifest": {},
            }
    except Exception as e:
        logger.error("Fallback context from DB failed for %s: %s", project_id, e)
        return None


# ── Core execution ───────────────────────────────────────────────

def _parse_forge_edits(text: str) -> list[dict[str, str]]:
    """Extract completed forge-edit blocks from streamed text."""
    edits: list[dict[str, str]] = []
    for match in re.finditer(r"```forge-edit\s*\n([\s\S]*?)```", text):
        try:
            parsed = json.loads(match.group(1))
            if parsed.get("path") and parsed.get("content"):
                edits.append(parsed)
        except (json.JSONDecodeError, AttributeError):
            continue
    return edits


async def run_auto_build(project_id: str, sandbox_id: str | None = None) -> dict[str, Any]:
    """Execute the auto-build: load context, call AI, write files.

    This runs as a background job (via Inngest) immediately after pipeline completes.
    """
    await set_auto_build_status(project_id, "running")
    await _publish_progress(project_id, {"type": "autobuild_status", "status": "running", "message": "Loading pipeline context…"})

    # 1. Load pipeline context
    ctx = await _load_pipeline_context(project_id)
    if not ctx:
        await set_auto_build_status(project_id, "failed", detail={"error": "No pipeline context found"})
        return {"status": "failed", "error": "no_context"}

    # 2. Load current scaffold files
    current_files = await _load_current_files(project_id)
    await _publish_progress(project_id, {
        "type": "autobuild_status", "status": "running",
        "message": f"Context loaded: {len(current_files)} scaffold files",
    })

    # 3. Assemble mega-prompt
    user_prompt = _build_auto_build_prompt(ctx, current_files)
    logger.info("Auto-build prompt assembled: %d chars for project %s", len(user_prompt), project_id)

    # 4. Resolve sandbox_id if not provided
    if not sandbox_id:
        sandbox_id = ctx.get("sandbox_id")
    sandbox_uuid = uuid.UUID(sandbox_id) if sandbox_id else None

    # 5. Stream AI response
    files_written: list[str] = []
    accumulated = ""
    applied_count = 0

    async def _process_chunk(new_text: str) -> None:
        nonlocal accumulated, applied_count
        accumulated += new_text

        # Check for newly completed forge-edit blocks
        edits = _parse_forge_edits(accumulated)
        while applied_count < len(edits):
            edit = edits[applied_count]
            path = edit["path"]
            content = edit["content"]
            desc = edit.get("description", "")

            # Write to Supabase Storage
            try:
                ct = "application/json" if path.endswith(".json") else "text/plain"
                await storage_service.upload_file(
                    bucket=settings.SUPABASE_BUCKET_PROJECTS,
                    path=f"{project_id}/{path}",
                    content=content.encode() if isinstance(content, str) else content,
                    content_type=ct,
                )
            except Exception as e:
                logger.error("Auto-build: failed to upload %s: %s", path, e)

            # Sync to sandbox
            if sandbox_uuid:
                try:
                    await sync_file(sandbox_uuid, path, content)
                except Exception as e:
                    logger.warning("Auto-build: sandbox sync failed for %s: %s", path, e)

            files_written.append(path)
            applied_count += 1

            # Publish progress
            await _publish_progress(project_id, {
                "type": "autobuild_file",
                "path": path,
                "description": desc,
                "files_done": applied_count,
            })
            logger.info("Auto-build: wrote %s (%d total)", path, applied_count)

    # Try Anthropic first, fall back to OpenAI
    success = False

    if settings.ANTHROPIC_API_KEY:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        for model in ANTHROPIC_MODELS:
            try:
                async with client.messages.stream(
                    model=model,
                    max_tokens=ANTHROPIC_MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                ) as stream:
                    async for text in stream.text_stream:
                        await _process_chunk(text)
                success = True
                break
            except anthropic.APIStatusError as e:
                if e.status_code == 529:
                    logger.warning("Anthropic %s overloaded for auto-build, trying next", model)
                    continue
                logger.error("Anthropic error in auto-build: %s", e)
                break
            except Exception as e:
                logger.error("Anthropic error in auto-build: %s", e)
                break

    if not success and settings.OPENAI_API_KEY:
        logger.info("Auto-build falling back to OpenAI %s", OPENAI_MODEL)
        oai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        try:
            stream = await oai_client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=OPENAI_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    await _process_chunk(delta.content)
            success = True
        except Exception as e:
            logger.error("OpenAI error in auto-build: %s", e)

    if not success:
        await set_auto_build_status(project_id, "failed", detail={"error": "AI service unavailable"})
        return {"status": "failed", "error": "ai_unavailable"}

    # Store the full AI response as the auto-build conversation
    try:
        await storage_service.upload_file(
            bucket=settings.SUPABASE_BUCKET_PROJECTS,
            path=f"{project_id}/autobuild_response.md",
            content=accumulated.encode(),
            content_type="text/markdown",
        )
    except Exception as e:
        logger.warning("Failed to save auto-build response: %s", e)

    # Restart sandbox so it picks up all new files
    if sandbox_uuid:
        try:
            from app.services.file_sync_service import restart_sandbox
            await restart_sandbox(sandbox_uuid)
        except Exception as e:
            logger.warning("Auto-build: sandbox restart failed: %s", e)

    await set_auto_build_status(project_id, "completed", detail={
        "files_written": len(files_written),
        "file_list": files_written,
    })
    await _publish_progress(project_id, {
        "type": "autobuild_status", "status": "completed",
        "message": f"Auto-build complete: {len(files_written)} files generated",
        "files_written": len(files_written),
        "file_list": files_written,
    })

    logger.info("Auto-build completed for project %s: %d files", project_id, len(files_written))
    return {"status": "completed", "files_written": files_written}
