"""Agent 2: Router — generate routes and page stubs from plan."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class RouterAgent(BaseBuildAgent):
    name = "router"
    agent_number = 2

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        existing_files = state.get("generated_files", {})

        pages = plan.get("pages", [
            {"name": "Home", "path": "/", "component": "HomePage"},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage"},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage"},
        ])

        system_prompt = (
            "You are a senior React developer. Generate the routing configuration and page stub files "
            "for a React + TypeScript app using react-router-dom v6.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- src/routes.tsx: AppRoutes component using <Routes> and <Route> from react-router-dom\n"
            "- One src/pages/<name>.tsx file per page with a real, functional stub component\n"
            "- Each page should have meaningful placeholder content that reflects its purpose\n"
            "- Use proper TypeScript and export named functions\n"
            "- Import all page components in routes.tsx\n"
            "- Include a catch-all NotFound route with path='*'\n"
            "- Page components should have appropriate Tailwind styling"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Pages from plan: {json.dumps(pages, default=str)}\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
