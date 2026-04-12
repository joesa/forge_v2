"""Tests for Reliability Layers 3, 5, and 6."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Layer 3: Static Analysis ────────────────────────────────────

from app.reliability.layer3_static.ast_analyser import (
    ASTIssue,
    analyse_file,
    analyse_files,
)
from app.reliability.layer3_static.import_graph_resolver import (
    resolve_import_graph,
)
from app.reliability.layer3_static.runtime_error_predictor import (
    RUNTIME_PATTERNS,
    PredictedError,
    predict_runtime_errors,
)

# ── Layer 5: Contracts ──────────────────────────────────────────

from app.reliability.layer5_contracts.pattern_library import (
    PATTERNS,
    Pattern,
    get_pattern,
    get_patterns_by_category,
    get_patterns_by_tag,
    list_pattern_names,
)
from app.reliability.layer5_contracts.api_contract_validator import (
    ContractViolation,
    validate_api_contracts,
)
from app.reliability.layer5_contracts.type_inference_engine import (
    TypeMapping,
    infer_model_types,
    infer_type,
    validate_type_consistency,
)

# ── Layer 6: Intelligence ───────────────────────────────────────

from app.reliability.layer6_intelligence.build_cache import (
    CacheResult,
    SIMILARITY_THRESHOLD,
    check_cache,
    store_in_cache,
)
from app.reliability.layer6_intelligence.build_memory import (
    BuildMemory,
    BuildRecord,
)
from app.reliability.layer6_intelligence.error_boundary_injector import (
    ERROR_BOUNDARY_COMPONENT,
    inject_error_boundaries,
)
from app.reliability.layer6_intelligence.incremental_build import (
    IncrementalBuildTracker,
    compute_file_hash,
)


# ═══════════════════════════════════════════════════════════════════
# LAYER 3 — STATIC ANALYSIS
# ═══════════════════════════════════════════════════════════════════


class TestASTAnalyser:
    def test_detects_null_reference(self):
        code = "const user: User | null = null;\nconst name = user.name;"
        issues = analyse_file("app.tsx", code)
        assert any(i.code == "NULL_REF" for i in issues)

    def test_detects_unhandled_async(self):
        code = "async function fetchData() {\n  const res = await fetch('/api');\n}"
        issues = analyse_file("api.ts", code)
        # async without try/catch
        assert any(i.code == "UNHANDLED_ASYNC" for i in issues)

    def test_detects_missing_error_boundary(self):
        code = """
import React from 'react';
export default function App() {
  return (<div><ChildComponent /></div>);
}
"""
        issues = analyse_file("src/pages/App.tsx", code)
        # Page without ErrorBoundary
        assert any(i.code == "MISSING_ERROR_BOUNDARY" for i in issues)

    def test_detects_useeffect_without_cleanup(self):
        code = "useEffect(() => { const sub = subscribe(); window.addEventListener('resize', handler); },"
        issues = analyse_file("hook.ts", code)
        assert any(i.code == "EFFECT_NO_CLEANUP" for i in issues)

    def test_detects_untyped_state(self):
        code = "const [data, setData] = useState();"
        issues = analyse_file("comp.tsx", code)
        assert any(i.code == "UNTYPED_STATE" for i in issues)

    def test_clean_code_passes(self):
        code = """
import { ErrorBoundary } from './ErrorBoundary';

