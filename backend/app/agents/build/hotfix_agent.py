"""Hotfix agent — callable stub for automated fixes."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agents.state import PipelineState

logger = logging.getLogger(__name__)


@dataclass
class HotfixResult:
    applied: bool
    agent_number: int
    description: str
    files_modified: list[str]


async def apply_hotfix(
    state: PipelineState,
    agent_number: int,
    gate_result: dict,
) -> HotfixResult:
    """Attempt to auto-fix a gate failure after a build agent.

    Currently a stub — returns not_yet_implemented.
    """
    logger.warning(
        "Hotfix requested for agent %d (gate: %s) — not yet implemented",
        agent_number,
        gate_result.get("reason", "unknown"),
    )
    return HotfixResult(
        applied=False,
        agent_number=agent_number,
        description="not_yet_implemented",
        files_modified=[],
    )


class HotfixAgent:
    """Container for the hotfix stub — used for registry/discovery."""

    name = "hotfix"

    async def execute(self, state: PipelineState, agent_number: int, gate_result: dict) -> HotfixResult:
        return await apply_hotfix(state, agent_number, gate_result)
