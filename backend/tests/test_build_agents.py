"""Tests for build agents, snapshot service, hotfix agent, and graph Stage 6."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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
        state = _base_state()
        files = await agent.execute(state)

        pkg = json.loads(files["package.json"])
        assert pkg["name"] == "test-app"
        assert "react" in pkg.get("dependencies", {})

    @pytest.mark.asyncio
    async def test_scaffold_uses_app_name(self):
        agent = ScaffoldAgent()
        state = _base_state()
        state["idea_spec"]["name"] = "my-cool-app"
        files = await agent.execute(state)

        assert "my-cool-app" in files["index.html"]
        pkg = json.loads(files["package.json"])
        assert pkg["name"] == "my-cool-app"


# ── Agent 2: Router ──────────────────────────────────────────────

class TestRouterAgent:
    @pytest.mark.asyncio
    async def test_generates_routes(self):
        agent = RouterAgent()
        state = _base_state()
        files = await agent.execute(state)

        assert "src/routes.tsx" in files
        routes_content = files["src/routes.tsx"]
        assert "AppRoutes" in routes_content
        assert 'path="/"' in routes_content
        assert 'path="/dashboard"' in routes_content

    @pytest.mark.asyncio
    async def test_generates_page_stubs(self):
        agent = RouterAgent()
        state = _base_state()
        files = await agent.execute(state)

        assert "src/pages/homePage.tsx" in files
        assert "src/pages/dashboardPage.tsx" in files


# ── Agent 3: Component ──────────────────────────────────────────

class TestComponentAgent:
    @pytest.mark.asyncio
    async def test_generates_components(self):
        agent = ComponentAgent()
        state = _base_state()
        files = await agent.execute(state)

        assert "src/components/header.tsx" in files
        assert "src/components/footer.tsx" in files
        assert "src/components/index.ts" in files

    @pytest.mark.asyncio
    async def test_barrel_exports(self):
        agent = ComponentAgent()
        state = _base_state()
        files = await agent.execute(state)

        barrel = files["src/components/index.ts"]
        assert "export { Header }" in barrel
        assert "export { Footer }" in barrel

    @pytest.mark.asyncio
    async def test_injects_zod_schemas(self):
        agent = ComponentAgent()
        state = _base_state()
        files = await agent.execute(state)

        assert "src/lib/schemas.ts" in files
        assert "UserSchema" in files["src/lib/schemas.ts"]

    @pytest.mark.asyncio
    async def test_injects_ts_interfaces(self):
        agent = ComponentAgent()
        state = _base_state()
        files = await agent.execute(state)

        assert "src/types/models.ts" in files


# ── Agent 4: Page ────────────────────────────────────────────────

class TestPageAgent:
    @pytest.mark.asyncio
    async def test_generates_pages_with_error_boundary(self):
        agent = PageAgent()
        state = _base_state()
        files = await agent.execute(state)

        assert "src/components/errorBoundary.tsx" in files
        assert "src/pages/homePage.tsx" in files

        home_content = files["src/pages/homePage.tsx"]
        assert "ErrorBoundary" in home_content

    @pytest.mark.asyncio
    async def test_error_boundary_component(self):
        agent = PageAgent()
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
        state = _base_state()
        files = await agent.execute(state)

        assert "src/lib/api.ts" in files
        api = files["src/lib/api.ts"]
        assert "listUsers" in api
        assert "authHeaders" in api

    @pytest.mark.asyncio
    async def test_api_with_empty_spec(self):
        agent = APIAgent()
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
        state = _base_state()
        files = await agent.execute(state)

        assert "src/types/database.ts" in files
        assert "src/lib/supabase.ts" in files

    @pytest.mark.asyncio
    async def test_db_uses_model_defs(self):
        agent = DBAgent()
        state = _base_state()
        files = await agent.execute(state)

        db_types = files["src/types/database.ts"]
        assert "User" in db_types

    @pytest.mark.asyncio
    async def test_db_fallback_entities(self):
        agent = DBAgent()
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
        state = _base_state()
        files = await agent.execute(state)

        assert "src/lib/auth.ts" in files
        assert "src/hooks/useAuth.ts" in files
        assert "src/components/protectedRoute.tsx" in files

    @pytest.mark.asyncio
    async def test_auth_functions(self):
        agent = AuthAgent()
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
        state = _base_state()
        files = await agent.execute(state)

        assert "tailwind.config.js" in files
        assert "src/index.css" in files

    @pytest.mark.asyncio
    async def test_uses_domain_palette(self):
        agent = StyleAgent()
        state = _base_state()
        state["comprehensive_plan"]["domain"] = "ecommerce"
        files = await agent.execute(state)

        tw = files["tailwind.config.js"]
        # ecommerce palette has green primary
        assert "#059669" in tw

    @pytest.mark.asyncio
    async def test_not_forge_colors(self):
        """Ensure generated apps don't use FORGE's own #04040a background."""
        agent = StyleAgent()
        state = _base_state()
        files = await agent.execute(state)

        css = files["src/index.css"]
        assert "#04040a" not in css


