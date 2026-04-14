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

MAX_RETRIES = 2


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
            max_tokens=4096,
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

        Retries up to MAX_RETRIES on failure. If validation fails but the LLM
        returned data, merges the raw data into the default schema so partial
        results are preserved. Never raises.
        """
        last_error: str = ""
        raw: dict = {}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = await self._run(idea_spec)
                validated = self.schema.model_validate(raw)
                return validated.model_dump()
            except ValidationError as e:
                last_error = f"Validation error (attempt {attempt}): {e}"
                logger.warning("G2 validation failed for %s (attempt %d): %s", self.name, attempt, e)
            except Exception as e:
                last_error = f"{type(e).__name__} (attempt {attempt}): {e}"
                logger.warning("%s failed (attempt %d): %s", self.name, attempt, e)

        # All retries exhausted — preserve whatever raw data the LLM returned
        defaults = self.schema().model_dump()
        if raw and isinstance(raw, dict):
            # Merge raw LLM output into defaults so partial data is kept
            for key in defaults:
                if key in raw and raw[key]:
                    val = raw[key]
                    # Basic type check: only merge if compatible
                    if isinstance(defaults[key], str) and isinstance(val, str):
                        defaults[key] = val
                    elif isinstance(defaults[key], list) and isinstance(val, list):
                        defaults[key] = val
                    elif isinstance(defaults[key], dict) and isinstance(val, dict):
                        defaults[key] = val
            logger.info("%s: merged %d raw fields into defaults after failure", self.name, sum(1 for k in defaults if k in raw and raw[k]))

        if last_error:
            defaults["_error"] = last_error
            logger.error("%s exhausted %d retries. Last error: %s", self.name, MAX_RETRIES, last_error)

        return defaults
