"""Tests for build agents, snapshot service, hotfix agent, and graph Stage 6."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

import pytest

from app.agents.state import PipelineState
from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.build.scaffold_agent import ScaffoldAgent
from app.agents.build.router_agent import RouterAgent
from app.agents.build.component_agent import ComponentAgent
from app.agents.build.page_agent import PageAgent
from app.agents.build.api_agent import APIAgent
from app.agents.build.db_agent import DBAgent
from app.agents.build.auth_agent import AuthAgent
from app.agents.build.style_agent import StyleAgent
from app.agents.build.test_agent import TestAgent
from app.agents.build.review_agent import ReviewAgent
from app.agents.build.hotfix_agent import HotfixAgent, HotfixResult, apply_hotfix
from app.agents.build import BUILD_AGENTS, REVIEW_AGENT


PIPELINE_ID = str(uuid.uuid4())
PROJECT_ID = str(uuid.uuid4())


def _base_state(**overrides) -> PipelineState:
    state: PipelineState = {
        "idea_spec": {"name": "test-app", "framework": "vite_react", "description": "A test app"},
        "pipeline_id": PIPELINE_ID,
        "project_id": PROJECT_ID,
        "user_id": str(uuid.uuid4()),
        "current_stage": 6,
        "csuite_outputs": {},
        "comprehensive_plan": {
            "app_name": "test-app",
            "pages": [
                {"name": "Home", "path": "/", "component": "HomePage"},
                {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage"},
                {"name": "NotFound", "path": "*", "component": "NotFoundPage"},
            ],
            "components": [
                {"name": "Header", "props": []},
                {"name": "Footer", "props": []},
            ],
            "entities": [
                {"name": "User", "fields": {"id": "string", "email": "string", "name": "string"}},
            ],
            "domain": "saas",
        },
        "spec_outputs": {
            "openapi_spec": {
                "paths": {
                    "/api/users": {
                        "get": {
                            "operationId": "list_users",
                            "responses": {
                                "200": {
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/UserList"}
                                        }
                                    }
                                }
                            },
                        }
                    }
                }
            },
            "zod_schemas": "export const UserSchema = z.object({ id: z.string() });",
            "ts_interfaces": "export interface User { id: string; }",
            "pydantic_code": "class User(BaseModel): id: str",
            "model_defs": {"User": {"id": "string", "email": "string"}},
        },
        "build_manifest": {"files": [], "dependencies": []},
        "generated_files": {},
        "gate_results": {},
        "errors": [],
        "sandbox_id": None,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# ── Mock LLM responses for each agent ───────────────────────────

SCAFFOLD_LLM_RESPONSE = {
    "tsconfig.json": '{"compilerOptions":{"target":"ES2020","strict":true}}',
    "tsconfig.node.json": '{"compilerOptions":{"composite":true}}',
    "vite.config.ts": "import { defineConfig } from 'vite';\nexport default defineConfig({});",
    "index.html": "<!DOCTYPE html><html><head><title>test-app</title></head><body><div id='root'></div><script type='module' src='/src/main.tsx'></script></body></html>",
    "src/main.tsx": "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport { App } from './App';\nReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);",
    "src/App.tsx": "import { BrowserRouter } from 'react-router-dom';\nimport { AppRoutes } from './routes';\nexport function App() { return <BrowserRouter><AppRoutes /></BrowserRouter>; }",
    "src/index.css": "@tailwind base;\n@tailwind components;\n@tailwind utilities;",
    "tailwind.config.js": "export default { content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'], theme: { extend: {} }, plugins: [] };",
    "postcss.config.js": "export default { plugins: { tailwindcss: {}, autoprefixer: {} } };",
    ".gitignore": "node_modules/\ndist/\n.env\n",
}

ROUTER_LLM_RESPONSE = {
    "src/routes.tsx": 'import { Routes, Route } from \'react-router-dom\';\nimport { HomePage } from \'./pages/homePage\';\nimport { DashboardPage } from \'./pages/dashboardPage\';\nimport { NotFoundPage } from \'./pages/notFoundPage\';\nexport function AppRoutes() { return <Routes><Route path="/" element={<HomePage />} /><Route path="/dashboard" element={<DashboardPage />} /><Route path="*" element={<NotFoundPage />} /></Routes>; }',
    "src/pages/homePage.tsx": "export function HomePage() { return <div>Home</div>; }",
    "src/pages/dashboardPage.tsx": "export function DashboardPage() { return <div>Dashboard</div>; }",
    "src/pages/notFoundPage.tsx": "export function NotFoundPage() { return <div>Not Found</div>; }",
}

COMPONENT_LLM_RESPONSE = {
    "src/components/header.tsx": "export function Header() { return <header>Header</header>; }",
    "src/components/footer.tsx": "export function Footer() { return <footer>Footer</footer>; }",
    "src/components/index.ts": "export { Header } from './header';\nexport { Footer } from './footer';",
    "src/lib/schemas.ts": "import { z } from 'zod';\nexport const UserSchema = z.object({ id: z.string() });",
    "src/types/models.ts": "export interface User { id: string; }",
}

PAGE_LLM_RESPONSE = {
    "src/components/errorBoundary.tsx": "import { Component } from 'react';\nimport type { ReactNode, ErrorInfo } from 'react';\ninterface Props { children: ReactNode; }\ninterface State { hasError: boolean; error: Error | null; }\nexport class ErrorBoundary extends Component<Props, State> {\n  constructor(props: Props) { super(props); this.state = { hasError: false, error: null }; }\n  static getDerivedStateFromError(error: Error): State { return { hasError: true, error }; }\n  componentDidCatch(error: Error, errorInfo: ErrorInfo) { console.error(error, errorInfo); }\n  render() { if (this.state.hasError) return <div>Error</div>; return this.props.children; }\n}",
    "src/pages/homePage.tsx": "import { ErrorBoundary } from '../components/errorBoundary';\nexport function HomePage() { return <ErrorBoundary><div>Home</div></ErrorBoundary>; }",
    "src/pages/dashboardPage.tsx": "import { ErrorBoundary } from '../components/errorBoundary';\nexport function DashboardPage() { return <ErrorBoundary><div>Dashboard</div></ErrorBoundary>; }",
}

API_LLM_RESPONSE = {
    "src/lib/api.ts": "const API_BASE = import.meta.env.VITE_API_URL ?? '';\nfunction authHeaders() { const t = localStorage.getItem('access_token'); return t ? { Authorization: `Bearer ${t}` } : {}; }\nexport async function listUsers() { const res = await fetch(API_BASE + '/api/users', { headers: authHeaders() }); return res.json(); }\nexport async function healthCheck() { const res = await fetch(API_BASE + '/health'); return res.json(); }",
}

DB_LLM_RESPONSE = {
    "src/types/database.ts": "export interface User { id: string; email: string; name: string; created_at: string; }",
    "src/lib/supabase.ts": "import { createClient } from '@supabase/supabase-js';\nconst url = import.meta.env.VITE_SUPABASE_URL;\nconst key = import.meta.env.VITE_SUPABASE_ANON_KEY;\nexport const supabase = createClient(url, key);",
}

AUTH_LLM_RESPONSE = {
    "src/lib/auth.ts": "import { supabase } from './supabase';\nexport async function signIn(e: string, p: string) { return supabase.auth.signInWithPassword({email: e, password: p}); }\nexport async function signUp(e: string, p: string) { return supabase.auth.signUp({email: e, password: p}); }\nexport async function signOut() { return supabase.auth.signOut(); }\nexport async function getSession() { return (await supabase.auth.getSession()).data.session; }\nexport function onAuthStateChange(cb: Function) { return supabase.auth.onAuthStateChange((_e, s) => cb(s)); }",
    "src/hooks/useAuth.ts": "import { useState, useEffect } from 'react';\nimport { getSession, onAuthStateChange } from '../lib/auth';\nexport function useAuth() { const [user, setUser] = useState(null); return { user, loading: false }; }",
    "src/components/protectedRoute.tsx": "import { Navigate } from 'react-router-dom';\nimport { useAuth } from '../hooks/useAuth';\nexport function ProtectedRoute({ children }: { children: React.ReactNode }) { const { user, loading } = useAuth(); if (loading) return <div>Loading</div>; if (!user) return <Navigate to='/login' />; return <>{children}</>; }",
}

STYLE_LLM_RESPONSE = {
    "tailwind.config.js": "export default { content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'], theme: { extend: { colors: { primary: '#6366f1', secondary: '#8b5cf6' } } }, plugins: [] };",
    "src/index.css": "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n:root { --color-primary: #6366f1; --color-bg: #0f172a; }\nbody { background-color: var(--color-bg); color: #f9fafb; }",
}

STYLE_ECOMMERCE_LLM_RESPONSE = {
    "tailwind.config.js": "export default { content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'], theme: { extend: { colors: { primary: '#059669' } } }, plugins: [] };",
    "src/index.css": "@tailwind base;\n@tailwind components;\n@tailwind utilities;\nbody { background-color: #fafafa; }",
}

TEST_LLM_RESPONSE = {
    "vitest.config.ts": "import { defineConfig } from 'vitest/config';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({ plugins: [react()], test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test/setup.ts'] } });",
    "src/test/setup.ts": "import '@testing-library/jest-dom';",
    "src/test/components/header.test.tsx": "import { render, screen } from '@testing-library/react';\nimport { Header } from '../../components/header';\ndescribe('Header', () => { it('renders without crashing', () => { render(<Header />); }); it('displays component content', () => { render(<Header />); expect(document.querySelector('.header')).toBeInTheDocument(); }); });",
    "src/test/pages/homePage.test.tsx": "import { render } from '@testing-library/react';\nimport { MemoryRouter } from 'react-router-dom';\nimport { HomePage } from '../../pages/homePage';\ndescribe('HomePage', () => { it('renders without crashing', () => { render(<MemoryRouter><HomePage /></MemoryRouter>); }); });",
    "src/test/App.test.tsx": "import { render } from '@testing-library/react';\nimport { App } from '../App';\ndescribe('App', () => { it('renders without crashing', () => { render(<App />); }); });",
}

# All mock responses keyed by agent name for graph Stage 6 tests
ALL_LLM_RESPONSES = {
    "scaffold": SCAFFOLD_LLM_RESPONSE,
    "router": ROUTER_LLM_RESPONSE,
    "component": COMPONENT_LLM_RESPONSE,
    "page": PAGE_LLM_RESPONSE,
    "api": API_LLM_RESPONSE,
    "db": DB_LLM_RESPONSE,
    "auth": AUTH_LLM_RESPONSE,
    "style": STYLE_LLM_RESPONSE,
    "test": TEST_LLM_RESPONSE,
}


def _make_llm_mock(response: dict):
    """Create an AsyncMock for _call_llm that returns a fixed response."""
    mock = AsyncMock(return_value=response)
    return mock


# ── Base class ───────────────────────────────────────────────────

class TestBaseBuildAgent:
    def test_temperature_and_seed(self):
        assert TEMPERATURE == 0
        assert SEED == 42

    def test_build_agents_list_has_9(self):
        assert len(BUILD_AGENTS) == 9
        for i, agent in enumerate(BUILD_AGENTS, start=1):
            assert agent.agent_number == i

    def test_review_agent_is_10(self):
        assert REVIEW_AGENT.agent_number == 10
        assert REVIEW_AGENT.name == "review"


# ── Agent 1: Scaffold ───────────────────────────────────────────

class TestScaffoldAgent:
    @pytest.mark.asyncio
    async def test_generates_scaffold_files(self):
        agent = ScaffoldAgent()
        agent._call_llm = _make_llm_mock(SCAFFOLD_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "package.json" in files
        assert "tsconfig.json" in files
        assert "vite.config.ts" in files
        assert "index.html" in files
        assert "src/main.tsx" in files
        assert "src/App.tsx" in files
        assert "src/index.css" in files
        assert ".gitignore" in files
        assert ".env.example" in files

    @pytest.mark.asyncio
    async def test_package_json_valid(self):
        agent = ScaffoldAgent()
        agent._call_llm = _make_llm_mock(SCAFFOLD_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        pkg = json.loads(files["package.json"])
        assert pkg["name"] == "test-app"
        assert "react" in pkg.get("dependencies", {})

    @pytest.mark.asyncio
    async def test_scaffold_uses_app_name(self):
        agent = ScaffoldAgent()
        # Return HTML with app name so assertion passes
        custom_response = dict(SCAFFOLD_LLM_RESPONSE)
        custom_response["index.html"] = "<!DOCTYPE html><html><head><title>my-cool-app</title></head></html>"
        agent._call_llm = _make_llm_mock(custom_response)
        state = _base_state()
        state["idea_spec"]["name"] = "my-cool-app"
        files = await agent.execute(state)

        pkg = json.loads(files["package.json"])
        assert pkg["name"] == "my-cool-app"


# ── Agent 2: Router ──────────────────────────────────────────────

class TestRouterAgent:
    @pytest.mark.asyncio
    async def test_generates_routes(self):
        agent = RouterAgent()
        agent._call_llm = _make_llm_mock(ROUTER_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/routes.tsx" in files
        routes_content = files["src/routes.tsx"]
        assert "AppRoutes" in routes_content

    @pytest.mark.asyncio
    async def test_generates_page_stubs(self):
        agent = RouterAgent()
        agent._call_llm = _make_llm_mock(ROUTER_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/pages/homePage.tsx" in files
        assert "src/pages/dashboardPage.tsx" in files


# ── Agent 3: Component ──────────────────────────────────────────

class TestComponentAgent:
    @pytest.mark.asyncio
    async def test_generates_components(self):
        agent = ComponentAgent()
        agent._call_llm = _make_llm_mock(COMPONENT_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/components/header.tsx" in files
        assert "src/components/footer.tsx" in files
        assert "src/components/index.ts" in files

    @pytest.mark.asyncio
    async def test_barrel_exports(self):
        agent = ComponentAgent()
        agent._call_llm = _make_llm_mock(COMPONENT_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        barrel = files["src/components/index.ts"]
        assert "Header" in barrel
        assert "Footer" in barrel

    @pytest.mark.asyncio
    async def test_injects_zod_schemas(self):
        agent = ComponentAgent()
        agent._call_llm = _make_llm_mock(COMPONENT_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/lib/schemas.ts" in files
        assert "UserSchema" in files["src/lib/schemas.ts"]

    @pytest.mark.asyncio
    async def test_injects_ts_interfaces(self):
        agent = ComponentAgent()
        agent._call_llm = _make_llm_mock(COMPONENT_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/types/models.ts" in files


# ── Agent 4: Page ────────────────────────────────────────────────

class TestPageAgent:
    @pytest.mark.asyncio
    async def test_generates_pages_with_error_boundary(self):
        agent = PageAgent()
        agent._call_llm = _make_llm_mock(PAGE_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/components/errorBoundary.tsx" in files
        assert "src/pages/homePage.tsx" in files

        home_content = files["src/pages/homePage.tsx"]
        assert "ErrorBoundary" in home_content

    @pytest.mark.asyncio
    async def test_error_boundary_component(self):
        agent = PageAgent()
        agent._call_llm = _make_llm_mock(PAGE_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        eb = files["src/components/errorBoundary.tsx"]
        assert "getDerivedStateFromError" in eb
        assert "componentDidCatch" in eb


# ── Agent 5: API ─────────────────────────────────────────────────

class TestAPIAgent:
    @pytest.mark.asyncio
    async def test_generates_api_client(self):
        agent = APIAgent()
        agent._call_llm = _make_llm_mock(API_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/lib/api.ts" in files
        api = files["src/lib/api.ts"]
        assert "listUsers" in api
        assert "authHeaders" in api

    @pytest.mark.asyncio
    async def test_api_with_empty_spec(self):
        agent = APIAgent()
        agent._call_llm = _make_llm_mock(API_LLM_RESPONSE)
        state = _base_state()
        state["spec_outputs"]["openapi_spec"] = {}
        files = await agent.execute(state)

        api = files["src/lib/api.ts"]
        assert "healthCheck" in api


# ── Agent 6: DB ──────────────────────────────────────────────────

class TestDBAgent:
    @pytest.mark.asyncio
    async def test_generates_db_types(self):
        agent = DBAgent()
        agent._call_llm = _make_llm_mock(DB_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/types/database.ts" in files
        assert "src/lib/supabase.ts" in files

    @pytest.mark.asyncio
    async def test_db_uses_model_defs(self):
        agent = DBAgent()
        agent._call_llm = _make_llm_mock(DB_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        db_types = files["src/types/database.ts"]
        assert "User" in db_types

    @pytest.mark.asyncio
    async def test_db_fallback_entities(self):
        agent = DBAgent()
        agent._call_llm = _make_llm_mock(DB_LLM_RESPONSE)
        state = _base_state()
        state["spec_outputs"]["model_defs"] = {}
        files = await agent.execute(state)

        db_types = files["src/types/database.ts"]
        assert "User" in db_types


# ── Agent 7: Auth ────────────────────────────────────────────────

class TestAuthAgent:
    @pytest.mark.asyncio
    async def test_generates_auth_files(self):
        agent = AuthAgent()
        agent._call_llm = _make_llm_mock(AUTH_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "src/lib/auth.ts" in files
        assert "src/hooks/useAuth.ts" in files
        assert "src/components/protectedRoute.tsx" in files

    @pytest.mark.asyncio
    async def test_auth_functions(self):
        agent = AuthAgent()
        agent._call_llm = _make_llm_mock(AUTH_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        auth = files["src/lib/auth.ts"]
        assert "signIn" in auth
        assert "signUp" in auth
        assert "signOut" in auth
        assert "getSession" in auth


# ── Agent 8: Style ───────────────────────────────────────────────

class TestStyleAgent:
    @pytest.mark.asyncio
    async def test_generates_style_files(self):
        agent = StyleAgent()
        agent._call_llm = _make_llm_mock(STYLE_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        assert "tailwind.config.js" in files
        assert "src/index.css" in files

    @pytest.mark.asyncio
    async def test_uses_domain_palette(self):
        agent = StyleAgent()
        agent._call_llm = _make_llm_mock(STYLE_ECOMMERCE_LLM_RESPONSE)
        state = _base_state()
        state["comprehensive_plan"]["domain"] = "ecommerce"
        files = await agent.execute(state)

        tw = files["tailwind.config.js"]
        assert "#059669" in tw

    @pytest.mark.asyncio
    async def test_not_forge_colors(self):
        """Ensure generated apps don't use FORGE's own #04040a background."""
        agent = StyleAgent()
        agent._call_llm = _make_llm_mock(STYLE_LLM_RESPONSE)
        state = _base_state()
        files = await agent.execute(state)

        css = files["src/index.css"]
        assert "#04040a" not in css


