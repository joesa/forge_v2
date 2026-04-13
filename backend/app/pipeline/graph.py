"""Pipeline execution bridge — connects Inngest functions to the LangGraph pipeline."""
from __future__ import annotations

import json
import time
from typing import Any

from app.agents.graph import build_pipeline_graph
from app.agents.state import PipelineState
from app.core.redis import redis_client


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

    return dict(final_state)


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
