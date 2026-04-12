"""Hotfix agent — delegates to Layer 9 real implementation."""
from __future__ import annotations

from app.agents.state import PipelineState
from app.reliability.layer9_resilience.hotfix_agent import (
    HotfixResult,
    apply_hotfix,
)

__all__ = ["HotfixAgent", "HotfixResult", "apply_hotfix"]


class HotfixAgent:
    """Container for the hotfix agent — delegates to Layer 9."""

    name = "hotfix"

    async def execute(self, state: PipelineState, agent_number: int, gate_result: dict) -> HotfixResult:
        return await apply_hotfix(state, agent_number, gate_result)
