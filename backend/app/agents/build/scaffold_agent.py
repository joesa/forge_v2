"""Agent 1: Scaffold — Layer 1 first, scaffold project structure + CI."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
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

        # Layer 1: Generate package.json
        package_json = generate_package_json(resolved_deps, dev_deps, name=app_name)

        # Layer 1: Env template
        env_template = get_env_template(framework)

        files: dict[str, str] = {}

        files["package.json"] = package_json

        files[".env.example"] = env_template

        files["tsconfig.json"] = """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}"""

        files["tsconfig.node.json"] = """{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}"""

        files["vite.config.ts"] = """import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
  },
});"""

        files["index.html"] = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{app_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>"""

        files["src/main.tsx"] = """import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);"""

        files["src/App.tsx"] = """import { BrowserRouter } from 'react-router-dom';
import { AppRoutes } from './routes';

export function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}"""

        files["src/index.css"] = """@tailwind base;
@tailwind components;
@tailwind utilities;
"""

        files["tailwind.config.js"] = """/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
};"""

        files["postcss.config.js"] = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};"""

        files[".gitignore"] = """node_modules/
dist/
.env
.env.local
*.log
"""

        return files
