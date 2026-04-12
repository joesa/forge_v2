"""Base class for all build agents. temperature=0, seed=42."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.agents.state import PipelineState

logger = logging.getLogger(__name__)

TEMPERATURE = 0
SEED = 42


class BaseBuildAgent(ABC):
    """Base class for sequential build agents 1-9 + review agent 10.

    All build agents use temperature=0, seed=42 for deterministic output.
    """

    name: str
    agent_number: int

    @abstractmethod
    async def _run(self, state: PipelineState) -> dict[str, str]:
        """Execute agent logic. Returns dict of filename → content to merge into generated_files."""
        ...

    async def execute(self, state: PipelineState) -> dict[str, str]:
        """Run agent and return generated files. Never raises — returns empty dict on failure."""
        try:
            result = await self._run(state)
            logger.info("Agent %d (%s) generated %d files", self.agent_number, self.name, len(result))
            return result
        except Exception as e:
            logger.error("Agent %d (%s) failed: %s", self.agent_number, self.name, e)
            return {}