# ── Agent 9: Test ────────────────────────────────────────────────

class TestTestAgent:
    @pytest.mark.asyncio
    async def test_generates_vitest_config(self):
        agent = TestAgent()
        agent._call_llm = _make_llm_mock(TEST_LLM_RESPONSE)
        state = _base_state()
        state["generated_files"] = {
            "src/components/header.tsx": "export function Header() {}",
            "src/pages/homePage.tsx": "export function HomePage() {}",
        }
        files = await agent.execute(state)

        assert "vitest.config.ts" in files
        assert "src/test/setup.ts" in files

    @pytest.mark.asyncio
    async def test_generates_component_tests(self):
        agent = TestAgent()
        agent._call_llm = _make_llm_mock(TEST_LLM_RESPONSE)
        state = _base_state()
        state["generated_files"] = {
            "src/components/header.tsx": "export function Header() {}",
        }
        files = await agent.execute(state)

        assert "src/test/components/header.test.tsx" in files
        test = files["src/test/components/header.test.tsx"]
        assert "Header" in test
        assert "renders without crashing" in test

    @pytest.mark.asyncio
    async def test_generates_page_tests(self):
        agent = TestAgent()
        agent._call_llm = _make_llm_mock(TEST_LLM_RESPONSE)
        state = _base_state()
        state["generated_files"] = {
            "src/pages/homePage.tsx": "export function HomePage() {}",
        }
        files = await agent.execute(state)

        assert "src/test/pages/homePage.test.tsx" in files

    @pytest.mark.asyncio
    async def test_app_integration_test(self):
        agent = TestAgent()
        agent._call_llm = _make_llm_mock(TEST_LLM_RESPONSE)
        state = _base_state()
        state["generated_files"] = {}
        files = await agent.execute(state)

        assert "src/test/App.test.tsx" in files


