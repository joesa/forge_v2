from __future__ import annotations

from app.agents.state import PipelineState


def validate_g1(state: PipelineState) -> dict:
    if not state.get("idea_spec"):
        return {"passed": False, "reason": "idea_spec is empty"}
    return {"passed": True, "reason": "idea_spec present"}


def validate_g2(state: PipelineState) -> dict:
    if not state.get("csuite_outputs"):
        return {"passed": False, "reason": "csuite_outputs missing"}
    return {"passed": True, "reason": "csuite_outputs present"}


def validate_g3(state: PipelineState) -> dict:
    return {"passed": True, "reason": "auto-resolved"}


def validate_g4(state: PipelineState) -> dict:
    plan = state.get("comprehensive_plan") or {}
    score = plan.get("coherence_score", 0)
    if score >= 0.85:
        return {"passed": True, "reason": f"coherence_score={score}"}
    return {"passed": False, "reason": f"coherence_score={score} < 0.85"}


def validate_g5(state: PipelineState) -> dict:
    if not state.get("spec_outputs"):
        return {"passed": False, "reason": "spec_outputs missing"}
    return {"passed": True, "reason": "spec_outputs present"}


def validate_g6(state: PipelineState) -> dict:
    if not state.get("build_manifest"):
        return {"passed": False, "reason": "build_manifest missing"}
    return {"passed": True, "reason": "build_manifest present"}


def validate_g7(state: PipelineState) -> dict:
    if not state.get("generated_files"):
        return {"passed": False, "reason": "no generated_files"}
    return {"passed": True, "reason": "generated_files present"}


def validate_g8(state: PipelineState) -> dict:
    errors = state.get("errors") or []
    if errors:
        return {"passed": False, "reason": f"{len(errors)} errors"}
    return {"passed": True, "reason": "no errors"}


def validate_g9(state: PipelineState) -> dict:
    if not state.get("sandbox_id"):
        return {"passed": False, "reason": "sandbox_id missing"}
    return {"passed": True, "reason": "sandbox_id present"}


def validate_g10(state: PipelineState) -> dict:
    return {"passed": True, "reason": "placeholder"}


def validate_g11(state: PipelineState) -> dict:
    return {"passed": True, "reason": "placeholder"}


def validate_g12(state: PipelineState) -> dict:
    return {"passed": True, "reason": "placeholder"}
