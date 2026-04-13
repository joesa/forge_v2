"""Agent 1: Scaffold — Layer 1 first, scaffold project structure + CI."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState
from app.reliability.layer1_pregeneration.dependency_resolver import resolve_dependencies
from app.reliability.layer1_pregeneration.lockfile_generator import generate_package_json
from app.reliability.layer1_pregeneration.env_contract_validator import get_env_template


class ScaffoldAgent(BaseBuildAgent):
    name = "scaffold"
    agent_number = 1

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        framework = idea_spec.get("framework", "vite_react")
        app_name = idea_spec.get("name", plan.get("app_name", "forge-app"))

        # Layer 1: Resolve dependencies
        raw_deps = plan.get("dependencies", {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "react-router-dom": "^6.23.0",
        })
        resolved_deps = resolve_dependencies(raw_deps)

        dev_deps = plan.get("dev_dependencies", {
            "typescript": "^5.4.0",
            "vite": "^5.4.0",
            "@types/react": "^18.3.0",
            "@types/react-dom": "^18.3.0",
            "tailwindcss": "^3.4.0",
            "postcss": "^8.4.0",
            "autoprefixer": "^10.4.0",
        })

        # Layer 1: Generate package.json (deterministic — no LLM needed)
        package_json = generate_package_json(resolved_deps, dev_deps, name=app_name)
        env_template = get_env_template(framework)

        system_prompt = (
            "You are a senior full-stack developer setting up a new Vite + React + TypeScript project. "
            "Generate the project scaffold files. Return a JSON object where each key is a file path "
            "and the value is the complete file content as a string.\n\n"
            "Required files:\n"
            "- tsconfig.json (strict mode, ES2020 target, bundler resolution)\n"
            "- tsconfig.node.json\n"
            "- vite.config.ts (port 3000, path aliases with @/ -> src/)\n"
            "- index.html (reference /src/main.tsx)\n"
            "- src/main.tsx (React 18 createRoot)\n"
            "- src/App.tsx (BrowserRouter wrapping AppRoutes from ./routes)\n"
            "- src/index.css (Tailwind directives)\n"
            "- tailwind.config.js (content paths for index.html + src/**)\n"
            "- postcss.config.js\n"
            "- .gitignore\n\n"
            "DO NOT include package.json or .env.example — those are provided separately.\n"
            "All code must be production-quality TypeScript with strict mode."
        )

        user_prompt = (
            f"App name: {app_name}\n"
            f"Framework: {framework}\n"
            f"Description: {idea_spec.get('description', 'A web application')}\n"
            f"Plan summary: {json.dumps(plan.get('summary', plan.get('description', '')), default=str)}\n"
            f"Dependencies: {json.dumps(list(resolved_deps.keys()), default=str)}"
        )

        files = await self._call_llm(system_prompt, user_prompt)

        # Merge deterministic Layer 1 outputs (these always override LLM)
        files["package.json"] = package_json
        files[".env.example"] = env_template

        return files