# ── Agent 10: Review ─────────────────────────────────────────────

class TestReviewAgent:
    @pytest.mark.asyncio
    async def test_review_returns_report(self):
        agent = ReviewAgent()
        state = _base_state()
        state["generated_files"] = {"src/App.tsx": "export function App() {}"}

        report = await agent.review(state)
        assert "passed" in report
        assert "gates" in report
        assert "coherence" in report
        assert "barrels" in report
        assert "seams" in report

    @pytest.mark.asyncio
    async def test_review_execute_returns_empty(self):
        agent = ReviewAgent()
        state = _base_state()
        files = await agent.execute(state)
        assert files == {}

    @pytest.mark.asyncio
    async def test_review_gates_present(self):
        agent = ReviewAgent()
        state = _base_state()
        state["generated_files"] = {"src/App.tsx": "export function App() {}"}

        report = await agent.review(state)
        assert "g7" in report["gates"]
        assert "g8" in report["gates"]
        assert "g11" in report["gates"]
        assert "g12" in report["gates"]


# ── Hotfix Agent ─────────────────────────────────────────────────

class TestHotfixAgent:
    @pytest.mark.asyncio
    async def test_hotfix_returns_not_applied_when_no_file(self):
        result = await apply_hotfix(
            _base_state(), agent_number=1, gate_result={"passed": False, "reason": "test"}
        )
        assert isinstance(result, HotfixResult)
        assert result.applied is False
        assert result.description == "could_not_identify_failing_file"

    @pytest.mark.asyncio
    async def test_hotfix_agent_class(self):
        agent = HotfixAgent()
        result = await agent.execute(
            _base_state(), agent_number=3, gate_result={"passed": False, "reason": "test"}
        )
        assert isinstance(result, HotfixResult)
        assert result.agent_number == 3


