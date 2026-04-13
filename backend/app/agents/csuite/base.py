from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import openai
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

# AGENTS.md rule 6: temperature=0, seed=42
TEMPERATURE = 0
SEED = 42
MODEL = "gpt-4o"


class BaseCSuiteAgent(ABC):
    """Base class for all C-Suite agents. Enforces safe defaults on failure."""

    name: str
    schema: type[BaseModel]

    @abstractmethod
    def _system_prompt(self) -> str:
        """Return the system prompt describing this agent's role."""
        ...

    @abstractmethod
    def _user_prompt(self, idea_spec: dict) -> str:
        """Build the user prompt from the idea_spec."""
        ...

    async def _call_llm(self, idea_spec: dict) -> dict:
        """Call the LLM and parse a JSON response matching self.schema."""
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        schema_json = json.dumps(
            self.schema.model_json_schema(), indent=2
        )

        response = await client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            seed=SEED,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"{self._user_prompt(idea_spec)}\n\n"
                        f"Respond with a JSON object matching this schema:\n```json\n{schema_json}\n```"
                    ),
                },
            ],
        )

        raw_text = response.choices[0].message.content or "{}"
        return json.loads(raw_text)

    async def _run(self, idea_spec: dict) -> dict:
        """Execute agent logic via LLM. Returns raw dict to be validated."""
        return await self._call_llm(idea_spec)

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
