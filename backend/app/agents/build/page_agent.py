"""Agent 4: Page — generate full page implementations with ErrorBoundary."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class PageAgent(BaseBuildAgent):
    name = "page"
    agent_number = 4

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        existing_files = state.get("generated_files", {})

        pages = plan.get("pages", [
            {"name": "Home", "path": "/", "component": "HomePage"},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage"},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage"},
        ])

        # Provide existing component/route code as context
        context_files = {
            k: v for k, v in existing_files.items()
            if k.startswith("src/components/") or k == "src/routes.tsx"
        }

        system_prompt = (
            "You are a senior React + TypeScript developer. Generate full page implementations.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- Generate src/components/errorBoundary.tsx (React class component ErrorBoundary)\n"
            "- Generate each page in src/pages/<name>.tsx\n"
            "- Each page MUST be wrapped in <ErrorBoundary>\n"
            "- Pages should have real, functional UI appropriate to the app's purpose\n"
            "- Import and use existing components where it makes sense\n"
            "- Use Tailwind CSS for styling — make pages visually appealing\n"
            "- Include state management with useState/useEffect where appropriate\n"
            "- Dashboard pages should have mock data visualizations or card layouts\n"
            "- Home pages should have a hero section and feature highlights\n"
            "- All code must be strict TypeScript"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Pages from plan: {json.dumps(pages, default=str)}\n"
            f"Existing components and routes:\n{json.dumps(context_files, default=str)}\n"
            f"All existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
