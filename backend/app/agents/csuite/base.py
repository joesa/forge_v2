from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

TEMPERATURE = 0.7


class BaseCSuiteAgent(ABC):
    """Base class for all C-Suite agents. Enforces safe defaults on failure."""

    name: str
    schema: type[BaseModel]

    @abstractmethod
    async def _run(self, idea_spec: dict) -> dict:
        """Execute agent logic. Returns raw dict to be validated."""
        ...

    async def execute(self, idea_spec: dict) -> dict:
        """Run agent and validate output against Pydantic schema.
        Returns safe defaults on any failure — never raises."""
        try:
            raw = await self._run(idea_spec)
            validated = self.schema.model_validate(raw)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning("G2 validation failed for %s: %s", self.name, e)
            return self.schema().model_dump()
        except Exception as e:
            logger.warning("%s failed, returning safe defaults: %s", self.name, e)
            return self.schema().model_dump()
