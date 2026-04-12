import asyncio

import pytest

from app.agents.csuite.ceo_agent import CEOAgent
from app.agents.csuite.cto_agent import CTOAgent
from app.agents.csuite.cdo_agent import CDOAgent
from app.agents.csuite.cmo_agent import CMOAgent
from app.agents.csuite.cpo_agent import CPOAgent
from app.agents.csuite.cso_agent import CSOAgent
from app.agents.csuite.cco_agent import CCOAgent
from app.agents.csuite.cfo_agent import CFOAgent
from app.agents.csuite.schemas import (
    CSUITE_SCHEMAS,
    CEOOutput,
    CTOOutput,
    CDOOutput,
    CMOOutput,
    CPOOutput,
    CSOOutput,
    CCOOutput,
    CFOOutput,
    ComprehensivePlan,
)
from app.agents.synthesis.g3_resolver import resolve_conflicts
from app.agents.synthesis.synthesizer import synthesize
from app.agents.validators import validate_g2, validate_g3, validate_g4
from app.agents.state import PipelineState


IDEA_SPEC = {"description": "A task management app with Kanban boards"}


# ── Agent output tests ───────────────────────────────────────────

_ALL_AGENTS = [
    (CEOAgent(), "ceo", CEOOutput),
    (CTOAgent(), "cto", CTOOutput),
    (CDOAgent(), "cdo", CDOOutput),
    (CMOAgent(), "cmo", CMOOutput),
    (CPOAgent(), "cpo", CPOOutput),
    (CSOAgent(), "cso", CSOOutput),
    (CCOAgent(), "cco", CCOOutput),
    (CFOAgent(), "cfo", CFOOutput),
]


@pytest.mark.parametrize("agent,name,schema", _ALL_AGENTS, ids=[a[1] for a in _ALL_AGENTS])
async def test_agent_output_validates(agent, name, schema):
    """Each agent output must pass its Pydantic schema (G2)."""
    output = await agent.execute(IDEA_SPEC)
    validated = schema.model_validate(output)
    assert validated is not None


async def test_all_8_agents_parallel():
    """All 8 agents run in parallel and return valid outputs."""
    agents = [a[0] for a in _ALL_AGENTS]

    async def _run(agent):
        return agent.name, await agent.execute(IDEA_SPEC)

    results = await asyncio.gather(*[_run(a) for a in agents])
    outputs = dict(results)

    assert len(outputs) == 8
    for name in ["ceo", "cto", "cdo", "cmo", "cpo", "cso", "cco", "cfo"]:
        assert name in outputs
        schema = CSUITE_SCHEMAS[name]
        schema.model_validate(outputs[name])


# ── Agent safe-default tests ─────────────────────────────────────

async def test_agent_returns_defaults_on_bad_input():
    """Agent must never raise — returns safe defaults."""
    ceo = CEOAgent()
    # Monkey-patch _run to throw
    async def _bad_run(idea_spec):
        raise RuntimeError("API down")
    ceo._run = _bad_run
    output = await ceo.execute(IDEA_SPEC)
    # Should be the safe defaults, not raise
    validated = CEOOutput.model_validate(output)
    assert validated.business_model == ""  # default


# ── G2 validation test ──────────────────────────────────────────

async def test_g2_validates_all_outputs():
    """G2 validates each agent output against Pydantic schema."""
    agents = [a[0] for a in _ALL_AGENTS]

    async def _run(agent):
        return agent.name, await agent.execute(IDEA_SPEC)

    results = await asyncio.gather(*[_run(a) for a in agents])
    state: PipelineState = {
        "idea_spec": IDEA_SPEC,
        "pipeline_id": "test",
        "project_id": "test",
        "user_id": "test",
        "current_stage": 2,
        "csuite_outputs": dict(results),
    }
    g2 = validate_g2(state)
    assert g2["passed"] is True


async def test_g2_fails_on_invalid_output():
    """G2 fails if an output doesn't match its schema type expectations."""
    state: PipelineState = {
        "idea_spec": IDEA_SPEC,
        "pipeline_id": "test",
        "project_id": "test",
        "user_id": "test",
        "current_stage": 2,
        "csuite_outputs": {},
    }
    g2 = validate_g2(state)
    assert g2["passed"] is False


# ── G3 resolver tests ───────────────────────────────────────────

async def test_g3_always_passes():
    """G3 always returns passed=True."""
    state: PipelineState = {
        "idea_spec": IDEA_SPEC,
        "pipeline_id": "test",
        "project_id": "test",
        "user_id": "test",
        "current_stage": 2,
    }
    result = validate_g3(state)
    assert result["passed"] is True
    assert result["reason"] == "auto-resolved"


