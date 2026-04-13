import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

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


# ── Fake LLM responses per agent role ────────────────────────────

_FAKE_LLM_RESPONSES: dict[str, dict] = {
    "ceo": {
        "market_opportunity": {"tam": "$5B task management", "sam": "$500M SMB segment", "som": "$25M year 1"},
        "business_model": "Freemium SaaS with team-based pricing",
        "revenue_strategy": "Free tier → Pro $12/mo → Enterprise custom",
        "competitive_moat": "AI-powered task prioritization and Kanban automation",
    },
    "cto": {
        "tech_stack_recommendation": {"frontend": "React + TypeScript", "backend": "FastAPI", "database": "PostgreSQL", "hosting": "Northflank"},
        "api_design": "RESTful with WebSocket for real-time board updates",
        "scalability_approach": "Horizontal scaling with connection pooling",
        "technical_risks": ["WebSocket state at scale", "Real-time sync conflicts", "File attachment storage limits"],
    },
    "cdo": {
        "ux_principles": ["Drag-and-drop first", "Minimal clicks to create task", "Clear visual hierarchy"],
        "design_system_recommendation": "Tailwind with custom Kanban components",
        "brand_identity": {"primary_color": "#4F46E5", "typography": "Inter", "tone": "Productive and clean"},
        "user_journey_map": [
            {"step": "signup", "action": "Create account", "emotion": "curious"},
            {"step": "onboarding", "action": "Create first board", "emotion": "excited"},
        ],
    },
    "cmo": {
        "gtm_strategy": "Product-led growth targeting project managers and dev teams",
        "target_customer_profile": "Small dev teams and freelancers needing visual task management",
        "growth_channels": ["ProductHunt launch", "Dev community content", "Integrations marketplace"],
        "positioning_statement": "The simplest Kanban tool for developers",
    },
    "cpo": {
        "feature_prioritization": {
            "must": ["Kanban boards", "Task CRUD", "User auth", "Drag-and-drop"],
            "should": ["Labels and filters", "Due dates", "Comments", "Notifications"],
            "could": ["Time tracking", "Calendar view"],
            "wont": ["Gantt charts", "Resource management"],
        },
        "mvp_scope": "Kanban boards + task CRUD + user auth + real-time sync",
        "user_stories": [
            {"title": "Create board", "description": "As a user I can create a new Kanban board", "priority": "must"},
            {"title": "Add task", "description": "As a user I can add a task to a column", "priority": "must"},
            {"title": "Drag task", "description": "As a user I can drag tasks between columns", "priority": "must"},
            {"title": "Edit task", "description": "As a user I can edit task details", "priority": "must"},
            {"title": "Delete task", "description": "As a user I can delete a task", "priority": "must"},
            {"title": "Sign up", "description": "As a user I can create an account", "priority": "must"},
            {"title": "Log in", "description": "As a user I can log in", "priority": "must"},
            {"title": "Add labels", "description": "As a user I can label tasks", "priority": "should"},
            {"title": "Filter tasks", "description": "As a user I can filter by label or assignee", "priority": "should"},
            {"title": "Due dates", "description": "As a user I can set due dates on tasks", "priority": "should"},
        ],
        "success_metrics": ["Board created in < 30s", "Zero onboarding failures", "> 50% day-7 retention"],
    },
    "cso": {
        "auth_architecture": "Supabase Auth with JWT/HS256 and RLS",
        "encryption_requirements": ["TLS 1.3", "AES-256-GCM for API keys", "bcrypt passwords"],
        "compliance_needs": ["OWASP Top 10", "Input sanitization", "Rate limiting"],
        "threat_model": [
            {"threat": "SQL injection", "mitigation": "Parameterized queries", "severity": "high"},
            {"threat": "XSS", "mitigation": "React auto-escaping", "severity": "high"},
        ],
    },
    "cco": {
        "regulatory_requirements": ["ToS required", "Cookie consent for EU"],
        "privacy_policy_requirements": ["Data collection disclosure", "Third-party list"],
        "gdpr_obligations": ["Consent basis", "Right to erasure", "Data portability"],
    },
    "cfo": {
        "pricing_strategy": "Free for 3 boards, Pro $12/mo unlimited",
        "unit_economics": {"cost_per_user": "$0.08", "arpu": "$6.50", "gross_margin": "82%"},
        "cac_estimate": "$18 blended",
        "ltv_estimate": "$195 at 18-month retention",
        "breakeven_analysis": "Breakeven at 1,800 paying users",
    },
}


def _mock_openai_create(agent_name: str):
    """Return an AsyncMock that returns the fake response for the given agent."""
    response_data = _FAKE_LLM_RESPONSES.get(agent_name, {})

    async def _create(**kwargs):
        msg = MagicMock()
        msg.content = json.dumps(response_data)
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    return _create


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock all OpenAI API calls in C-Suite agents to return fake responses."""
    with patch("app.agents.csuite.base.openai.AsyncOpenAI") as MockClient:
        instance = MagicMock()
        MockClient.return_value = instance

        # The create method needs to return different data per agent.
        # We capture the system prompt to determine which agent is calling.
        async def _smart_create(**kwargs):
            messages = kwargs.get("messages", [])
            system_msg = messages[0]["content"] if messages else ""

            # Map system prompt keywords to agent names
            agent_map = {
                "CEO": "ceo", "CTO": "cto", "Chief Design": "cdo",
                "CMO": "cmo", "CPO": "cpo", "Chief Security": "cso",
                "Chief Compliance": "cco", "CFO": "cfo",
            }
            agent_name = "ceo"
            for keyword, name in agent_map.items():
                if keyword.lower() in system_msg.lower():
                    agent_name = name
                    break

            response_data = _FAKE_LLM_RESPONSES.get(agent_name, {})
            msg = MagicMock()
            msg.content = json.dumps(response_data)
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        instance.chat.completions.create = _smart_create
        yield MockClient

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
