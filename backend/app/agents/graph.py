from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from sqlalchemy import update as _sql_update

from langgraph.graph import END, StateGraph

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.ceo_agent import CEOAgent
from app.agents.csuite.cto_agent import CTOAgent
from app.agents.csuite.cdo_agent import CDOAgent
from app.agents.csuite.cmo_agent import CMOAgent
from app.agents.csuite.cpo_agent import CPOAgent
from app.agents.csuite.cso_agent import CSOAgent
from app.agents.csuite.cco_agent import CCOAgent
from app.agents.csuite.cfo_agent import CFOAgent
from app.agents.csuite.schemas import CSUITE_SCHEMAS
from app.agents.state import PipelineState
from app.agents.synthesis.g3_resolver import resolve_conflicts
from app.agents.synthesis.plan_flattener import flatten_plan
from app.agents.synthesis.synthesizer import synthesize
from app.agents.validators import (
    validate_g1,
    validate_g2,
    validate_g3,
    validate_g4,
    validate_g6,
    validate_g7,
)
from app.core.redis import redis_client
from app.reliability.layer1_pregeneration.env_contract_validator import validate_env_contract
from app.reliability.layer2_schema_driven.openapi_injector import generate_openapi_spec
from app.reliability.layer2_schema_driven.pydantic_schema_injector import (
    extract_model_defs,
    generate_pydantic_models,
)
from app.reliability.layer2_schema_driven.zod_schema_injector import generate_zod_schemas
from app.reliability.layer2_schema_driven.db_type_injector import generate_ts_interfaces
from app.reliability.layer4_coherence.file_coherence_engine import run_coherence_check
from app.reliability.layer4_coherence.barrel_validator import validate_barrels
from app.reliability.layer4_coherence.seam_checker import check_seams
from app.reliability.layer7_simulation.wiremock_manager import (
    WireMockManager,
    detect_required_services,
)
from app.agents.build import BUILD_AGENTS, REVIEW_AGENT
from app.agents.build.hotfix_agent import apply_hotfix
from app.services.snapshot_service import capture_snapshot
from app.services.storage_service import upload_file
from app.core.database import get_write_session
from app.models.build import Build, BuildStatus
from app.config import settings

logger = logging.getLogger(__name__)


# ── Summary extraction for C-Suite cards ────────────────────────

_SUMMARY_KEYS: dict[str, list[str]] = {
    "ceo": ["business_model", "revenue_strategy", "competitive_moat"],
    "cto": ["scalability_approach", "api_design"],
    "cdo": ["design_system_recommendation"],
    "cmo": ["positioning_statement", "gtm_strategy"],
    "cpo": ["mvp_scope"],
    "cso": ["auth_architecture"],
    "cco": [],
    "cfo": ["pricing_strategy", "breakeven_analysis"],
}


def _extract_summary(agent_name: str, output: dict) -> str:
    """Build a concise summary for the pipeline card display."""
    if not isinstance(output, dict):
        return ""

    parts: list[str] = []
    # Try agent-specific keys first
    for key in _SUMMARY_KEYS.get(agent_name, []):
        val = output.get(key, "")
        if isinstance(val, str) and len(val) > 5:
            parts.append(val)
            break
        if isinstance(val, dict):
            # e.g. tech_stack_recommendation
            snippet = ", ".join(f"{k}: {v}" for k, v in val.items() if isinstance(v, str) and v)[:150]
            if snippet:
                parts.append(snippet)
                break

    # Fallback: gather key list/dict stats
    if not parts:
        for k, v in output.items():
            if isinstance(v, str) and len(v) > 5:
                parts.append(v)
                break
            if isinstance(v, list) and v:
                items = [str(x) for x in v[:3]]
                parts.append(f"{k}: {', '.join(items)}")
                break

    summary = parts[0] if parts else ""
    return summary[:200]

_CSUITE_AGENTS: list[BaseCSuiteAgent] = [
    CEOAgent(), CTOAgent(), CDOAgent(), CMOAgent(),
    CPOAgent(), CSOAgent(), CCOAgent(), CFOAgent(),
]


async def _publish(state: PipelineState, stage: int, status: str, message: str) -> None:
    if redis_client is None:
        return
    # Map "completed" → "done" for frontend StageStatus compatibility
    ws_status = "done" if status == "completed" else status
    await redis_client.publish(
        f"pipeline:{state['pipeline_id']}",
        json.dumps({
            "type": "stage_update",
            "stage": stage,
            "status": ws_status,
            "message": message,
            "timestamp_ms": int(time.time() * 1000),
        }),
    )


