from __future__ import annotations

import asyncio
import json
import time
import uuid

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

_CSUITE_AGENTS: list[BaseCSuiteAgent] = [
    CEOAgent(), CTOAgent(), CDOAgent(), CMOAgent(),
    CPOAgent(), CSOAgent(), CCOAgent(), CFOAgent(),
]


async def _publish(state: PipelineState, stage: int, status: str, message: str) -> None:
    if redis_client is None:
        return
    await redis_client.publish(
        f"pipeline:{state['pipeline_id']}",
        json.dumps({
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp_ms": int(time.time() * 1000),
        }),
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

    # 8 agents in parallel
    async def _run_agent(agent: BaseCSuiteAgent) -> tuple[str, dict]:
        output = await agent.execute(idea_spec)
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

    # 9 build agents (placeholders — agents 1-9)
    for i in range(1, 10):
        agent_name = f"build_agent_{i}"
        state["generated_files"][f"file_{i}.ts"] = f"// generated by {agent_name}"

        g7 = validate_g7(state)
        state.setdefault("gate_results", {})[f"g7_{agent_name}"] = g7

    # Build agent 10: ReviewAgent — runs Layer 4 coherence checks
    await _publish(state, 6, "running", "ReviewAgent: coherence checks")

    build_id = uuid.UUID(state.get("pipeline_id", str(uuid.uuid4())))
    generated_files = state.get("generated_files", {})

    # Layer 4a: File coherence engine (import/export validation)
    coherence_report = await run_coherence_check(build_id, generated_files)
    state.setdefault("gate_results", {})["coherence"] = coherence_report

    # Layer 4b: Barrel validation
    barrel_result = validate_barrels(generated_files)
    state.setdefault("gate_results", {})["barrels"] = barrel_result

    # Layer 4c: Seam check (frontend↔backend routes)
    seam_result = check_seams(generated_files)
    state.setdefault("gate_results", {})["seams"] = seam_result

    g7_review = validate_g7(state)
    state.setdefault("gate_results", {})["g7_build_agent_10"] = g7_review

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
