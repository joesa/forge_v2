from __future__ import annotations

from pydantic import BaseModel, Field


# ── CEO ──────────────────────────────────────────────────────────

class MarketOpportunity(BaseModel):
    tam: str = ""
    sam: str = ""
    som: str = ""

class CEOOutput(BaseModel):
    market_opportunity: MarketOpportunity = Field(default_factory=MarketOpportunity)
    business_model: str = ""
    revenue_strategy: str = ""
    competitive_moat: str = ""


# ── CTO ──────────────────────────────────────────────────────────

class CTOOutput(BaseModel):
    tech_stack_recommendation: dict = Field(default_factory=dict)
    api_design: str = ""
    scalability_approach: str = ""
    technical_risks: list[str] = Field(default_factory=list)


# ── CDO ──────────────────────────────────────────────────────────

class CDOOutput(BaseModel):
    ux_principles: list[str] = Field(default_factory=list)
    design_system_recommendation: str = ""
    brand_identity: dict = Field(default_factory=dict)
    user_journey_map: list[dict] = Field(default_factory=list)


# ── CMO ──────────────────────────────────────────────────────────

class CMOOutput(BaseModel):
    gtm_strategy: str = ""
    target_customer_profile: str = ""
    growth_channels: list[str] = Field(default_factory=list)
    positioning_statement: str = ""


# ── CPO ──────────────────────────────────────────────────────────

class UserStory(BaseModel):
    title: str = ""
    description: str = ""
    priority: str = "should"

class CPOOutput(BaseModel):
    feature_prioritization: dict = Field(default_factory=lambda: {
        "must": [], "should": [], "could": [], "wont": []
    })
    mvp_scope: str = ""
    user_stories: list[UserStory] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)


# ── CSO ──────────────────────────────────────────────────────────

class CSOOutput(BaseModel):
    auth_architecture: str = ""
    encryption_requirements: list[str] = Field(default_factory=list)
    compliance_needs: list[str] = Field(default_factory=list)
    threat_model: list[dict] = Field(default_factory=list)


# ── CCO ──────────────────────────────────────────────────────────

class CCOOutput(BaseModel):
    regulatory_requirements: list[str] = Field(default_factory=list)
    privacy_policy_requirements: list[str] = Field(default_factory=list)
    gdpr_obligations: list[str] = Field(default_factory=list)


# ── CFO ──────────────────────────────────────────────────────────

class CFOOutput(BaseModel):
    pricing_strategy: str = ""
    unit_economics: dict = Field(default_factory=dict)
    cac_estimate: str = ""
    ltv_estimate: str = ""
    breakeven_analysis: str = ""


# ── Comprehensive Plan ───────────────────────────────────────────

class ComprehensivePlan(BaseModel):
    ceo: CEOOutput = Field(default_factory=CEOOutput)
    cto: CTOOutput = Field(default_factory=CTOOutput)
    cdo: CDOOutput = Field(default_factory=CDOOutput)
    cmo: CMOOutput = Field(default_factory=CMOOutput)
    cpo: CPOOutput = Field(default_factory=CPOOutput)
    cso: CSOOutput = Field(default_factory=CSOOutput)
    cco: CCOOutput = Field(default_factory=CCOOutput)
    cfo: CFOOutput = Field(default_factory=CFOOutput)
    coherence_score: float = 0.0
    conflict_resolutions: list[str] = Field(default_factory=list)


# ── Schema registry for G2 validation ───────────────────────────

CSUITE_SCHEMAS: dict[str, type[BaseModel]] = {
    "ceo": CEOOutput,
    "cto": CTOOutput,
    "cdo": CDOOutput,
    "cmo": CMOOutput,
    "cpo": CPOOutput,
    "cso": CSOOutput,
    "cco": CCOOutput,
    "cfo": CFOOutput,
}
