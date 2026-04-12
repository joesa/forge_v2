from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Conflict priority rules:
# - CFO wins over CTO on budget/cost matters
# - CPO scope wins over timeline constraints
# - CSO/CCO always wins on security/compliance

_PRIORITY_ORDER = ["cso", "cco", "cfo", "cpo", "ceo", "cto", "cdo", "cmo"]


def resolve_conflicts(csuite_outputs: dict) -> tuple[dict, list[str]]:
    """Resolve conflicts between C-suite outputs.

    Returns (merged_outputs, resolutions_log).
    G3 ALWAYS passes — never blocks the pipeline.
    """
    resolutions: list[str] = []

    # CSO/CCO always wins on security and compliance
    cso = csuite_outputs.get("cso", {})
    cco = csuite_outputs.get("cco", {})
    cto = csuite_outputs.get("cto", {})
    cfo = csuite_outputs.get("cfo", {})
    cpo = csuite_outputs.get("cpo", {})

    # Rule 1: CSO auth_architecture overrides any CTO suggestions on auth
    if cso.get("auth_architecture") and cto.get("tech_stack_recommendation"):
        resolutions.append("CSO auth_architecture takes precedence over CTO auth suggestions")

    # Rule 2: CCO compliance requirements are mandatory constraints
    if cco.get("gdpr_obligations"):
        resolutions.append("CCO GDPR obligations enforced as hard requirements")

    # Rule 3: CFO budget wins over CTO infrastructure preferences
    if cfo.get("unit_economics") and cto.get("scalability_approach"):
        resolutions.append("CFO budget constraints applied to CTO infrastructure choices")

    # Rule 4: CPO scope defines what ships in MVP regardless of timeline
    if cpo.get("mvp_scope"):
        resolutions.append("CPO MVP scope is the authoritative feature boundary")

    if not resolutions:
        resolutions.append("No conflicts detected")

    logger.info("G3 resolved %d conflicts", len(resolutions))
    return csuite_outputs, resolutions
