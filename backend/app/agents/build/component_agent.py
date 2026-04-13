"""Agent 3: Component — Layer 2 inject Zod schemas, generate UI components."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class ComponentAgent(BaseBuildAgent):
    name = "component"
    agent_number = 3

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        spec_outputs = state.get("spec_outputs", {})
        existing_files = state.get("generated_files", {})

        zod_schemas = spec_outputs.get("zod_schemas", "")
        ts_interfaces = spec_outputs.get("ts_interfaces", "")
        components = plan.get("components", [
            {"name": "Header", "props": []},
            {"name": "Footer", "props": []},
            {"name": "Layout", "props": ["children"]},
        ])

        system_prompt = (
            "You are a senior React + TypeScript developer. Generate reusable UI components.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- Generate each component in src/components/<name>.tsx\n"
            "- Create src/components/index.ts barrel export file\n"
            "- If Zod schemas are provided, create src/lib/schemas.ts\n"
            "- If TypeScript interfaces are provided, create src/types/models.ts\n"
            "- Components must be functional React components with proper TypeScript props interfaces\n"
            "- Use Tailwind CSS for styling\n"
            "- Components should be production-quality with real, useful UI — not just placeholders\n"
            "- Each component should render meaningful content appropriate to its purpose\n"
            "- Include a Layout component that wraps children with a header and navigation"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Components from plan: {json.dumps(components, default=str)}\n"
            f"Zod schemas:\n{zod_schemas or '(none)'}\n\n"
            f"TypeScript interfaces:\n{ts_interfaces or '(none)'}\n\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