async def _publish_agent(state: PipelineState, agent: str, status: str, output: str = "", *, detail: dict | None = None) -> None:
    """Publish a per-agent update (used for C-Suite cards)."""
    if redis_client is None:
        return
    ws_status = "done" if status == "completed" else status
    msg: dict = {
        "type": "agent_update",
        "agent": agent,
        "status": ws_status,
        "output": output,
        "timestamp_ms": int(time.time() * 1000),
    }
    if detail is not None:
        msg["detail"] = detail
    await redis_client.publish(
        f"pipeline:{state['pipeline_id']}",
        json.dumps(msg),
    )


# ── Stage 1: Input Layer ────────────────────────────────────────
async def input_layer(state: PipelineState) -> PipelineState:
    await _publish(state, 1, "running", "Validating input")
    state["current_stage"] = 1

    g1 = validate_g1(state)
    state.setdefault("gate_results", {})["g1"] = g1
    if not g1["passed"]:
        state.setdefault("errors", []).append(g1["reason"])
        await _publish(state, 1, "failed", g1["reason"])
        return state

    # Layer 1: Env contract validation
    idea_spec = state.get("idea_spec", {})
    framework = idea_spec.get("framework", "vite_react")
    env_vars = idea_spec.get("env_vars", {})
    env_result = validate_env_contract(framework, env_vars)
    state.setdefault("gate_results", {})["env_contract"] = env_result
    if not env_result["passed"]:
        # Inject missing vars with empty placeholders so build can proceed
        for var in env_result["missing"]:
            env_vars[var] = ""
        idea_spec["env_vars"] = env_vars

    await _publish(state, 1, "completed", "Input validated")
    return state


# ── Stage 2: C-Suite Analysis ───────────────────────────────────
async def csuite_analysis(state: PipelineState) -> PipelineState:
    await _publish(state, 2, "running", "Running C-suite agents")
    state["current_stage"] = 2

    idea_spec = state.get("idea_spec", {})

    # 8 agents in parallel — publish per-agent updates as each completes
    async def _run_agent(agent: BaseCSuiteAgent) -> tuple[str, dict]:
        await _publish_agent(state, agent.name, "running")
        output = await agent.execute(idea_spec)
        # Extract a short summary for the card display
        summary = _extract_summary(agent.name, output)
        await _publish_agent(state, agent.name, "completed", summary, detail=output)
        return agent.name, output

    results = await asyncio.gather(*[_run_agent(a) for a in _CSUITE_AGENTS])
    csuite_outputs = dict(results)

    # G2: validate each agent output against its Pydantic schema
    g2_all_passed = True
    for name, output in csuite_outputs.items():
        schema = CSUITE_SCHEMAS.get(name)
        if schema:
            try:
                schema.model_validate(output)
            except Exception:
                g2_all_passed = False

    g2 = {"passed": g2_all_passed, "reason": "all outputs valid" if g2_all_passed else "schema validation failed"}
    state.setdefault("gate_results", {})["g2"] = g2

    # G3: resolve conflicts (always passes)
    resolved_outputs, resolutions = resolve_conflicts(csuite_outputs)
    state["csuite_outputs"] = resolved_outputs

    g3 = validate_g3(state)
    state.setdefault("gate_results", {})["g3"] = g3

    await _publish(state, 2, "completed", "C-suite analysis done")
    return state


# ── Stage 3: Synthesis ──────────────────────────────────────────
async def synthesis(state: PipelineState) -> PipelineState:
    await _publish(state, 3, "running", "Synthesizing plan")
    state["current_stage"] = 3

    csuite_outputs = state.get("csuite_outputs", {})
    resolutions = state.get("gate_results", {}).get("g3", {}).get("resolutions", [])

    # Synthesize into ComprehensivePlan
    plan = await synthesize(csuite_outputs, resolutions)
    state["comprehensive_plan"] = plan

    # G4 — retry once on fail
    g4 = validate_g4(state)
    if not g4["passed"]:
        plan = await synthesize(csuite_outputs, resolutions)
        state["comprehensive_plan"] = plan
        g4 = validate_g4(state)

    state.setdefault("gate_results", {})["g4"] = g4
    if not g4["passed"]:
        state.setdefault("errors", []).append(g4["reason"])
        await _publish(state, 3, "failed", g4["reason"])
        return state

    # Flatten plan into build-ready keys (pages, entities, features, components)
    await _publish(state, 3, "running", "Extracting build specification")
    idea_spec = state.get("idea_spec", {})
    state["comprehensive_plan"] = await flatten_plan(plan, idea_spec)

    await _publish(state, 3, "completed", "Synthesis done")
    return state


