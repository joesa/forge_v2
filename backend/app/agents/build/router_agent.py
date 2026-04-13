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
            {"name": "Home", "path": "/", "component": "HomePage", "description": "Landing page", "protected": False},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage", "description": "Main workspace with CRUD", "protected": True},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage", "description": "404 page", "protected": False},
        ])

        features = plan.get("features", [])

        system_prompt = (
            "You are a senior React developer. Generate the routing configuration and page stub files\n"
            "for a React + TypeScript app using react-router-dom v6.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- src/routes.tsx: export default a component using <Routes> and <Route>\n"
            "- One src/pages/<name>.tsx file per page — each page must use export default\n"
            "- Protected pages should be wrapped in <ProtectedRoute> (from ./components/protectedRoute)\n"
            "- All imports in src/routes.tsx use relative paths from src/ — e.g. ./pages/Home, ./components/protectedRoute\n"
            "- Every page stub must contain a meaningful skeleton reflecting the page description,\n"
            "  with proper Tailwind classes and at least a heading + description of what will go there\n"
            "- Import page components in routes.tsx using: import PageName from './pages/Name'\n"
            "- Include a catch-all NotFound route at path='*'\n"
            "- Use TypeScript strict mode, no 'any' types\n"
            "- src/routes.tsx MUST have export default — NOT named export"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n\n"
            f"Pages:\n{json.dumps(pages, indent=2, default=str)}\n\n"
            f"Features per page:\n{json.dumps(features, indent=2, default=str)}\n\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
