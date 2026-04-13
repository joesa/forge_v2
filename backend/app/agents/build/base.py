"""Base class for all build agents. temperature=0, seed=42."""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import openai

from app.agents.state import PipelineState
from app.config import settings

logger = logging.getLogger(__name__)

TEMPERATURE = 0
SEED = 42
MODEL = "gpt-4o"


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

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> dict[str, str]:
        """Call LLM and parse response as JSON dict of filename → content.

        The LLM must return a JSON object where keys are file paths and values
        are complete file contents as strings.
        """
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            seed=SEED,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)

        # Handle nested "files" key if the LLM wraps it
        if "files" in parsed and isinstance(parsed["files"], dict):
            parsed = parsed["files"]

        # Ensure all values are strings
        return {k: str(v) for k, v in parsed.items() if isinstance(k, str)}
