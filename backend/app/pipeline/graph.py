"""Pipeline execution bridge — connects Inngest functions to the LangGraph pipeline."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.agents.graph import build_pipeline_graph
from app.agents.state import PipelineState
from app.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


async def _publish_event(pipeline_id: str, event_type: str, stage: int, status: str, message: str) -> None:
    if redis_client is None:
        return
    await redis_client.publish(
        f"pipeline:{pipeline_id}",
        json.dumps({
            "type": event_type,
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp_ms": int(time.time() * 1000),
        }),
    )


async def execute_pipeline(
    *,
    pipeline_id: str,
    project_id: str,
    user_id: str,
    idea_spec: dict[str, Any],
) -> dict[str, Any]:
    """Run the full 6-stage pipeline graph and return final state."""
    graph = await build_pipeline_graph()
    compiled = graph.compile()

    initial_state: PipelineState = {
        "pipeline_id": pipeline_id,
        "project_id": project_id,
        "user_id": user_id,
        "idea_spec": idea_spec,
    }

    await _publish_event(pipeline_id, "stage_update", 0, "running", "Pipeline starting")

    # LangGraph invoke — runs all stages via conditional edges
    final_state = await compiled.ainvoke(initial_state)

    # Publish terminal pipeline-level status (type=pipeline_complete triggers WS close)
    if final_state.get("errors"):
        await _publish_event(pipeline_id, "pipeline_complete", final_state.get("current_stage", 6), "failed", "Pipeline failed")
    else:
        await _publish_event(pipeline_id, "pipeline_complete", 6, "completed", "Pipeline complete")

    # Always persist pipeline context so auto-build can use whatever data is available
    await _save_pipeline_context(final_state)

    return dict(final_state)


async def _save_pipeline_context(state: dict[str, Any]) -> None:
    """Save pipeline context (C-Suite, synthesis, spec, bootstrap) to Supabase Storage."""
    from app.services.storage_service import upload_file

    project_id = state.get("project_id", "")
    if not project_id:
        return

    context = {
        "idea_spec": state.get("idea_spec", {}),
        "design_architecture": state.get("design_architecture", {}),
        "csuite_outputs": state.get("csuite_outputs", {}),
        "comprehensive_plan": state.get("comprehensive_plan", {}),
        "spec_outputs": state.get("spec_outputs", {}),
        "build_manifest": state.get("build_manifest", {}),
        "gate_results": state.get("gate_results", {}),
        "generated_files": list(state.get("generated_files", {}).keys()),
        "pipeline_id": state.get("pipeline_id", ""),
        "build_id": state.get("build_id", ""),
        "sandbox_id": state.get("sandbox_id", ""),
    }

    populated = [k for k, v in context.items() if v and k not in ("pipeline_id", "build_id", "sandbox_id")]
    logger.info("Pipeline context for %s — populated keys: %s", project_id, populated)

    try:
        await upload_file(
            bucket=settings.SUPABASE_BUCKET_PROJECTS,
            path=f"{project_id}/pipeline_context.json",
            content=json.dumps(context, default=str).encode(),
            content_type="application/json",
        )
        logger.info("Saved pipeline context for project %s", project_id)
    except Exception as e:
        logger.error("Failed to save pipeline context: %s", e)


async def execute_build_stage(
    *,
    build_id: str,
    project_id: str,
) -> dict[str, Any]:
    """Run only the build stage (Stage 6) for a standalone rebuild."""
    from app.agents.graph import build as build_node

    state: PipelineState = {
        "pipeline_id": build_id,
        "project_id": project_id,
        "current_stage": 6,
        "generated_files": {},
    }

    result = await build_node(state)
    return dict(result)