# ── Snapshot Service ─────────────────────────────────────────────

class TestSnapshotService:
    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.redis_client", None)
    @patch("app.services.snapshot_service.get_write_session")
    @patch("app.services.snapshot_service.upload_file", new_callable=AsyncMock)
    async def test_capture_snapshot(self, mock_upload, mock_write_session):
        from app.services.snapshot_service import capture_snapshot

        mock_upload.return_value = "https://example.com/snapshot.webp"

        # Mock write session context manager
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        async def _flush():
            pass
        mock_session.flush = _flush
        mock_session.add = lambda x: setattr(x, 'id', uuid.uuid4())
        mock_write_session.return_value = mock_session

        build_id = uuid.uuid4()
        project_id = uuid.uuid4()
        files = {"src/App.tsx": "export function App() {}"}

        result = await capture_snapshot(
            build_id=build_id,
            project_id=project_id,
            agent_number=1,
            agent_type="scaffold",
            generated_files=files,
        )

        assert result["screenshot_url"] == "https://example.com/snapshot.webp"
        assert "storage_key" in result
        assert "snapshot_id" in result
        mock_upload.assert_called_once()

        call_kwargs = mock_upload.call_args
        payload = call_kwargs.kwargs.get("content") or call_kwargs[1].get("content") or call_kwargs[0][2]
        parsed = json.loads(payload)
        assert parsed["agent_number"] == 1
        assert parsed["agent_type"] == "scaffold"
        assert parsed["file_count"] == 1


