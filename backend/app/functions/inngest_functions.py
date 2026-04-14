from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

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
    from app.pipeline.graph import execute_pipeline

    try:
        await execute_pipeline(
            pipeline_id=data["pipeline_id"],
            project_id=data["project_id"],
            user_id=data["user_id"],
            idea_spec=data["idea_spec"],
        )
    except Exception:
        logger.exception("Pipeline execution failed for %s", data.get("pipeline_id"))
        raise


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
    from app.pipeline.graph import execute_build_stage

    await execute_build_stage(
        build_id=data["build_id"],
        project_id=data["project_id"],
    )


async def generate_five_ideas(answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate 5 unique app ideas from questionnaire answers using AI."""
    from app.pipeline.idea_generator import generate_ideas

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
    """Call Northflank REST API for sandbox VM lifecycle operations.

    Each sandbox is a deployment service pulling the image built by the
    'sandbox-image' build service in the same project.
    """
    base_url = "https://api.northflank.com/v1"
    headers = {
        "Authorization": f"Bearer {settings.NORTHFLANK_API_KEY}",
        "Content-Type": "application/json",
    }
    project_id = settings.NORTHFLANK_PROJECT_ID

    async with httpx.AsyncClient(timeout=60) as client:
        if action == "provision":
            sandbox_id = data.get("sandbox_id", uuid.uuid4().hex[:8])
            svc_name = f"sandbox-{sandbox_id[:12]}"

            resp = await client.post(
                f"{base_url}/projects/{project_id}/services/deployment",
                headers=headers,
                json={
                    "name": svc_name,
                    "description": f"Forge sandbox {sandbox_id}",
                    "billing": {"deploymentPlan": settings.NORTHFLANK_SANDBOX_PLAN},
                    "deployment": {
                        "instances": 1,
                        "docker": {"configType": "default"},
                        "internal": {
                            "id": settings.NORTHFLANK_BUILD_SERVICE_ID,
                            "branch": "master",
                            "buildSHA": "latest",
                        },
                        "storage": {
                            "ephemeralStorage": {"storageSize": 2048},
                        },
                    },
                    "ports": [
                        {"name": "app", "internalPort": 3000, "public": True, "protocol": "HTTP"},
                        {"name": "agent", "internalPort": 9999, "public": True, "protocol": "HTTP"},
                        {"name": "hmr", "internalPort": 24678, "public": True, "protocol": "HTTP"},
                    ],
                    "runtimeEnvironment": {
                        "SANDBOX_ID": sandbox_id,
                        "PROJECT_ID": data.get("project_id") or "",
                        "REDIS_URL": settings.REDIS_URL,
                        "FORGE_API_URL": _get_forge_api_url(),
                        "FORGE_SERVICE_TOKEN": settings.FORGE_SERVICE_TOKEN,
                    },
                    "healthChecks": [
                        {
                            "protocol": "HTTP",
                            "type": "readinessProbe",
                            "port": 9999,
                            "path": "/health",
                            "initialDelaySeconds": 10,
                            "periodSeconds": 10,
                            "timeoutSeconds": 5,
                            "failureThreshold": 3,
                            "successThreshold": 1,
                        },
                    ],
                },
            )

            # Handle duplicate: if service already exists, fetch it
            if resp.status_code == 409:
                resp = await client.get(
                    f"{base_url}/projects/{project_id}/services/{svc_name}",
                    headers=headers,
                )
                resp.raise_for_status()
            else:
                resp.raise_for_status()

            result = resp.json()

            service_data = result.get("data", result)
            nf_service_id = service_data.get("id", "")

            # Extract public URL from ports DNS
            ports = service_data.get("ports", [])
            app_url = ""
            for port in ports:
                if port.get("name") == "app" and port.get("dns"):
                    app_url = f"https://{port['dns']}"
                    break

            # Fallback: construct from Northflank DNS convention
            if not app_url and nf_service_id:
                app_url = f"https://app--{nf_service_id}--{project_id}.code.run"

            return {
                "northflank_service_id": nf_service_id,
                "sandbox_url": app_url,
                "sandbox_id": sandbox_id,
            }

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


def _get_forge_api_url() -> str:
    """Return the public backend URL for sandbox→backend communication."""
    if settings.FORGE_API_PUBLIC_URL:
        return settings.FORGE_API_PUBLIC_URL
    if settings.FORGE_ENV == "development":
        return "http://host.docker.internal:8000"
    return f"https://api.{settings.PREVIEW_DOMAIN.replace('preview.', '')}"


async def register_sandbox_url_in_kv(sandbox_id: str, sandbox_url: str) -> None:
    """Write sandbox URL to Cloudflare KV so the preview proxy can route to it."""
    if not settings.CLOUDFLARE_API_TOKEN or not settings.CLOUDFLARE_KV_NAMESPACE_ID:
        logger.warning("Cloudflare KV not configured — skipping URL registration for %s", sandbox_id)
        return

    kv_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}"
        f"/storage/kv/namespaces/{settings.CLOUDFLARE_KV_NAMESPACE_ID}"
        f"/values/sandbox:{sandbox_id}:url"
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(
            kv_url,
            headers={
                "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
                "Content-Type": "text/plain",
            },
            content=sandbox_url,
        )
        if resp.is_success:
            logger.info("Registered sandbox %s → %s in CF KV", sandbox_id, sandbox_url)
        else:
            logger.error("Failed to register in CF KV: %s %s", resp.status_code, resp.text)


async def deregister_sandbox_url_from_kv(sandbox_id: str) -> None:
    """Remove sandbox URL from Cloudflare KV."""
    if not settings.CLOUDFLARE_API_TOKEN or not settings.CLOUDFLARE_KV_NAMESPACE_ID:
        return

    kv_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}"
        f"/storage/kv/namespaces/{settings.CLOUDFLARE_KV_NAMESPACE_ID}"
        f"/values/sandbox:{sandbox_id}:url"
    )

    async with httpx.AsyncClient(timeout=15) as client:
        await client.delete(
            kv_url,
            headers={"Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}"},
        )


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

    # Trigger auto-build: AI Editor builds the full app from pipeline context
    await step.run(
        "trigger-auto-build",
        _trigger_auto_build,
        data["project_id"],
    )


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
# FUNCTION 1c: editor-auto-build
# ─────────────────────────────────────────────────────────────────

async def _trigger_auto_build(project_id: str) -> None:
    """Send the auto-build Inngest event. Called as an Inngest step."""
    await forge_inngest.send(inngest.Event(
        name="forge/editor-build.run",
        data={"project_id": project_id},
    ))


async def _run_auto_build(data: dict[str, Any]) -> dict[str, Any]:
    """Run the auto-build service."""
    from app.services.auto_build_service import run_auto_build
    return await run_auto_build(
        project_id=data["project_id"],
        sandbox_id=data.get("sandbox_id"),
    )


async def _editor_auto_build_handler(
    ctx: inngest.Context, step: inngest.Step
) -> None:
    """Build the full app via AI Editor immediately after pipeline completes."""
    data = ctx.event.data
    await step.run("run-auto-build", _run_auto_build, data)


editor_auto_build_fn = forge_inngest.create_function(
    fn_id="editor-auto-build",
    trigger=inngest.TriggerEvent(event="forge/editor-build.run"),
    retries=2,
)(_editor_auto_build_handler)


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
    sandbox_id = data.get("sandbox_id")

    result = await step.run(f"northflank-{action}", call_northflank_api, action, data)

    if action == "provision" and result:
        # Save Northflank service ID on the sandbox row
        nf_service_id = result.get("northflank_service_id", "")
        sandbox_url = result.get("sandbox_url", "")

        async def _save_nf_service_id() -> None:
            if not sandbox_id or not nf_service_id:
                return
            async with get_write_session() as db:
                row = await db.execute(
                    select(Sandbox).where(Sandbox.id == uuid.UUID(sandbox_id))
                )
                sandbox = row.scalar_one_or_none()
                if sandbox:
                    sandbox.northflank_service_id = nf_service_id
                    if sandbox_url:
                        sandbox.sandbox_url = sandbox_url

        await step.run("save-service-id", _save_nf_service_id)

        # Register the sandbox URL in Cloudflare KV for the preview proxy
        if sandbox_url and sandbox_id:
            await step.run(
                "register-kv",
                register_sandbox_url_in_kv,
                sandbox_id,
                sandbox_url,
            )

    if action == "destroy" and sandbox_id:
        await step.run("deregister-kv", deregister_sandbox_url_from_kv, sandbox_id)

    # Fresh-provisioned sandboxes with a project_id should transition
    # directly to "claimed" (not "warm") so file sync can find them.
    final_status = action_to_status(action)
    if action == "provision" and data.get("project_id"):
        final_status = "claimed"

    await step.run(
        "update-sandbox-status",
        update_sandbox_status,
        sandbox_id,
        final_status,
    )


sandbox_lifecycle_fn = forge_inngest.create_function(
    fn_id="sandbox-lifecycle",
    trigger=inngest.TriggerEvent(event="forge/sandbox.lifecycle"),
    retries=3,
    concurrency=[
        inngest.Concurrency(
            limit=1,
            key="event.data.sandbox_id",
        ),
    ],
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