export default function Page() {
  return <ErrorBoundary><div>Clean</div></ErrorBoundary>;
}
"""
        issues = analyse_file("clean.tsx", code)
        # May have warnings but no errors
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) == 0

    def test_analyse_files_returns_dict(self):
        files = {
            "app.tsx": "const x = data.value;",
            "util.ts": "export const sum = (a: number, b: number) => a + b;",
        }
        result = analyse_files(files)
        assert "passed" in result
        assert "total_issues" in result
        assert "issues" in result
        assert isinstance(result["issues"], list)


class TestImportGraphResolver:
    def test_resolves_clean_imports(self):
        files = {
            "src/App.tsx": "import { Header } from './components/Header';",
            "src/components/Header.tsx": "export function Header() { return <header />; }",
        }
        result = resolve_import_graph(files)
        assert result["passed"] is True
        assert len(result["circular_imports"]) == 0

    def test_detects_circular_imports(self):
        files = {
            "src/a.ts": "import { b } from './b';",
            "src/b.ts": "import { a } from './a';",
        }
        result = resolve_import_graph(files)
        assert result["passed"] is False
        assert len(result["circular_imports"]) > 0

    def test_detects_missing_imports(self):
        files = {
            "src/App.tsx": "import { Missing } from './Missing';",
        }
        result = resolve_import_graph(files)
        assert len(result["missing_imports"]) > 0

    def test_ignores_external_packages(self):
        files = {
            "src/App.tsx": "import React from 'react';\nimport { create } from 'zustand';",
        }
        result = resolve_import_graph(files)
        # External packages should not appear in missing_imports
        assert not any("react" in m.get("module", "") for m in result["missing_imports"])

    def test_detects_duplicate_packages(self):
        files = {
            "package.json": json.dumps({
                "dependencies": {"lodash": "4.17.21"},
                "devDependencies": {"lodash": "4.17.21"},
            }),
        }
        result = resolve_import_graph(files)
        assert len(result["duplicate_packages"]) > 0


class TestRuntimeErrorPredictor:
    def test_has_patterns(self):
        assert len(RUNTIME_PATTERNS) >= 10

    def test_detects_missing_key_prop(self):
        code = "{items.map(item => (<div>{item.name}</div>))}"
        files = {"List.tsx": code}
        result = predict_runtime_errors(files)
        assert any(
            p["pattern_name"] == "missing_key_prop"
            for p in result["predictions"]
        )

    def test_detects_hooks_conditional(self):
        code = "if (isLoggedIn) { const [user, setUser] = useState(null); }"
        files = {"Hook.tsx": code}
        result = predict_runtime_errors(files)
        assert any(
            p["pattern_name"] == "hooks_conditional"
            for p in result["predictions"]
        )

    def test_detects_direct_state_mutation(self):
        code = "items.push(newItem);"
        files = {"mutate.ts": code}
        result = predict_runtime_errors(files)
        assert any(
            p["pattern_name"] == "direct_state_mutation"
            for p in result["predictions"]
        )

    def test_detects_innerhtml_xss(self):
        code = '<div dangerouslySetInnerHTML={{ __html: userInput }} />'
        files = {"page.tsx": code}
        result = predict_runtime_errors(files)
        assert any(
            p["pattern_name"] == "innerhtml_xss"
            for p in result["predictions"]
        )

    def test_detects_json_parse_unguarded(self):
        code = "const data = JSON.parse(raw);"
        files = {"parse.ts": code}
        result = predict_runtime_errors(files)
        assert any(
            p["pattern_name"] == "json_parse_unguarded"
            for p in result["predictions"]
        )

    def test_clean_code_passes(self):
        code = "export const add = (a: number, b: number) => a + b;"
        files = {"util.ts": code}
        result = predict_runtime_errors(files)
        assert result["passed"] is True

    def test_result_structure(self):
        files = {"x.ts": "const x = 1;"}
        result = predict_runtime_errors(files)
        assert "passed" in result
        assert "total_predictions" in result
        assert "errors" in result
        assert "warnings" in result
        assert "predictions" in result


# ═══════════════════════════════════════════════════════════════════
# LAYER 5 — CONTRACTS
# ═══════════════════════════════════════════════════════════════════


class TestPatternLibrary:
    def test_has_30_plus_patterns(self):
        assert len(PATTERNS) >= 30

    def test_pattern_has_required_fields(self):
        for name, pattern in PATTERNS.items():
            assert pattern.name == name
            assert pattern.description
            assert pattern.category
            assert pattern.implementation_template
            assert pattern.test_template

    def test_get_pattern(self):
        p = get_pattern("auth_jwt")
        assert p is not None
        assert p.name == "auth_jwt"
        assert p.category == "auth"

    def test_get_pattern_missing(self):
        p = get_pattern("nonexistent_pattern")
        assert p is None

    def test_get_patterns_by_category(self):
        auth_patterns = get_patterns_by_category("auth")
        assert len(auth_patterns) >= 2
        assert all(p.category == "auth" for p in auth_patterns)

    def test_get_patterns_by_tag(self):
        supabase_patterns = get_patterns_by_tag("supabase")
        assert len(supabase_patterns) >= 3
        assert all("supabase" in p.tags for p in supabase_patterns)

    def test_list_pattern_names(self):
        names = list_pattern_names()
        assert len(names) >= 30
        assert names == sorted(names)  # Sorted alphabetically

    def test_pattern_categories_exist(self):
        categories = {p.category for p in PATTERNS.values()}
        assert "auth" in categories
        assert "ui" in categories
        assert "state" in categories
        assert "data" in categories

    def test_implementation_template_not_empty(self):
        for p in PATTERNS.values():
            assert len(p.implementation_template) > 20

    def test_test_template_not_empty(self):
        for p in PATTERNS.values():
            assert len(p.test_template) > 20


class TestAPIContractValidator:
    def test_empty_spec_passes(self):
        result = validate_api_contracts({}, {})
        assert result["passed"] is True

    def test_missing_route_detected(self):
        spec = {
            "paths": {
                "/api/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "OK"}},
                    },
                },
            },
        }
        files = {}  # No route files
        result = validate_api_contracts(spec, files)
        assert result["passed"] is False
        assert any(
            v["violation_type"] == "MISSING_ROUTE"
            for v in result["violations"]
        )

    def test_implemented_route_passes(self):
        spec = {
            "paths": {
                "/api/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "OK"}},
                    },
                },
            },
        }
        files = {
            "src/routes/api.ts": "router.get('/api/users', async (req, res) => { res.json([]); });",
        }
        result = validate_api_contracts(spec, files)
        assert result["passed"] is True

    def test_extra_route_warning(self):
        spec = {"paths": {"/api/users": {"get": {"responses": {"200": {}}}}}}
        files = {
            "src/routes/api.ts": "router.get('/api/users', async (req, res) => {});\nrouter.get('/api/extra', async (req, res) => {});",
        }
        result = validate_api_contracts(spec, files)
        assert any(
            v["violation_type"] == "EXTRA_ROUTE"
            for v in result["violations"]
        )

    def test_result_structure(self):
        result = validate_api_contracts({"paths": {}}, {})
        assert "passed" in result
        assert "total_violations" in result
        assert "errors" in result
        assert "warnings" in result
        assert "violations" in result


class TestTypeInferenceEngine:
    def test_str_to_ts(self):
        m = infer_type("str")
        assert m.typescript_type == "string"
        assert m.nullable is False

    def test_int_to_ts(self):
        m = infer_type("int")
        assert m.typescript_type == "number"

    def test_bool_to_ts(self):
        m = infer_type("bool")
        assert m.typescript_type == "boolean"

    def test_optional_str_to_ts(self):
        """CRITICAL: Optional[str] → string | null"""
        m = infer_type("Optional[str]")
        assert m.typescript_type == "string | null"
        assert m.nullable is True

    def test_union_none_to_ts(self):
        """X | None → X | null"""
        m = infer_type("str | None")
        assert m.typescript_type == "string | null"
        assert m.nullable is True

    def test_optional_zod(self):
        m = infer_type("Optional[str]")
        assert ".nullable()" in m.zod_type

    def test_optional_openapi(self):
        m = infer_type("Optional[str]")
        assert m.openapi_schema.get("nullable") is True

    def test_list_type(self):
        m = infer_type("list[str]")
        assert m.typescript_type == "string[]"
        assert "z.array" in m.zod_type

    def test_dict_type(self):
        m = infer_type("dict[str, int]")
        assert "Record<string, number>" in m.typescript_type

    def test_nested_optional_list(self):
        m = infer_type("Optional[list[str]]")
        assert "| null" in m.typescript_type
        assert m.nullable is True

    def test_infer_model_types(self):
        models = [
            {
                "name": "User",
                "fields": [
                    {"name": "id", "type": "uuid", "required": True},
                    {"name": "email", "type": "str", "required": True},
                    {"name": "bio", "type": "str", "required": False},
                ],
            },
        ]
        result = infer_model_types(models)
        assert len(result) == 1
        assert result[0]["name"] == "User"

        fields = result[0]["fields"]
        id_field = next(f for f in fields if f["name"] == "id")
        assert id_field["ts_type"] == "string"

        bio_field = next(f for f in fields if f["name"] == "bio")
        assert "| null" in bio_field["ts_type"]
        assert bio_field["nullable"] is True

    def test_validate_type_consistency_match(self):
        models = [
            {
                "name": "Item",
                "fields": [
                    {"name": "id", "type": "uuid", "required": True},
                    {"name": "title", "type": "str", "required": True},
                ],
            }
        ]
        files = {
            "src/types.ts": """
