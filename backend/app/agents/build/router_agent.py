"""Agent 2: Router — Layer 2 inject routes, generate all route stubs."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


class RouterAgent(BaseBuildAgent):
    name = "router"
    agent_number = 2

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        spec_outputs = state.get("spec_outputs", {})

        # Extract routes from plan
        pages = plan.get("pages", [
            {"name": "Home", "path": "/", "component": "HomePage"},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage"},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage"},
        ])

        # Build route imports and elements
        imports: list[str] = []
        routes: list[str] = []

        for page in pages:
            component = page.get("component", page.get("name", "Page"))
            path = page.get("path", "/")
            # Derive import path from component name
            module = component[0].lower() + component[1:]
            imports.append(f"import {{ {component} }} from './pages/{module}';")
            routes.append(f'      <Route path="{path}" element={{<{component} />}} />')

        imports_str = "\n".join(imports)
        routes_str = "\n".join(routes)

        routes_file = f"""import {{ Routes, Route }} from 'react-router-dom';
{imports_str}

export function AppRoutes() {{
  return (
    <Routes>
{routes_str}
    </Routes>
  );
}}"""

        files: dict[str, str] = {
            "src/routes.tsx": routes_file,
        }

        # Generate stub page files so imports resolve
        for page in pages:
            component = page.get("component", page.get("name", "Page"))
            module = component[0].lower() + component[1:]
            files[f"src/pages/{module}.tsx"] = f"""export function {component}() {{
  return <div>{component}</div>;
}}"""

        return files
