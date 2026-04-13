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
            {"name": "Home", "path": "/", "component": "HomePage", "description": "Landing page"},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage", "description": "Main CRUD workspace"},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage", "description": "404 page"},
        ])
        entities = plan.get("entities", [])
        features = plan.get("features", [])

        # Provide ALL existing generated code as context
        context_files = {
            k: v for k, v in existing_files.items()
            if k.startswith("src/components/") or k == "src/routes.tsx"
            or k.startswith("src/types/") or k.startswith("src/lib/")
        }

        system_prompt = (
            "You are a senior React + TypeScript developer. Generate FULLY FUNCTIONAL page implementations.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "- Generate src/components/errorBoundary.tsx (React class component ErrorBoundary)\n"
            "- Generate each page in src/pages/<Name>.tsx with export default\n"
            "- Each page MUST be wrapped in <ErrorBoundary> and <Layout>\n\n"
            "FUNCTIONAL REQUIREMENTS (most important):\n"
            "- Pages must have REAL, WORKING functionality — NOT mock data or placeholders\n"
            "- Use Supabase client directly for data operations:\n"
            "  import { supabase } from '../lib/supabase'\n"
            "  const { data, error } = await supabase.from('table_name').select('*')\n"
            "- Dashboard/main pages MUST implement full CRUD:\n"
            "  - Fetch and display data from Supabase on mount (useEffect + useState)\n"
            "  - Add new items via a form (with controlled inputs and validation)\n"
            "  - Edit existing items (inline editing or modal form)\n"
            "  - Delete items (with confirmation)\n"
            "  - Show loading and error states\n"
            "- Home/landing page: hero section, feature highlights, call-to-action\n"
            "- Import and USE existing components from '../components' (Layout, Header, etc.)\n"
            "- Import entity-specific components if they exist (e.g. TaskForm, TaskCard)\n\n"
            "STYLING:\n"
            "- Use Tailwind CSS classes for professional appearance\n"
            "- Responsive grid layouts for item lists\n"
            "- Proper form styling with labels, inputs, buttons\n"
            "- Loading spinners, empty states, error messages\n\n"
            "TYPESCRIPT:\n"
            "- Define TypeScript interfaces for all data types inline or import from types/\n"
            "- Strict mode, no 'any' types\n"
            "- Proper event handler typing"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n\n"
            f"Pages to generate:\n{json.dumps(pages, indent=2, default=str)}\n\n"
            f"Data entities (Supabase tables):\n{json.dumps(entities, indent=2, default=str)}\n\n"
            f"Features per page:\n{json.dumps(features, indent=2, default=str)}\n\n"
            f"Existing components and code:\n{json.dumps(context_files, default=str)}\n\n"
            f"All existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