export interface Item {
  id: string;
  title: string;
}
""",
        }
        result = validate_type_consistency(models, files)
        assert result["passed"] is True

    def test_validate_type_consistency_mismatch(self):
        models = [
            {
                "name": "Item",
                "fields": [
                    {"name": "id", "type": "uuid", "required": True},
                    {"name": "count", "type": "int", "required": True},
                ],
            }
        ]
        files = {
            "src/types.ts": """
export interface Item {
  id: string;
  count: string;
}
""",
        }
        result = validate_type_consistency(models, files)
        assert result["passed"] is False
        assert result["total_mismatches"] > 0


# ═══════════════════════════════════════════════════════════════════
# LAYER 6 — INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════


class TestBuildCache:
    @pytest.mark.asyncio
    async def test_check_cache_no_config(self):
        result = await check_cache({"idea": "todo app"})
        assert result is None

    @pytest.mark.asyncio
    async def test_check_cache_hit(self):
        mock_index = MagicMock()
        mock_index.query.return_value = {
            "matches": [
                {
                    "score": 0.95,
                    "metadata": {
                        "build_id": "abc-123",
                        "files": '{"src/App.tsx": "code"}',
                    },
                }
            ]
        }
        mock_embed = AsyncMock(return_value=[0.1] * 1536)

        result = await check_cache(
            {"idea": "todo app"},
            pinecone_index=mock_index,
            embedding_fn=mock_embed,
        )
        assert result is not None
        assert result.build_id == "abc-123"
        assert result.similarity == 0.95
        assert "src/App.tsx" in result.files

    @pytest.mark.asyncio
    async def test_check_cache_miss(self):
        mock_index = MagicMock()
        mock_index.query.return_value = {
            "matches": [{"score": 0.5, "metadata": {}}]
        }
        mock_embed = AsyncMock(return_value=[0.1] * 1536)

        result = await check_cache(
            {"idea": "unique app"},
            pinecone_index=mock_index,
            embedding_fn=mock_embed,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_store_requires_all_gates_passed(self):
        mock_index = MagicMock()
        mock_embed = AsyncMock(return_value=[0.1] * 1536)

        stored = await store_in_cache(
            idea_spec={"idea": "test"},
            build_id="abc",
            files={"app.tsx": "code"},
            all_gates_passed=False,
            pinecone_index=mock_index,
            embedding_fn=mock_embed,
        )
        assert stored is False
        mock_index.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_success(self):
        mock_index = MagicMock()
        mock_embed = AsyncMock(return_value=[0.1] * 1536)

        stored = await store_in_cache(
            idea_spec={"idea": "test"},
            build_id="abc-123",
            files={"app.tsx": "code"},
            all_gates_passed=True,
            pinecone_index=mock_index,
            embedding_fn=mock_embed,
        )
        assert stored is True
        mock_index.upsert.assert_called_once()

    def test_similarity_threshold(self):
        assert SIMILARITY_THRESHOLD == 0.92


class TestBuildMemory:
    def test_record_build(self):
        memory = BuildMemory()
        record = memory.record_build(
            build_id="build-1",
            idea_summary="A todo app",
            tech_stack=["react", "supabase"],
            files={"app.tsx": "code"},
            gate_results={"G1": True, "G2": True},
            patterns_used=["auth_jwt", "supabase_crud"],
        )
        assert record.build_id == "build-1"
        assert record.success is True

    def test_get_successful_builds(self):
        memory = BuildMemory()
        memory.record_build("b1", "app1", ["react"], {"a.ts": "x"}, {"G1": True})
        memory.record_build("b2", "app2", ["react"], {"a.ts": "x"}, {"G1": False})
        assert len(memory.get_successful_builds()) == 1

    def test_get_builds_by_tech(self):
        memory = BuildMemory()
        memory.record_build("b1", "app1", ["react", "supabase"], {"a.ts": "x"}, {"G1": True})
        memory.record_build("b2", "app2", ["vue"], {"a.ts": "x"}, {"G1": True})
        assert len(memory.get_builds_by_tech("react")) == 1
        assert len(memory.get_builds_by_tech("vue")) == 1

    def test_get_common_patterns(self):
        memory = BuildMemory()
        memory.record_build("b1", "a1", ["react"], {"a": "x"}, {"G1": True}, ["auth_jwt", "crud"])
        memory.record_build("b2", "a2", ["react"], {"a": "x"}, {"G1": True}, ["auth_jwt", "form"])
        common = memory.get_common_patterns(min_count=2)
        assert any(p[0] == "auth_jwt" for p in common)

    def test_suggest_patterns(self):
        memory = BuildMemory()
        memory.record_build("b1", "a1", ["react"], {"a": "x"}, {"G1": True}, ["auth_jwt", "crud"])
        suggestions = memory.suggest_patterns(["react"])
        assert "auth_jwt" in suggestions

    def test_get_failure_patterns(self):
        memory = BuildMemory()
        memory.record_build("b1", "failed app", ["react"], {"a": "x"}, {"G1": True, "G5": False})
        failures = memory.get_failure_patterns()
        assert len(failures) == 1
        assert "G5" in failures[0]["failed_gates"]

    def test_stats(self):
        memory = BuildMemory()
        memory.record_build("b1", "a1", ["react"], {"a": "x"}, {"G1": True})
        stats = memory.get_stats()
        assert stats["total_builds"] == 1
        assert stats["successful_builds"] == 1

    def test_serialization(self):
        memory = BuildMemory()
        memory.record_build("b1", "a1", ["react"], {"a.ts": "x"}, {"G1": True}, ["auth_jwt"])
        json_str = memory.to_json()
        restored = BuildMemory.from_json(json_str)
        assert len(restored.get_successful_builds()) == 1


class TestErrorBoundaryInjector:
    def test_injects_into_pages(self):
        files = {
            "src/pages/Home.tsx": """