async def test_g3_resolver_produces_resolutions():
    """G3 resolver detects and logs conflict resolutions."""
    agents = [a[0] for a in _ALL_AGENTS]

    async def _run(agent):
        return agent.name, await agent.execute(IDEA_SPEC)

    results = await asyncio.gather(*[_run(a) for a in agents])
    outputs = dict(results)
    resolved, resolutions = resolve_conflicts(outputs)
    assert len(resolutions) > 0
    assert resolved is outputs  # same dict, just annotated


async def test_g3_resolver_cso_wins():
    """CSO auth_architecture takes precedence over CTO."""
    outputs = {
        "cso": {"auth_architecture": "Supabase Auth"},
        "cto": {"tech_stack_recommendation": {"auth": "custom JWT"}},
    }
    _, resolutions = resolve_conflicts(outputs)
    assert any("CSO" in r for r in resolutions)


async def test_g3_resolver_cfo_wins_budget():
    """CFO budget wins over CTO infra."""
    outputs = {
        "cfo": {"unit_economics": {"cost": "$0.10"}},
        "cto": {"scalability_approach": "expensive multi-region"},
    }
    _, resolutions = resolve_conflicts(outputs)
    assert any("CFO" in r for r in resolutions)


# ── Synthesizer tests ────────────────────────────────────────────

async def test_synthesizer_produces_comprehensive_plan():
    """Synthesizer merges all 8 outputs into ComprehensivePlan with coherence_score."""
    agents = [a[0] for a in _ALL_AGENTS]

    async def _run(agent):
        return agent.name, await agent.execute(IDEA_SPEC)

    results = await asyncio.gather(*[_run(a) for a in agents])
    outputs = dict(results)
    _, resolutions = resolve_conflicts(outputs)

    plan = await synthesize(outputs, resolutions)
    validated = ComprehensivePlan.model_validate(plan)

    assert validated.coherence_score >= 0.85
    assert validated.ceo.business_model != ""
    assert validated.cto.api_design != ""
    assert len(validated.cpo.user_stories) == 10


async def test_synthesizer_coherence_above_085():
    """When all 8 agents succeed, coherence_score >= 0.85."""
    agents = [a[0] for a in _ALL_AGENTS]

    async def _run(agent):
        return agent.name, await agent.execute(IDEA_SPEC)

    results = await asyncio.gather(*[_run(a) for a in agents])
    outputs = dict(results)

    plan = await synthesize(outputs, [])
    assert plan["coherence_score"] >= 0.85


# ── G4 gate test ─────────────────────────────────────────────────

async def test_g4_passes_with_full_outputs():
    """G4 passes when coherence_score >= 0.85."""
    agents = [a[0] for a in _ALL_AGENTS]

    async def _run(agent):
        return agent.name, await agent.execute(IDEA_SPEC)

    results = await asyncio.gather(*[_run(a) for a in agents])
    outputs = dict(results)
    plan = await synthesize(outputs, [])

    state: PipelineState = {
        "idea_spec": IDEA_SPEC,
        "pipeline_id": "test",
        "project_id": "test",
        "user_id": "test",
        "current_stage": 3,
        "comprehensive_plan": plan,
    }
    g4 = validate_g4(state)
    assert g4["passed"] is True


async def test_g4_fails_low_coherence():
    """G4 fails when coherence_score < 0.85."""
    state: PipelineState = {
        "idea_spec": IDEA_SPEC,
        "pipeline_id": "test",
        "project_id": "test",
        "user_id": "test",
        "current_stage": 3,
        "comprehensive_plan": {"coherence_score": 0.50},
    }
    g4 = validate_g4(state)
    assert g4["passed"] is False


# ── CEO-specific fields ─────────────────────────────────────────

async def test_ceo_has_tam_sam_som():
    ceo = CEOAgent()
    output = await ceo.execute(IDEA_SPEC)
    assert "market_opportunity" in output
    mo = output["market_opportunity"]
    assert "tam" in mo
    assert "sam" in mo
    assert "som" in mo


# ── CPO MoSCoW ───────────────────────────────────────────────────

async def test_cpo_has_moscow():
    cpo = CPOAgent()
    output = await cpo.execute(IDEA_SPEC)
    fp = output["feature_prioritization"]
    assert "must" in fp
    assert "should" in fp
    assert "could" in fp
    assert "wont" in fp


# ── CPO top 10 user stories ─────────────────────────────────────

async def test_cpo_has_10_user_stories():
    cpo = CPOAgent()
    output = await cpo.execute(IDEA_SPEC)
    assert len(output["user_stories"]) == 10


# ── CFO fields ───────────────────────────────────────────────────

async def test_cfo_has_all_fields():
    cfo = CFOAgent()
    output = await cfo.execute(IDEA_SPEC)
    assert output["pricing_strategy"] != ""
    assert output["unit_economics"] != {}
    assert output["cac_estimate"] != ""
    assert output["ltv_estimate"] != ""
    assert output["breakeven_analysis"] != ""