# ── Stage 4: Spec Layer ─────────────────────────────────────────
async def spec_layer(state: PipelineState) -> PipelineState:
    await _publish(state, 4, "running", "Generating specs")
    state["current_stage"] = 4

    # 5 spec agents parallel (placeholders)
    async def _spec_agent(name: str) -> tuple[str, dict]:
        return name, {"status": "ok"}

    specs = ["api", "db", "ui", "infra", "security"]
    results = await asyncio.gather(*[_spec_agent(s) for s in specs])
    state["spec_outputs"] = dict(results)

    # Layer 2: Extract model defs first — used by OpenAPI and schema injectors
    model_defs = extract_model_defs(state.get("spec_outputs", {}))

    # Layer 2: Generate OpenAPI spec from comprehensive_plan + model schemas
    plan = state.get("comprehensive_plan", {})
    openapi_spec = generate_openapi_spec(plan, model_defs=model_defs)
    state.setdefault("spec_outputs", {})["openapi_spec"] = openapi_spec

    # Layer 2: Generate typed schemas for build agents
    pydantic_code = generate_pydantic_models(state.get("spec_outputs", {}))
    zod_code = generate_zod_schemas(model_defs)
    ts_interfaces = generate_ts_interfaces(model_defs)

    # Store in state for build agents to consume
    state.setdefault("spec_outputs", {})["pydantic_code"] = pydantic_code
    state.setdefault("spec_outputs", {})["zod_schemas"] = zod_code
    state.setdefault("spec_outputs", {})["ts_interfaces"] = ts_interfaces
    state.setdefault("spec_outputs", {})["model_defs"] = model_defs

    await _publish(state, 4, "completed", "Specs generated")
    return state


# ── Stage 5: Bootstrap ──────────────────────────────────────────
async def bootstrap(state: PipelineState) -> PipelineState:
    await _publish(state, 5, "running", "Building manifest")
    state["current_stage"] = 5

    # BuildManifest (placeholder)
    state["build_manifest"] = {"files": [], "dependencies": []}

    g6 = validate_g6(state)
    state.setdefault("gate_results", {})["g6"] = g6

    # Cache check (placeholder)

    await _publish(state, 5, "completed", "Manifest ready")
    return state