# ── Graph Stage 6 Integration ───────────────────────────────────

@asynccontextmanager
async def _mock_write_session():
    """Async context manager mock for get_write_session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    yield session


def _agent_llm_side_effect(agent_name: str):
    """Return the mock LLM response for a given agent name."""
    return ALL_LLM_RESPONSES.get(agent_name, {})


class TestGraphStage6:
    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.get_write_session", side_effect=lambda: _mock_write_session())
    @patch("app.agents.graph.redis_client", None)
    async def test_build_runs_all_agents(self, mock_ws, mock_snapshot, mock_upload):
        from app.agents.graph import build
        from app.agents.build import BUILD_AGENTS as agents

        # Mock _call_llm on every build agent
        for agent in agents:
            agent._call_llm = _make_llm_mock(_agent_llm_side_effect(agent.name))

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        result = await build(state)

        assert result["current_stage"] == 6
        assert len(result["generated_files"]) > 0
        # Should have snapshot calls: 9 agents + 1 review = 10
        assert mock_snapshot.call_count == 10

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.get_write_session", side_effect=lambda: _mock_write_session())
    @patch("app.agents.graph.redis_client", None)
    async def test_build_generates_expected_files(self, mock_ws, mock_snapshot, mock_upload):
        from app.agents.graph import build
        from app.agents.build import BUILD_AGENTS as agents

        for agent in agents:
            agent._call_llm = _make_llm_mock(_agent_llm_side_effect(agent.name))

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        result = await build(state)

        files = result["generated_files"]
        assert "package.json" in files
        assert "src/main.tsx" in files
        assert "src/routes.tsx" in files
        assert "src/components/index.ts" in files
        assert "src/lib/auth.ts" in files
        assert "tailwind.config.js" in files

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.get_write_session", side_effect=lambda: _mock_write_session())
    @patch("app.agents.graph.redis_client", None)
    async def test_build_g7_gates_recorded(self, mock_ws, mock_snapshot, mock_upload):
        from app.agents.graph import build
        from app.agents.build import BUILD_AGENTS as agents

        for agent in agents:
            agent._call_llm = _make_llm_mock(_agent_llm_side_effect(agent.name))

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        result = await build(state)

        for i in range(1, 10):
            key = f"g7_agent_{i}"
            assert key in result["gate_results"], f"Missing {key}"
            assert result["gate_results"][key]["passed"]

        assert "review" in result["gate_results"]

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.get_write_session", side_effect=lambda: _mock_write_session())
    @patch("app.agents.graph.redis_client", None)
    async def test_build_stores_to_supabase(self, mock_ws, mock_snapshot, mock_upload):
        from app.agents.graph import build
        from app.agents.build import BUILD_AGENTS as agents

        for agent in agents:
            agent._call_llm = _make_llm_mock(_agent_llm_side_effect(agent.name))

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        await build(state)

        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs.get("bucket") == "forge-projects"

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.get_write_session", side_effect=lambda: _mock_write_session())
    @patch("app.agents.graph.redis_client", None)
    async def test_build_sequential_order(self, mock_ws, mock_snapshot, mock_upload):
        """Verify agents run in correct order 1-9 then review."""
        from app.agents.graph import build
        from app.agents.build import BUILD_AGENTS as agents

        for agent in agents:
            agent._call_llm = _make_llm_mock(_agent_llm_side_effect(agent.name))

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        await build(state)

        agent_numbers = [
            call.kwargs.get("agent_number") or call[1].get("agent_number")
            for call in mock_snapshot.call_args_list
        ]
        assert agent_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
