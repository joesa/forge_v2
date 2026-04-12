from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
import inngest
from sqlalchemy import func, select

from app.config import settings
from app.core.database import get_read_session, get_write_session
from app.inngest_client import forge_inngest
from app.models.build import Build, BuildStatus
from app.models.idea import Idea
from app.models.idea_session import IdeaSession
from app.models.pipeline_run import PipelineRun, PipelineStatus
from app.models.sandbox import Sandbox, SandboxStatus


# ─────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────

async def update_pipeline_status(pipeline_id: str, status: str) -> None:
    async with get_write_session() as db:
        result = await db.execute(
            select(PipelineRun).where(PipelineRun.id == uuid.UUID(pipeline_id))
        )
        run = result.scalar_one_or_none()
        if run:
            run.status = PipelineStatus(status)


async def run_pipeline_graph(data: dict[str, Any]) -> None:
    """Execute the LangGraph pipeline graph."""
    from app.pipeline.graph import execute_pipeline  # type: ignore[import-not-found]

    await execute_pipeline(
        pipeline_id=data["pipeline_id"],
        project_id=data["project_id"],
        user_id=data["user_id"],
        idea_spec=data["idea_spec"],
    )


async def update_build_status(build_id: str, status: str) -> None:
    async with get_write_session() as db:
        result = await db.execute(
            select(Build).where(Build.id == uuid.UUID(build_id))
        )
        build = result.scalar_one_or_none()
        if build:
            build.status = BuildStatus(status)


async def run_build_agents(data: dict[str, Any]) -> None:
    """Run Stage 6 build agents for a standalone rebuild."""
    from app.pipeline.graph import execute_build_stage  # type: ignore[import-not-found]

    await execute_build_stage(
        build_id=data["build_id"],
        project_id=data["project_id"],
    )