# ── Stage 6: Build ──────────────────────────────────────────────
async def build(state: PipelineState) -> PipelineState:
    await _publish(state, 6, "running", "Building application")
    state["current_stage"] = 6

    state["generated_files"] = {}

    pipeline_id = state.get("pipeline_id", str(uuid.uuid4()))
    project_id = state.get("project_id", str(uuid.uuid4()))
    user_id = state.get("user_id")
    pipeline_uuid = uuid.UUID(pipeline_id) if pipeline_id else uuid.uuid4()
    project_uuid = uuid.UUID(project_id) if project_id else uuid.uuid4()

    # Create a Build record so snapshots have a valid FK
    build_uuid = uuid.uuid4()
    state["build_id"] = str(build_uuid)
    async with get_write_session() as db:
        build_row = Build(
            id=build_uuid,
            project_id=project_uuid,
            user_id=uuid.UUID(user_id) if user_id else project_uuid,
            status=BuildStatus.building,
        )
        db.add(build_row)

    # ── Layer 7: WireMock external service simulation ────────────
    wiremock = WireMockManager()
    import os
    _original_base_url = os.environ.get("EXTERNAL_API_BASE_URL")
    try:
        await wiremock.start()
        required_services = detect_required_services(state)
        await wiremock.configure_stubs(required_services)
        os.environ["EXTERNAL_API_BASE_URL"] = wiremock.base_url

        # ── Agents 1-9: sequential build ─────────────────────────
        for agent in BUILD_AGENTS:
            await _publish(state, 6, "running", f"Agent {agent.agent_number}: {agent.name}")

            new_files = await agent.execute(state)
            state["generated_files"].update(new_files)

            # Snapshot after every agent
            await capture_snapshot(
                build_id=build_uuid,
                project_id=project_uuid,
                agent_number=agent.agent_number,
                agent_type=agent.name,
                generated_files=state["generated_files"],
            )

            # G7 gate after every agent
            g7 = validate_g7(state)
            state.setdefault("gate_results", {})[f"g7_agent_{agent.agent_number}"] = g7

            if not g7["passed"]:
                await _publish(state, 6, "running", f"G7 failed for agent {agent.agent_number}, attempting hotfix")
                hotfix_result = await apply_hotfix(state, agent.agent_number, g7)
                if not hotfix_result.applied:
                    state.setdefault("errors", []).append(
                        f"Agent {agent.agent_number} ({agent.name}) G7 failed: {g7['reason']}"
                    )
                    await _publish(state, 6, "failed", f"Agent {agent.agent_number} build failed")
                    # Mark build as failed
                    async with get_write_session() as db:
                        await db.execute(
                            _sql_update(Build).where(Build.id == build_uuid).values(
                                status=BuildStatus.failed,
                                gate_results=state.get("gate_results"),
                            )
                        )
                    return state

        # ── Agent 10: ReviewAgent — validates only ───────────────
        await _publish(state, 6, "running", "Agent 10: review (validation only)")

        review_report = await REVIEW_AGENT.review(state)
        state.setdefault("gate_results", {})["review"] = review_report

        # Snapshot after review
        await capture_snapshot(
            build_id=build_uuid,
            project_id=project_uuid,
            agent_number=10,
            agent_type="review",
            generated_files=state["generated_files"],
        )

        # Verify all external calls were stubbed
        wiremock_report = await wiremock.verify_all_calls()
        state.setdefault("gate_results", {})["wiremock"] = wiremock_report

    finally:
        # MUST always stop — even on pipeline failure
        await wiremock.stop()
        if _original_base_url is not None:
            os.environ["EXTERNAL_API_BASE_URL"] = _original_base_url
        else:
            os.environ.pop("EXTERNAL_API_BASE_URL", None)

    # ── Store generated files to Supabase Storage ────────────────
    storage_key = f"{project_id}/{build_uuid}/build.json"
    payload = json.dumps(state["generated_files"], sort_keys=True).encode()
    logger.info("Uploading build.json (%d bytes, %d files) to %s",
                len(payload), len(state["generated_files"]), storage_key)
    try:
        await upload_file(
            bucket=settings.SUPABASE_BUCKET_PROJECTS,
            path=storage_key,
            content=payload,
            content_type="application/json",
        )
    except Exception as e:
        logger.exception("Failed to upload build.json: %s", e)
        raise

    # Upload each generated file individually so the editor can access them
    await _publish(state, 6, "running", "Uploading files to storage")
    for filepath, content in state["generated_files"].items():
        ct = "application/json" if filepath.endswith(".json") else "text/plain"
        try:
            await upload_file(
                bucket=settings.SUPABASE_BUCKET_PROJECTS,
                path=f"{project_id}/{filepath}",
                content=content.encode() if isinstance(content, str) else content,
                content_type=ct,
            )
        except Exception as e:
            logger.error("Failed to upload file %s: %s", filepath, e)
            state.setdefault("errors", []).append(f"Upload failed for {filepath}: {e}")

    # Mark build as success
    async with get_write_session() as db:
        await db.execute(
            _sql_update(Build).where(Build.id == build_uuid).values(
                status=BuildStatus.success,
                generated_files_key=storage_key,
                gate_results=state.get("gate_results"),
            )
        )

    # Provision a sandbox so the preview is ready when the user opens the editor
    try:
        from app.services.sandbox_service import claim_or_provision_sandbox, wait_for_sandbox_ready
        sandbox_id = await claim_or_provision_sandbox(project_uuid)
        state["sandbox_id"] = sandbox_id
        logger.info("Sandbox provisioning started: %s for project %s", sandbox_id, project_id)

        await _publish(state, 6, "in_progress", "Provisioning sandbox container…")
        ready = await wait_for_sandbox_ready(sandbox_id, timeout=120)
        if ready:
            logger.info("Sandbox ready: %s", sandbox_id)
        else:
            logger.warning("Sandbox not ready after timeout: %s", sandbox_id)
    except Exception as e:
        logger.error("Sandbox provisioning failed (non-fatal): %s", e)

    await _publish(state, 6, "completed", "Build complete")
    return state


# ── Error Handler ────────────────────────────────────────────────
async def error_handler(state: PipelineState) -> PipelineState:
    errors = state.get("errors") or []
    stage = state.get("current_stage", 0)
    await _publish(state, stage, "failed", f"Pipeline failed: {'; '.join(errors)}")
    return state


def _should_continue(state: PipelineState) -> str:
    if state.get("errors"):
        return "error_handler"
    return "continue"


# ── Graph Builder ────────────────────────────────────────────────
async def build_pipeline_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("input_layer", input_layer)
    graph.add_node("csuite_analysis", csuite_analysis)
    graph.add_node("synthesis", synthesis)
    graph.add_node("spec_layer", spec_layer)
    graph.add_node("bootstrap", bootstrap)
    graph.add_node("build", build)
    graph.add_node("error_handler", error_handler)

    graph.set_entry_point("input_layer")

    graph.add_conditional_edges("input_layer", _should_continue, {
        "continue": "csuite_analysis",
        "error_handler": "error_handler",
    })
    graph.add_conditional_edges("csuite_analysis", _should_continue, {
        "continue": "synthesis",
        "error_handler": "error_handler",
    })
    graph.add_conditional_edges("synthesis", _should_continue, {
        "continue": "spec_layer",
        "error_handler": "error_handler",
    })
    graph.add_edge("spec_layer", "bootstrap")
    graph.add_edge("bootstrap", "build")
    graph.add_edge("build", END)
    graph.add_edge("error_handler", END)

    return graph


# Alias — both names work
build_graph = build_pipeline_graph
