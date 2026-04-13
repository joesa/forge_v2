"""Agent 8: Style — generate unique palette and theme for the app."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class StyleAgent(BaseBuildAgent):
    name = "style"
    agent_number = 8

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        existing_files = state.get("generated_files", {})

        domain = plan.get("domain", idea_spec.get("category", "saas")).lower()
        app_name = idea_spec.get("name", plan.get("app_name", "app"))

        # Provide existing component/page code as context for styling
        context_files = {
            k: v for k, v in existing_files.items()
            if k.endswith(".tsx") or k.endswith(".css")
        }

        system_prompt = (
            "You are a senior UI/UX designer and frontend developer. Generate the styling and theme "
            "for a React + TypeScript app.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- tailwind.config.js: Complete Tailwind config with custom color palette, fonts, and spacing\n"
            "- src/index.css: CSS with Tailwind directives, CSS custom properties, and base styles\n"
            "- The color palette MUST be unique to this app — derive colors from the domain and app name\n"
            "- Include dark mode support\n"
            "- Define CSS custom properties for primary, secondary, accent, background, surface colors\n"
            "- body should use the background color\n"
            "- Use a professional color scheme appropriate for the app's domain\n"
            "- DO NOT use generic/default Tailwind colors — create a distinctive brand palette"
        )

        user_prompt = (
            f"App: {app_name}\n"
            f"Domain: {domain}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Existing components: {json.dumps(list(context_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