async def generate_five_ideas(answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate 5 unique app ideas from questionnaire answers using AI."""
    from app.pipeline.idea_generator import generate_ideas  # type: ignore[import-not-found]

    return await generate_ideas(answers, count=5)


async def store_ideas(
    session_id: str, user_id: str, ideas: list[dict[str, Any]]
) -> None:
    async with get_write_session() as db:
        for idea_data in ideas:
            idea = Idea(
                idea_session_id=uuid.UUID(session_id),
                user_id=uuid.UUID(user_id),
                title=idea_data.get("title", ""),
                description=idea_data.get("description", ""),
                tech_stack=idea_data.get("tech_stack", {}),
                market_analysis=idea_data.get("market_analysis"),
                status="generated",
            )
            db.add(idea)


async def mark_idea_session_complete(session_id: str) -> None:
    async with get_write_session() as db:
        result = await db.execute(
            select(IdeaSession).where(IdeaSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if session:
            session.completed = True
            session.status = "completed"


async def call_northflank_api(action: str, data: dict[str, Any]) -> dict[str, Any]:
    """Call Northflank REST API for sandbox VM lifecycle operations."""
    base_url = "https://api.northflank.com/v1"
    headers = {
        "Authorization": f"Bearer {settings.NORTHFLANK_API_KEY}",
        "Content-Type": "application/json",
    }
    project_id = settings.NORTHFLANK_PROJECT_ID

    async with httpx.AsyncClient(timeout=60) as client:
        if action == "provision":
            resp = await client.post(
                f"{base_url}/projects/{project_id}/services",
                headers=headers,
                json={
                    "name": f"sandbox-{data.get('sandbox_id', uuid.uuid4().hex[:8])}",
                    "type": "combined",
                    "billing": {"deploymentPlan": "nf-compute-20"},
                },
            )
            resp.raise_for_status()
            return resp.json()

        elif action == "start":
            resp = await client.post(
                f"{base_url}/projects/{project_id}/services/{data['northflank_service_id']}/resume",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

        elif action == "stop":
            resp = await client.post(
                f"{base_url}/projects/{project_id}/services/{data['northflank_service_id']}/pause",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

        elif action == "destroy":
            resp = await client.delete(
                f"{base_url}/projects/{project_id}/services/{data['northflank_service_id']}",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()

        else:
            raise ValueError(f"Unknown sandbox action: {action}")


def action_to_status(action: str) -> str:
    mapping = {
        "provision": "warm",
        "start": "claimed",
        "stop": "stopped",
        "destroy": "stopped",
    }
    return mapping.get(action, "error")


async def update_sandbox_status(sandbox_id: str | None, status: str) -> None:
    if not sandbox_id:
        return
    async with get_write_session() as db:
        result = await db.execute(
            select(Sandbox).where(Sandbox.id == uuid.UUID(sandbox_id))
        )
        sandbox = result.scalar_one_or_none()
        if sandbox:
            sandbox.status = SandboxStatus(status)


async def count_warm_sandboxes() -> int:
    async with get_read_session() as db:
        result = await db.execute(
            select(func.count()).select_from(Sandbox).where(
                Sandbox.status == SandboxStatus.warm
            )
        )
        return result.scalar_one()


async def provision_vms(n: int) -> None:
    """Provision n new Firecracker VMs via Northflank."""
    for _ in range(n):
        sandbox_id = str(uuid.uuid4())
        await call_northflank_api("provision", {"sandbox_id": sandbox_id})
        async with get_write_session() as db:
            sandbox = Sandbox(
                id=uuid.UUID(sandbox_id),
                status=SandboxStatus.warm,
            )
            db.add(sandbox)


# ─────────────────────────────────────────────────────────────────
# FUNCTION 1: pipeline-run
# ─────────────────────────────────────────────────────────────────


async def _pipeline_run_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    data = ctx.event.data

    await step.run("update-status-running", update_pipeline_status, data["pipeline_id"], "running")
    await step.run("execute-pipeline", run_pipeline_graph, data)
    await step.run("update-status-completed", update_pipeline_status, data["pipeline_id"], "completed")


pipeline_run_fn = forge_inngest.create_function(
    fn_id="pipeline-run",
    trigger=inngest.TriggerEvent(event="forge/pipeline.run"),
    retries=3,
)(_pipeline_run_handler)


# ─────────────────────────────────────────────────────────────────
# FUNCTION 1b: pipeline-failure-handler
# ─────────────────────────────────────────────────────────────────

async def _pipeline_failure_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    """Mark pipeline as failed when pipeline-run exhausts all retries."""
    failed_fn_id = ctx.event.data.get("function_id", "")
    if failed_fn_id != "pipeline-run":
        return
    event_data = ctx.event.data.get("event", {}).get("data", {})
    pipeline_id = event_data.get("pipeline_id")
    if pipeline_id:
        await step.run("mark-failed", update_pipeline_status, pipeline_id, "failed")


pipeline_failure_handler_fn = forge_inngest.create_function(
    fn_id="pipeline-failure-handler",
    trigger=inngest.TriggerEvent(event="inngest/function.failed"),
)(_pipeline_failure_handler)


# ─────────────────────────────────────────────────────────────────
# FUNCTION 2: build-run
# ─────────────────────────────────────────────────────────────────

async def _build_run_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    data = ctx.event.data
    await step.run("update-status-building", update_build_status, data["build_id"], "building")
    await step.run("run-build-agents", run_build_agents, data)
    await step.run("update-status-complete", update_build_status, data["build_id"], "success")


build_run_fn = forge_inngest.create_function(
    fn_id="build-run",
    trigger=inngest.TriggerEvent(event="forge/build.run"),
    retries=2,
)(_build_run_handler)


# ─────────────────────────────────────────────────────────────────
# FUNCTION 3: idea-generation
# ─────────────────────────────────────────────────────────────────

async def _idea_generation_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    data = ctx.event.data
    ideas = await step.run("generate-ideas", generate_five_ideas, data["answers"])
    await step.run("store-ideas", store_ideas, data["session_id"], data["user_id"], ideas)
    await step.run("mark-complete", mark_idea_session_complete, data["session_id"])


idea_generation_fn = forge_inngest.create_function(
    fn_id="idea-generation",
    trigger=inngest.TriggerEvent(event="forge/idea.generate"),
    retries=2,
)(_idea_generation_handler)


# ─────────────────────────────────────────────────────────────────
# FUNCTION 4: sandbox-lifecycle
# ─────────────────────────────────────────────────────────────────

async def _sandbox_lifecycle_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    data = ctx.event.data
    action = data["action"]

    await step.run(f"northflank-{action}", call_northflank_api, action, data)
    await step.run(
        "update-sandbox-status",
        update_sandbox_status,
        data.get("sandbox_id"),
        action_to_status(action),
    )


sandbox_lifecycle_fn = forge_inngest.create_function(
    fn_id="sandbox-lifecycle",
    trigger=inngest.TriggerEvent(event="forge/sandbox.lifecycle"),
    retries=3,
)(_sandbox_lifecycle_handler)


# ─────────────────────────────────────────────────────────────────
# FUNCTION 5: pool-replenish (CRON — every 5 minutes)
# ─────────────────────────────────────────────────────────────────

async def _pool_replenish_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    warm_count = await step.run("count-warm-sandboxes", count_warm_sandboxes)
    target = int(os.getenv("POOL_TARGET", "20"))

    if warm_count < target:
        needed = target - warm_count
        await step.run("provision-vms", provision_vms, needed)


pool_replenish_fn = forge_inngest.create_function(
    fn_id="pool-replenish",
    trigger=inngest.TriggerCron(cron="*/5 * * * *"),
)(_pool_replenish_handler)
