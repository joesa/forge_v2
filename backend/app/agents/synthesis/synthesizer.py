from __future__ import annotations

import logging

from app.agents.csuite.schemas import (
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

logger = logging.getLogger(__name__)


async def synthesize(csuite_outputs: dict, conflict_resolutions: list[str]) -> dict:
    """Merge all 8 C-suite outputs into a ComprehensivePlan with coherence_score.

    Returns plan dict. Never raises — returns safe defaults on failure.
    """
    try:
        plan = ComprehensivePlan(
            ceo=CEOOutput.model_validate(csuite_outputs.get("ceo", {})),
            cto=CTOOutput.model_validate(csuite_outputs.get("cto", {})),
            cdo=CDOOutput.model_validate(csuite_outputs.get("cdo", {})),
            cmo=CMOOutput.model_validate(csuite_outputs.get("cmo", {})),
            cpo=CPOOutput.model_validate(csuite_outputs.get("cpo", {})),
            cso=CSOOutput.model_validate(csuite_outputs.get("cso", {})),
            cco=CCOOutput.model_validate(csuite_outputs.get("cco", {})),
            cfo=CFOOutput.model_validate(csuite_outputs.get("cfo", {})),
            conflict_resolutions=conflict_resolutions,
            coherence_score=_compute_coherence(csuite_outputs),
        )
        return plan.model_dump()
    except Exception as e:
        logger.warning("Synthesis failed, returning defaults: %s", e)
        return ComprehensivePlan().model_dump()


def _compute_coherence(outputs: dict) -> float:
    """Score 0.0–1.0 based on how many agents produced non-empty output."""
    expected = {"ceo", "cto", "cdo", "cmo", "cpo", "cso", "cco", "cfo"}
    present = 0
    for key in expected:
        agent_out = outputs.get(key, {})
        if agent_out and any(v for v in agent_out.values() if v):
            present += 1
    # Base score: fraction of agents with output, scaled to 0.80–1.0 range
    ratio = present / len(expected)
    return round(0.80 + (ratio * 0.20), 2)
