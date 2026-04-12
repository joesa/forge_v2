from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    idea_spec: dict
    pipeline_id: str
    project_id: str
    user_id: str
    current_stage: int  # 1-6
    csuite_outputs: dict
    comprehensive_plan: dict
    spec_outputs: dict
    build_manifest: dict
    generated_files: dict[str, str]
    gate_results: dict[str, dict]
    errors: list[str]
    sandbox_id: str | None