import React from 'react';

export default function Home() {
  return <div>Hello</div>;
}
""",
            "src/components/Button.tsx": "export function Button() { return <button />; }",
        }
        result = inject_error_boundaries(files)
        assert result["injected_count"] >= 1
        assert "src/pages/Home.tsx" in result["pages_wrapped"]
        # ErrorBoundary component should be added
        assert result["error_boundary_file"] in result["files"]

    def test_skips_already_wrapped(self):
        files = {
            "src/pages/Home.tsx": """
import { ErrorBoundary } from '../components/ErrorBoundary';

export default function Home() {
  return <ErrorBoundary><div>Hello</div></ErrorBoundary>;
}
""",
        }
        result = inject_error_boundaries(files)
        assert result["injected_count"] == 0

    def test_skips_non_page_files(self):
        files = {
            "src/utils/helper.ts": "export const sum = (a: number, b: number) => a + b;",
        }
        result = inject_error_boundaries(files)
        assert result["injected_count"] == 0

    def test_handles_const_export(self):
        files = {
            "src/pages/About.tsx": """
import React from 'react';

const About = () => {
  return <div>About</div>;
};

export default About;
""",
        }
        result = inject_error_boundaries(files)
        assert result["injected_count"] == 1
        content = result["files"]["src/pages/About.tsx"]
        assert "ErrorBoundary" in content

    def test_error_boundary_component_content(self):
        assert "getDerivedStateFromError" in ERROR_BOUNDARY_COMPONENT
        assert "componentDidCatch" in ERROR_BOUNDARY_COMPONENT
        assert "Try Again" in ERROR_BOUNDARY_COMPONENT


class TestIncrementalBuild:
    def test_first_build_all_new(self):
        tracker = IncrementalBuildTracker()
        files = {"a.ts": "const x = 1;", "b.ts": "const y = 2;"}
        result = tracker.compare(files)
        assert len(result.new_files) == 2
        assert len(result.changed_files) == 0
        assert result.total_files == 2

    def test_unchanged_files_detected(self):
        tracker = IncrementalBuildTracker()
        files = {"a.ts": "const x = 1;", "b.ts": "const y = 2;"}
        tracker.update(files)

        result = tracker.compare(files)
        assert len(result.unchanged_files) == 2
        assert len(result.changed_files) == 0
        assert len(result.rebuild_files) == 0

    def test_changed_files_detected(self):
        tracker = IncrementalBuildTracker()
        files_v1 = {"a.ts": "const x = 1;", "b.ts": "const y = 2;"}
        tracker.update(files_v1)

        files_v2 = {"a.ts": "const x = 99;", "b.ts": "const y = 2;"}
        result = tracker.compare(files_v2)
        assert "a.ts" in result.changed_files
        assert "b.ts" in result.unchanged_files

    def test_deleted_files_detected(self):
        tracker = IncrementalBuildTracker()
        tracker.update({"a.ts": "x", "b.ts": "y"})

        result = tracker.compare({"a.ts": "x"})
        assert "b.ts" in result.deleted_files

    def test_dependency_cascade(self):
        tracker = IncrementalBuildTracker()
        files = {"a.ts": "const x = 1;", "b.ts": "import a;"}
        dep_graph = {"b.ts": ["a.ts"]}
        tracker.update(files, dep_graph)

        files_v2 = {"a.ts": "const x = 99;", "b.ts": "import a;"}
        result = tracker.compare(files_v2, dep_graph)
        # b.ts depends on a.ts which changed → b.ts must rebuild
        assert "a.ts" in result.rebuild_files
        assert "b.ts" in result.rebuild_files

    def test_compute_file_hash(self):
        h1 = compute_file_hash("hello")
        h2 = compute_file_hash("hello")
        h3 = compute_file_hash("world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA-256 hex

    def test_tracker_clear(self):
        tracker = IncrementalBuildTracker()
        tracker.update({"a.ts": "x"})
        assert tracker.file_count == 1
        tracker.clear()
        assert tracker.file_count == 0

    def test_get_hash(self):
        tracker = IncrementalBuildTracker()
        tracker.update({"a.ts": "content"})
        h = tracker.get_hash("a.ts")
        assert h is not None
        assert h.filepath == "a.ts"
        assert len(h.content_hash) == 64
