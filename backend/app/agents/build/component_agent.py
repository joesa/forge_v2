"""Agent 3: Component — Layer 2 inject Zod schemas, generate UI components."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent, build_design_context
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
            {"name": "Header", "props": [], "description": "Navigation header with links"},
            {"name": "Footer", "props": [], "description": "Page footer"},
            {"name": "Layout", "props": [{"name": "children", "type": "ReactNode", "required": True}],
             "description": "Page layout wrapper with Header, main content, Footer"},
        ])
        entities = plan.get("entities", [])
        features = plan.get("features", [])

        system_prompt = (
            "You are a senior React + TypeScript developer. Generate reusable UI components\n"
            "that will be used by the page implementations.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- Generate each component in src/components/<Name>.tsx\n"
            "- Create src/components/index.ts barrel export (re-export defaults as named exports)\n"
            "- If Zod schemas are provided, create src/lib/schemas.ts\n"
            "- If TypeScript interfaces are provided, create src/types/models.ts\n"
            "- Components MUST be functional React components with TypeScript props interfaces\n"
            "- Use Tailwind CSS for styling — professional, polished appearance\n"
            "- Each component must be REAL and FUNCTIONAL:\n"
            "  - Form components must have controlled inputs with onChange/onSubmit handlers\n"
            "  - List components must accept data arrays and render items with actions\n"
            "  - Modal/dialog components must handle open/close state via props\n"
            "  - Card components must display entity data with edit/delete action buttons\n"
            "- Layout component: wraps children with Header (nav links matching routes) + Footer\n"
            "- Header MUST include navigation links matching the app's pages\n"
            "- All components use export default\n"
            "- Use TypeScript strict mode, no 'any' types\n\n"
            "CRITICAL: Generate components that the Page agent will actually USE for CRUD operations.\n"
            "For example, if the app manages tasks, generate a TaskForm, TaskCard, TaskList component."
        )

        design_context = build_design_context(state)
        user_prompt = (
            f"{design_context}\n\n"
            f"=== COMPONENT-SPECIFIC ===\n"
            f"Components from plan:\n{json.dumps(components, indent=2, default=str)}\n\n"
            f"Entities (data models the components will display/edit):\n"
            f"{json.dumps(entities, indent=2, default=str)}\n\n"
            f"Features (what the components need to support):\n"
            f"{json.dumps(features, indent=2, default=str)}\n\n"
            f"Zod schemas:\n{zod_schemas or '(none)'}\n\n"
            f"TypeScript interfaces:\n{ts_interfaces or '(none)'}\n\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
