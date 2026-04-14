"""Agent 8: Style — generate unique palette and theme for the app."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent, build_design_context
from app.agents.state import PipelineState


class StyleAgent(BaseBuildAgent):
    name = "style"
    agent_number = 8

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        existing_files = state.get("generated_files", {})

        domain = plan.get("domain", idea_spec.get("category", "saas")).lower()
        app_name = plan.get("app_name", idea_spec.get("name", "app"))

        # Provide existing component/page code as context for styling
        context_files = {
            k: v for k, v in existing_files.items()
            if k.endswith(".tsx") or k.endswith(".css")
        }

        system_prompt = (
            "You are a senior UI/UX designer and frontend developer. Generate the styling and theme\n"
            "for a React + TypeScript app.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Required files:\n"
            "- tailwind.config.js: Complete Tailwind v3 config. MUST use ESM syntax:\n"
            "    export default { content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'], ... }\n"
            "  Include custom color palette, font stack, and spacing.\n\n"
            "- src/index.css: Tailwind directives + custom CSS:\n"
            "    @tailwind base;\n"
            "    @tailwind components;\n"
            "    @tailwind utilities;\n"
            "  Plus CSS custom properties for --color-primary, --color-secondary, etc.\n"
            "  Body background color, font family, and base text styling.\n\n"
            "CRITICAL:\n"
            "- tailwind.config.js MUST use 'export default' (ESM) — NOT 'module.exports' (CJS)\n"
            "- The content array MUST include './index.html' and './src/**/*.{js,ts,jsx,tsx}'\n"
            "- Color palette must be unique and domain-appropriate — not default Tailwind\n"
            "- Include dark mode support (darkMode: 'class')\n"
            "- DO NOT include postcss.config.js — it's already generated"
        )

        design_context = build_design_context(state)
        user_prompt = (
            f"{design_context}\n\n"
            f"=== STYLE-SPECIFIC ===\n"
            f"Existing components and pages to style:\n"
            f"{json.dumps(list(context_files.keys()))}\n\n"
            f"IMPORTANT: Use the exact design tokens above for colors, typography, and spacing.\n"
            f"The tailwind.config.js must reflect the design system defined above."
        )

        return await self._call_llm(system_prompt, user_prompt)
