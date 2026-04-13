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
        app_name = plan.get("app_name", idea_spec.get("name", "forge-app"))

        # Layer 1: Resolve dependencies from plan
        raw_deps = plan.get("dependencies", {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "react-router-dom": "^6.23.0",
            "@supabase/supabase-js": "^2.45.0",
            "zod": "^3.23.0",
        })
        resolved_deps = resolve_dependencies(raw_deps)

        dev_deps = plan.get("dev_dependencies", {
            "typescript": "^5.4.0",
            "vite": "^5.4.0",
            "@vitejs/plugin-react": "^4.3.0",
            "@types/react": "^18.3.0",
            "@types/react-dom": "^18.3.0",
            "tailwindcss": "^3.4.0",
            "postcss": "^8.4.0",
            "autoprefixer": "^10.4.0",
        })

        # Enforce minimum compatible versions for core toolchain
        # (plan may hallucinate incompatible versions)
        _REQUIRED_DEPS = {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
        }
        _REQUIRED_DEV_DEPS = {
            "vite": "^5.4.0",
            "@vitejs/plugin-react": "^4.3.0",
            "typescript": "^5.4.0",
            "@types/react": "^18.3.0",
            "@types/react-dom": "^18.3.0",
            "tailwindcss": "^3.4.0",
            "postcss": "^8.4.0",
            "autoprefixer": "^10.4.0",
        }
        for k, v in _REQUIRED_DEPS.items():
            resolved_deps[k] = v
        for k, v in _REQUIRED_DEV_DEPS.items():
            dev_deps[k] = v

        # Layer 1: Generate package.json (deterministic — no LLM needed)
        package_json = generate_package_json(resolved_deps, dev_deps, name=app_name)
        env_template = get_env_template(framework)

        system_prompt = (
            "You are a senior full-stack developer setting up a new Vite + React + TypeScript project.\n"
            "Generate the project scaffold files. Return a JSON object where each key is a file path\n"
            "and the value is the complete file content as a string.\n\n"
            "Required files:\n"
            "- tsconfig.json (strict mode, ES2020 target, bundler resolution)\n"
            "- tsconfig.node.json\n"
            "- vite.config.ts — MUST include:\n"
            "  - @vitejs/plugin-react plugin\n"
            "  - server.port = 3000, server.host = '0.0.0.0'\n"
            "  - server.allowedHosts = true\n"
            "  - resolve.alias: '@' → './src'\n"
            "- index.html (reference /src/main.tsx, include <div id='root'>)\n"
            "- src/main.tsx (React 18 createRoot, import App and index.css)\n"
            "- src/App.tsx (BrowserRouter wrapping AppRoutes from ./routes)\n"
            "- src/index.css (Tailwind directives: @tailwind base/components/utilities)\n"
            "- tailwind.config.js — MUST use ESM syntax (export default), include content paths\n"
            "- postcss.config.js — MUST use ESM syntax (export default)\n"
            "- .gitignore\n\n"
            "CRITICAL: The package.json uses \"type\": \"module\", so ALL .js config files MUST use\n"
            "ESM syntax (export default {...}) — NOT CommonJS (module.exports = {...}).\n\n"
            "DO NOT include package.json or .env.example — those are provided separately.\n"
            "All code must be production-quality TypeScript with strict mode."
        )

        user_prompt = (
            f"App name: {app_name}\n"
            f"Framework: {framework}\n"
            f"Description: {idea_spec.get('description', 'A web application')}\n"
            f"Domain: {plan.get('domain', 'saas')}\n"
            f"Dependencies: {json.dumps(list(resolved_deps.keys()), default=str)}"
        )

        files = await self._call_llm(system_prompt, user_prompt)

        # Merge deterministic Layer 1 outputs (these always override LLM)
        files["package.json"] = package_json
        files[".env.example"] = env_template

        return files
