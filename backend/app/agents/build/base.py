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
MAX_TOKENS = 16384  # 4x default — ensures agents generate full, detailed files


def build_design_context(state: PipelineState) -> str:
    """Assemble the full design context from all prior pipeline stages.

    This gives every build agent the rich output from the Design Architect,
    C-Suite analysis, synthesis, spec layer, and bootstrap — not just the
    original short user description.
    """
    idea_spec = state.get("idea_spec", {})
    design_arch = state.get("design_architecture", {})
    plan = state.get("comprehensive_plan", {})
    spec_outputs = state.get("spec_outputs", {})

    sections: list[str] = []

    # 1. Builder prompt — the most important single piece of context
    builder_prompt = idea_spec.get("builder_prompt") or design_arch.get("builder_prompt", "")
    if builder_prompt:
        sections.append(f"=== BUILDER PROMPT (follow this closely) ===\n{builder_prompt}")

    # 2. Product overview
    overview = design_arch.get("product_overview") or {}
    if overview:
        sections.append(f"=== PRODUCT OVERVIEW ===\n{json.dumps(overview, indent=2, default=str)}")

    # 3. Design framework & inspiration
    df = design_arch.get("design_framework") or idea_spec.get("design_framework") or {}
    if df:
        sections.append(f"=== DESIGN FRAMEWORK ===\n{json.dumps(df, indent=2, default=str)}")

    # 4. Design tokens — colors, typography, spacing, shadows
    tokens = idea_spec.get("design_tokens") or design_arch.get("design_tokens") or {}
    if tokens:
        sections.append(f"=== DESIGN TOKENS (use these exact values) ===\n{json.dumps(tokens, indent=2, default=str)}")

    # 5. Layout system
    layout = idea_spec.get("layout") or design_arch.get("layout") or {}
    if layout:
        sections.append(f"=== LAYOUT SYSTEM ===\n{json.dumps(layout, indent=2, default=str)}")

    # 6. Pages with full descriptions/sections
    pages = plan.get("pages") or idea_spec.get("pages") or design_arch.get("pages") or []
    if pages:
        sections.append(f"=== PAGES ===\n{json.dumps(pages, indent=2, default=str)}")

    # 7. Component library with interactions/props
    components = plan.get("components") or idea_spec.get("component_library") or design_arch.get("component_library") or []
    if components:
        sections.append(f"=== COMPONENT LIBRARY ===\n{json.dumps(components, indent=2, default=str)}")

    # 8. Entities / data models
    entities = plan.get("entities") or idea_spec.get("entities") or design_arch.get("entities") or []
    if entities:
        sections.append(f"=== DATA ENTITIES ===\n{json.dumps(entities, indent=2, default=str)}")

    # 9. Features
    features = plan.get("features") or []
    if features:
        sections.append(f"=== FEATURES ===\n{json.dumps(features, indent=2, default=str)}")

    # 10. Interactions & animations
    interactions = idea_spec.get("interactions") or design_arch.get("interactions") or {}
    if interactions:
        sections.append(f"=== INTERACTIONS & ANIMATIONS ===\n{json.dumps(interactions, indent=2, default=str)}")

    # 11. Spec layer outputs (Zod, TS interfaces)
    zod = spec_outputs.get("zod_schemas", "")
    ts_ifaces = spec_outputs.get("ts_interfaces", "")
    if zod:
        sections.append(f"=== ZOD SCHEMAS ===\n{zod}")
    if ts_ifaces:
        sections.append(f"=== TYPESCRIPT INTERFACES ===\n{ts_ifaces}")

    # 12. App metadata
    meta_parts: list[str] = []
    meta_parts.append(f"App name: {idea_spec.get('name', plan.get('app_name', 'App'))}")
    meta_parts.append(f"Framework: {idea_spec.get('framework', 'vite_react')}")
    meta_parts.append(f"Domain: {plan.get('domain', idea_spec.get('product_type', 'saas'))}")
    if idea_spec.get("target_audience"):
        meta_parts.append(f"Target audience: {idea_spec['target_audience']}")
    if idea_spec.get("key_features"):
        meta_parts.append(f"Key features: {', '.join(idea_spec['key_features'])}")
    sections.insert(0, f"=== APP METADATA ===\n" + "\n".join(meta_parts))

    return "\n\n".join(sections)


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
            max_tokens=MAX_TOKENS,
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