# ── Agent 9: Test ────────────────────────────────────────────────

class TestTestAgent:
    @pytest.mark.asyncio
    async def test_generates_vitest_config(self):
        agent = TestAgent()
        state = _base_state()
        # Need some generated files for test agent to discover
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
        state = _base_state()
        state["generated_files"] = {
            "src/pages/homePage.tsx": "export function HomePage() {}",
        }
        files = await agent.execute(state)

        assert "src/test/pages/homePage.test.tsx" in files

    @pytest.mark.asyncio
    async def test_app_integration_test(self):
        agent = TestAgent()
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
    @patch("app.services.snapshot_service.upload_file", new_callable=AsyncMock)
    async def test_capture_snapshot(self, mock_upload):
        from app.services.snapshot_service import capture_snapshot

        mock_upload.return_value = "https://example.com/snapshot.json"

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

        assert result["url"] == "https://example.com/snapshot.json"
        assert "storage_key" in result
        mock_upload.assert_called_once()

        # Verify the payload is valid JSON
        call_kwargs = mock_upload.call_args
        payload = call_kwargs.kwargs.get("content") or call_kwargs[1].get("content") or call_kwargs[0][2]
        parsed = json.loads(payload)
        assert parsed["agent_number"] == 1
        assert parsed["agent_type"] == "scaffold"
        assert parsed["file_count"] == 1


# ── Graph Stage 6 Integration ───────────────────────────────────

class TestGraphStage6:
    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.redis_client", None)
    async def test_build_runs_all_agents(self, mock_snapshot, mock_upload):
        from app.agents.graph import build

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        result = await build(state)

        assert result["current_stage"] == 6
        assert len(result["generated_files"]) > 0
        # Should have snapshot calls: 9 agents + 1 review = 10
        assert mock_snapshot.call_count == 10
        # Should upload final build to storage
        mock_upload.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.redis_client", None)
    async def test_build_generates_expected_files(self, mock_snapshot, mock_upload):
        from app.agents.graph import build

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        result = await build(state)

        files = result["generated_files"]
        # Scaffold files
        assert "package.json" in files
        assert "src/main.tsx" in files
        # Router files
        assert "src/routes.tsx" in files
        # Component files
        assert "src/components/index.ts" in files
        # Auth files
        assert "src/lib/auth.ts" in files
        # Style files
        assert "tailwind.config.js" in files

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.redis_client", None)
    async def test_build_g7_gates_recorded(self, mock_snapshot, mock_upload):
        from app.agents.graph import build

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        result = await build(state)

        # G7 gates for agents 1-9
        for i in range(1, 10):
            key = f"g7_agent_{i}"
            assert key in result["gate_results"], f"Missing {key}"
            assert result["gate_results"][key]["passed"]

        # Review report
        assert "review" in result["gate_results"]

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.redis_client", None)
    async def test_build_stores_to_supabase(self, mock_snapshot, mock_upload):
        from app.agents.graph import build

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        await build(state)

        # Verify upload was called with correct bucket
        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs.get("bucket") == "forge-projects"

    @pytest.mark.asyncio
    @patch("app.agents.graph.upload_file", new_callable=AsyncMock)
    @patch("app.agents.graph.capture_snapshot", new_callable=AsyncMock)
    @patch("app.agents.graph.redis_client", None)
    async def test_build_sequential_order(self, mock_snapshot, mock_upload):
        """Verify agents run in correct order 1-9 then review."""
        from app.agents.graph import build

        mock_snapshot.return_value = {"storage_key": "test", "url": "https://example.com"}
        mock_upload.return_value = "https://example.com/build.json"

        state = _base_state()
        await build(state)

        # Check snapshot calls were in order
        agent_numbers = [
            call.kwargs.get("agent_number") or call[1].get("agent_number")
            for call in mock_snapshot.call_args_list
        ]
        assert agent_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
