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
from app.models.pipeline_run import PipelineRun
from app.config import settings

logger = logging.getLogger(__name__)


# ── Stage persistence ───────────────────────────────────────────

async def _persist_stage(state: PipelineState, stage: int, status: str) -> None:
    """Persist stage completion status to PipelineRun so frontend can catch up on missed WS events."""
    pipeline_id = state.get("pipeline_id")
    if not pipeline_id:
        return
    try:
        async with get_write_session() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(PipelineRun).where(PipelineRun.id == uuid.UUID(pipeline_id))
            )
            run = result.scalar_one_or_none()
            if run:
                run.current_stage = stage
                stages = run.stage_states or {}
                stages[str(stage)] = status
                run.stage_states = stages
                if status == "failed":
                    run.errors = state.get("errors", [])
    except Exception as e:
        logger.warning("Failed to persist stage %d status: %s", stage, e)


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


async def _publish(state: PipelineState, stage: int, status: str, message: str, *, detail: dict | None = None) -> None:
    if redis_client is None:
        return
    # Map "completed" → "done" for frontend StageStatus compatibility
    ws_status = "done" if status == "completed" else status
    msg: dict = {
        "type": "stage_update",
        "stage": stage,
        "status": ws_status,
        "message": message,
        "timestamp_ms": int(time.time() * 1000),
    }
    if detail is not None:
        msg["detail"] = detail
    await redis_client.publish(
        f"pipeline:{state['pipeline_id']}",
        json.dumps(msg),
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


async def _publish_build_agent(state: PipelineState, agent_number: int, agent_name: str, status: str, message: str = "", *, detail: dict | None = None) -> None:
    """Publish a per-build-agent update (used for Build stage progress cards)."""
    if redis_client is None:
        return
    ws_status = "done" if status == "completed" else status
    msg: dict = {
        "type": "build_agent_update",
        "agent_number": agent_number,
        "agent_name": agent_name,
        "status": ws_status,
        "message": message,
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

    try:
        g1 = validate_g1(state)
        state.setdefault("gate_results", {})["g1"] = g1
        if not g1["passed"]:
            # Missing idea_spec is recoverable — create a minimal one from whatever we have
            logger.warning("G1 failed: %s — creating minimal idea_spec", g1["reason"])
            if not state.get("idea_spec"):
                state["idea_spec"] = {"description": "Application", "framework": "vite_react", "name": "App"}
            g1 = {"passed": True, "reason": "idea_spec recovered"}
            state["gate_results"]["g1"] = g1

        # Layer 1: Env contract validation
        idea_spec = state.get("idea_spec", {})
        framework = idea_spec.get("framework", "vite_react")
        env_vars = idea_spec.get("env_vars", {})
        env_result = validate_env_contract(framework, env_vars)
        state.setdefault("gate_results", {})["env_contract"] = env_result
        if not env_result["passed"]:
            for var in env_result.get("missing", []):
                env_vars[var] = ""
            idea_spec["env_vars"] = env_vars

        # ── Design Architect ─────────────────────────────────────
        # Feed the user's idea through the Design Architect to generate
        # a full app structure, design system, and builder prompt.
        await _publish(state, 1, "running", "Running Design Architect…")

        from app.agents.design_architect import run_design_architect

        # Build idea_context from enriched fields (from generated ideas)
        idea_context = {}
        for field in ("problem", "solution", "market", "revenue", "tagline", "target_stack", "uniqueness", "complexity"):
            if idea_spec.get(field):
                idea_context[field] = idea_spec[field]

        design_output = await run_design_architect(
            idea=idea_spec.get("description", ""),
            name=idea_spec.get("name", ""),
            framework=framework,
            idea_context=idea_context if idea_context else None,
        )

        # Store the full design architecture output
        state["design_architecture"] = design_output

        # Enrich idea_spec with the Design Architect's structured output
        # The builder_prompt becomes the core specification for downstream agents
        if design_output.get("builder_prompt"):
            idea_spec["builder_prompt"] = design_output["builder_prompt"]
        if design_output.get("product_overview"):
            overview = design_output["product_overview"]
            idea_spec.setdefault("name", overview.get("name", ""))
            idea_spec["product_type"] = overview.get("type", "")
            idea_spec["target_audience"] = overview.get("target_audience", "")
            idea_spec["key_features"] = overview.get("key_features", [])
        if design_output.get("design_tokens"):
            idea_spec["design_tokens"] = design_output["design_tokens"]
        if design_output.get("pages"):
            idea_spec["pages"] = design_output["pages"]
        if design_output.get("component_library"):
            idea_spec["component_library"] = design_output["component_library"]
        if design_output.get("entities"):
            idea_spec["entities"] = design_output["entities"]
        if design_output.get("dependencies"):
            idea_spec["dependencies"] = design_output["dependencies"]
        if design_output.get("dev_dependencies"):
            idea_spec["dev_dependencies"] = design_output["dev_dependencies"]
        if design_output.get("interactions"):
            idea_spec["interactions"] = design_output["interactions"]
        if design_output.get("layout"):
            idea_spec["layout"] = design_output["layout"]
        if design_output.get("design_framework"):
            idea_spec["design_framework"] = design_output["design_framework"]

        state["idea_spec"] = idea_spec

    except Exception as e:
        # Input layer MUST NOT fail — log and continue with whatever state we have
        logger.exception("Input layer unexpected error (non-fatal): %s", e)
        g1 = {"passed": True, "reason": f"auto-recovered from error: {e}"}
        state.setdefault("gate_results", {})["g1"] = g1

    # ── Build rich detail for frontend display ───────────────────
    da = state.get("design_architecture", {})
    detail: dict = {
        "gate_g1": state.get("gate_results", {}).get("g1", {}),
        "env_contract": state.get("gate_results", {}).get("env_contract", {}),
    }

    # Product overview
    if da.get("product_overview"):
        detail["product_overview"] = da["product_overview"]

    # Design framework & inspiration
    if da.get("design_framework"):
        detail["design_framework"] = da["design_framework"]

    # Design tokens — show colors as a summary
    if da.get("design_tokens"):
        tokens = da["design_tokens"]
        detail["design_tokens"] = {
            "colors": tokens.get("colors", {}),
            "typography": tokens.get("typography", {}),
            "spacing": tokens.get("spacing", {}),
        }

    # Pages with full detail
    if da.get("pages"):
        detail["pages"] = da["pages"]

    # Component library
    if da.get("component_library"):
        detail["component_library"] = [
            {"name": c.get("name", ""), "purpose": c.get("purpose", "")}
            for c in da["component_library"][:20]
        ]

    # Entities
    if da.get("entities"):
        detail["entities"] = da["entities"]

    # Interactions
    if da.get("interactions"):
        detail["interactions"] = da["interactions"]

    # Builder prompt (truncated for display)
    bp = da.get("builder_prompt", "")
    if bp:
        detail["builder_prompt"] = bp[:500] + ("…" if len(bp) > 500 else "")

    await _persist_stage(state, 1, "done")
    await _publish(state, 1, "completed", "Design architecture ready", detail=detail)
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
        # Check if the agent hit an error (preserved by base class)
        agent_error = output.pop("_error", None)
        # Extract a short summary for the card display
        summary = _extract_summary(agent.name, output)
        if agent_error and not summary:
            summary = "Analysis completed with fallback defaults"
        # Include error info in the detail so the modal can display it
        detail_output = dict(output)
        if agent_error:
            detail_output["_analysis_note"] = f"Agent used fallback defaults: {agent_error}"
        await _publish_agent(state, agent.name, "completed", summary, detail=detail_output)
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

    # Build rich summaries of each agent's output for the stage detail
    agent_details = []
    role_map = {a.name: a for a in _CSUITE_AGENTS}
    role_labels = {
        "ceo": "CEO — Business Strategy", "cto": "CTO — Architecture",
        "cdo": "CDO — Design", "cmo": "CMO — Market Strategy",
        "cpo": "CPO — Product", "cso": "CSO — Security",
        "cco": "CCO — Quality", "cfo": "CFO — Finance",
    }
    for name, output in resolved_outputs.items():
        summary = _extract_summary(name, output)
        # Extract key decisions/recommendations from agent output
        highlights = []
        if isinstance(output, dict):
            for k, v in output.items():
                if isinstance(v, str) and len(v) > 10:
                    highlights.append(v[:200])
                elif isinstance(v, list) and v:
                    highlights.append(", ".join(str(x) for x in v[:5]))
                if len(highlights) >= 3:
                    break
        agent_details.append({
            "agent": role_labels.get(name, name),
            "summary": summary or "Analysis complete",
            "highlights": highlights[:3],
        })
    await _persist_stage(state, 2, "done")
    await _publish(state, 2, "completed", "C-suite analysis done", detail={
        "agents": agent_details,
        "gate_g2": g2,
        "gate_g3": g3,
        "conflict_resolutions": resolutions,
    })
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
        await _persist_stage(state, 3, "failed")
        await _publish(state, 3, "failed", g4["reason"])
        return state

    # Flatten plan into build-ready keys (pages, entities, features, components)
    await _publish(state, 3, "running", "Extracting build specification")
    idea_spec = state.get("idea_spec", {})
    state["comprehensive_plan"] = await flatten_plan(plan, idea_spec)

    # Extract rich plan sections for detail display
    plan_detail: dict = {}
    if isinstance(state.get("comprehensive_plan"), dict):
        cp = state["comprehensive_plan"]
        for key in ["pages", "entities", "features", "components", "api_routes"]:
            val = cp.get(key)
            if isinstance(val, list) and val:
                # Include actual items — extract name/description for each
                items = []
                for item in val[:20]:  # cap at 20 per category
                    if isinstance(item, dict):
                        items.append({
                            k: v for k, v in item.items()
                            if k in ("name", "description", "route", "path", "method", "type", "fields")
                            and v
                        } or item)
                    else:
                        items.append(item)
                plan_detail[key] = items
            elif val is not None:
                plan_detail[key] = val
    await _persist_stage(state, 3, "done")
    await _publish(state, 3, "completed", "Synthesis done", detail={
        **plan_detail,
        "gate_g4": g4,
    })
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

    # Build rich detail for spec layer
    spec_detail: dict = {}

    # OpenAPI: show actual routes with methods
    if isinstance(openapi_spec, dict) and openapi_spec.get("paths"):
        routes = []
        for path, methods in list(openapi_spec["paths"].items())[:25]:
            for method in methods:
                if method.upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    summary = methods[method].get("summary", "") if isinstance(methods[method], dict) else ""
                    routes.append({"method": method.upper(), "path": path, "summary": summary})
        spec_detail["api_routes"] = routes

    # Models: show model names with their fields
    if isinstance(model_defs, dict) and model_defs:
        models = []
        for name, defn in list(model_defs.items())[:15]:
            fields = list(defn.keys())[:8] if isinstance(defn, dict) else []
            models.append({"name": name, "fields": fields})
        spec_detail["data_models"] = models

    spec_detail["generated_schemas"] = {
        "pydantic": "✓ Generated" if pydantic_code else "—",
        "zod": "✓ Generated" if zod_code else "—",
        "typescript_interfaces": "✓ Generated" if ts_interfaces else "—",
    }

    await _persist_stage(state, 4, "done")
    await _publish(state, 4, "completed", "Specs generated", detail=spec_detail)
    return state


# ── Stage 5: Bootstrap ──────────────────────────────────────────
async def bootstrap(state: PipelineState) -> PipelineState:
    await _publish(state, 5, "running", "Building manifest")
    state["current_stage"] = 5

    plan = state.get("comprehensive_plan", {})
    spec_outputs = state.get("spec_outputs", {})
    idea_spec = state.get("idea_spec", {})
    framework = idea_spec.get("framework", "vite_react")

    # ── Derive the full file tree from plan ──────────────────────
    file_tree: list[dict] = []  # [{path, type, description?}]

    # Config files every project gets
    config_files = [
        "package.json", "tsconfig.json", "vite.config.ts",
        "tailwind.config.ts", "postcss.config.js", "index.html",
        "src/main.tsx", "src/App.tsx", "src/index.css",
        "src/lib/supabase.ts", "src/lib/utils.ts",
    ]
    if framework == "nextjs":
        config_files = [
            "package.json", "tsconfig.json", "next.config.js",
            "tailwind.config.ts", "postcss.config.js",
            "src/app/layout.tsx", "src/app/page.tsx", "src/app/globals.css",
            "src/lib/supabase.ts", "src/lib/utils.ts",
        ]
    for cf in config_files:
        file_tree.append({"path": cf, "type": "config"})

    # Pages → route files
    pages = plan.get("pages", [])
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict):
                comp = page.get("component") or page.get("name", "Page")
                route = page.get("path", "/")
                desc = page.get("description", "")
                if framework == "nextjs":
                    # Next.js app router convention
                    slug = route.strip("/") or ""
                    path = f"src/app/{slug}/page.tsx" if slug else "src/app/page.tsx"
                else:
                    path = f"src/pages/{comp}.tsx"
                file_tree.append({"path": path, "type": "page", "route": route, "description": desc[:100]})

    # Components → component files
    components = plan.get("components", [])
    if isinstance(components, list):
        for comp in components:
            if isinstance(comp, dict):
                name = comp.get("name", "Component")
                desc = comp.get("description", "")
                file_tree.append({"path": f"src/components/{name}.tsx", "type": "component", "description": desc[:100]})

    # Entities → type files
    entities = plan.get("entities", [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, dict):
                name = entity.get("name", "Entity")
                table = entity.get("table", name.lower() + "s")
                fields = entity.get("fields", [])
                field_names = [f.get("name", "") for f in fields if isinstance(f, dict)][:8]
                file_tree.append({
                    "path": f"src/types/{name.lower()}.ts",
                    "type": "entity",
                    "table": table,
                    "fields": field_names,
                })

    # ── Dependencies ─────────────────────────────────────────────
    deps = plan.get("dependencies", {})
    dev_deps = plan.get("dev_dependencies", {})
    if not isinstance(deps, dict):
        deps = {}
    if not isinstance(dev_deps, dict):
        dev_deps = {}

    # Ensure core deps exist
    core_runtime = {"react": "^18.3.1", "react-dom": "^18.3.1", "react-router-dom": "^6.26.0",
                    "@supabase/supabase-js": "^2.45.0", "tailwindcss": "^3.4.0"}
    if framework == "nextjs":
        core_runtime["next"] = "^14.2.0"
    for k, v in core_runtime.items():
        deps.setdefault(k, v)

    core_dev = {"typescript": "^5.4.0", "vite": "^5.4.0", "@vitejs/plugin-react": "^4.3.0",
                "@types/react": "^18.3.0", "@types/react-dom": "^18.3.0"}
    for k, v in core_dev.items():
        dev_deps.setdefault(k, v)

    # Add deps from spec layer
    model_defs = spec_outputs.get("model_defs", {})
    if model_defs:
        deps.setdefault("zod", "^3.23.0")
    if spec_outputs.get("openapi_spec"):
        deps.setdefault("axios", "^1.7.0")

    # ── Features summary ─────────────────────────────────────────
    features = plan.get("features", [])
    feature_summary: list[dict] = []
    if isinstance(features, list):
        for feat in features[:15]:
            if isinstance(feat, dict):
                feature_summary.append({
                    "name": feat.get("name", "Feature"),
                    "page": feat.get("page", ""),
                    "crud": feat.get("crud_ops", []),
                })

    state["build_manifest"] = {
        "files": [f["path"] for f in file_tree],
        "file_tree": file_tree,
        "dependencies": deps,
        "dev_dependencies": dev_deps,
        "features": feature_summary,
    }

    g6 = validate_g6(state)
    state.setdefault("gate_results", {})["g6"] = g6

    # ── Rich detail for frontend display ─────────────────────────
    detail: dict = {"gate_g6": g6}

    # Project structure — group by type
    detail["project_structure"] = {
        "config_files": [f["path"] for f in file_tree if f["type"] == "config"],
        "pages": [{
            "name": f["path"].rsplit("/", 1)[-1],
            "path": f["path"],
            "route": f.get("route", ""),
            "description": f.get("description", ""),
        } for f in file_tree if f["type"] == "page"],
        "components": [{
            "name": f["path"].rsplit("/", 1)[-1],
            "path": f["path"],
            "description": f.get("description", ""),
        } for f in file_tree if f["type"] == "component"],
        "entities": [{
            "name": f["path"].rsplit("/", 1)[-1],
            "path": f["path"],
            "table": f.get("table", ""),
            "fields": f.get("fields", []),
        } for f in file_tree if f["type"] == "entity"],
    }

    detail["dependencies"] = deps
    detail["dev_dependencies"] = dev_deps

    if feature_summary:
        detail["features"] = feature_summary

    detail["stats"] = {
        "total_files": str(len(file_tree)),
        "pages": str(len([f for f in file_tree if f["type"] == "page"])),
        "components": str(len([f for f in file_tree if f["type"] == "component"])),
        "entities": str(len([f for f in file_tree if f["type"] == "entity"])),
        "runtime_deps": str(len(deps)),
        "dev_deps": str(len(dev_deps)),
    }

    await _persist_stage(state, 5, "done")
    await _publish(state, 5, "completed", "Manifest ready", detail=detail)
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
        total_agents = len(BUILD_AGENTS)
        for agent in BUILD_AGENTS:
            await _publish(state, 6, "running", f"Agent {agent.agent_number}: {agent.name}")
            # Publish per-build-agent progress so frontend shows real-time cards
            await _publish_build_agent(state, agent.agent_number, agent.name, "running", f"Generating {agent.name} files…")

            new_files = await agent.execute(state)
            files_generated = len(new_files)
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
                await _publish_build_agent(state, agent.agent_number, agent.name, "running", "Hotfix in progress…")
                hotfix_result = await apply_hotfix(state, agent.agent_number, g7)
                if not hotfix_result.applied:
                    state.setdefault("errors", []).append(
                        f"Agent {agent.agent_number} ({agent.name}) G7 failed: {g7['reason']}"
                    )
                    await _publish_build_agent(state, agent.agent_number, agent.name, "failed", f"G7 failed: {g7['reason']}")
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

            # Agent completed — publish success with file count
            file_list = sorted(new_files.keys())
            await _publish_build_agent(
                state, agent.agent_number, agent.name, "done",
                f"{files_generated} file{'s' if files_generated != 1 else ''} generated",
                detail={"files": file_list, "agent_number": agent.agent_number, "total_agents": total_agents},
            )

        # ── Agent 10: ReviewAgent — validates only ───────────────
        await _publish(state, 6, "running", "Agent 10: review (validation only)")
        await _publish_build_agent(state, 10, "review", "running", "Running validation checks…")

        review_report = await REVIEW_AGENT.review(state)
        state.setdefault("gate_results", {})["review"] = review_report
        await _publish_build_agent(state, 10, "review", "done", "Validation complete")

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
            # Tell sandbox to re-pull files and restart dev server — files are
            # already in storage at this point so the pull will succeed.
            from app.services.file_sync_service import restart_sandbox
            restarted = await restart_sandbox(uuid.UUID(sandbox_id))
            if restarted:
                logger.info("Sandbox restart triggered for %s", sandbox_id)
            else:
                logger.warning("Sandbox restart failed for %s — user may need to reload", sandbox_id)
        else:
            logger.warning("Sandbox not ready after timeout: %s", sandbox_id)
    except Exception as e:
        logger.error("Sandbox provisioning failed (non-fatal): %s", e)

    await _persist_stage(state, 6, "done")
    await _publish(state, 6, "completed", "Build complete", detail={
        "files_generated": len(state.get("generated_files", {})),
        "file_list": sorted(state.get("generated_files", {}).keys()),
        "agents_completed": [a.name for a in BUILD_AGENTS],
        "review_report": state.get("gate_results", {}).get("review", {}),
        "sandbox_id": state.get("sandbox_id"),
    })
    return state


# ── Error Handler ────────────────────────────────────────────────
async def error_handler(state: PipelineState) -> PipelineState:
    errors = state.get("errors") or []
    stage = state.get("current_stage", 0)
    await _persist_stage(state, stage, "failed")
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
