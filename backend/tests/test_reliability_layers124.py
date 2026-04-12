"""Tests for Reliability Layers 1, 2, and 4."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

# ── Layer 1: Pregeneration ───────────────────────────────────────

from app.reliability.layer1_pregeneration.dependency_resolver import (
    _parse_semver,
    _satisfies,
    check_range_compatibility,
    detect_peer_conflicts,
    resolve_dependencies,
)
from app.reliability.layer1_pregeneration.lockfile_generator import (
    generate_install_command,
    generate_lockfile,
    generate_package_json,
)
from app.reliability.layer1_pregeneration.env_contract_validator import (
    get_env_template,
    scan_generated_code,
    validate_env_against_code,
    validate_env_contract,
)


class TestDependencyResolver:
    def test_resolves_known_peer_deps(self):
        deps = {"react": "^18.2.0", "react-dom": "^18.2.0", "zustand": "5.0.2"}
        resolved = resolve_dependencies(deps)
        assert resolved["react"] == "18.3.1"
        assert resolved["react-dom"] == "18.3.1"
        assert resolved["zustand"] == "5.0.2"

    def test_preserves_range_operators(self):
        """Real fix: keep ^/~ for npm install instead of stripping them."""
        deps = {"axios": "^1.6.0", "zod": "~3.22.0"}
        resolved = resolve_dependencies(deps)
        assert resolved["axios"] == "^1.6.0"
        assert resolved["zod"] == "~3.22.0"

    def test_skips_workspace_protocols(self):
        deps = {"my-local": "workspace:*", "axios": "1.6.0"}
        resolved = resolve_dependencies(deps)
        assert "my-local" not in resolved
        assert "axios" in resolved

    def test_detect_peer_conflicts_none(self):
        deps = {"react": "18.3.1", "react-dom": "18.3.1"}
        assert detect_peer_conflicts(deps) == []

    def test_detect_peer_conflicts_major_mismatch(self):
        deps = {"react": "18.3.1", "react-dom": "17.0.2"}
        conflicts = detect_peer_conflicts(deps)
        assert len(conflicts) >= 1
        assert "mismatch" in conflicts[0]

    def test_detect_incompatible_pairs(self):
        deps = {"react-router-dom": "6.0.0", "react-router": "6.0.0"}
        conflicts = detect_peer_conflicts(deps)
        assert len(conflicts) >= 1

    def test_parse_semver(self):
        assert _parse_semver("^18.3.1") == ("^", 18, 3, 1)
        assert _parse_semver("~3.22.0") == ("~", 3, 22, 0)
        assert _parse_semver(">=1.0.0") == (">=", 1, 0, 0)
        assert _parse_semver("5.4.0") == ("", 5, 4, 0)

    def test_satisfies_caret(self):
        assert _satisfies("18.3.1", "^18.2.0") is True
        assert _satisfies("19.0.0", "^18.2.0") is False
        assert _satisfies("18.1.0", "^18.2.0") is False

    def test_satisfies_tilde(self):
        assert _satisfies("3.22.5", "~3.22.0") is True
        assert _satisfies("3.23.0", "~3.22.0") is False

    def test_satisfies_exact(self):
        assert _satisfies("1.0.0", "1.0.0") is True
        assert _satisfies("1.0.1", "1.0.0") is False

    def test_check_range_compatibility_same_major(self):
        result = check_range_compatibility("react", ["^18.2.0", "^18.3.0"])
        assert result["compatible"] is True
        assert result["resolved"] is not None

    def test_check_range_compatibility_different_major(self):
        result = check_range_compatibility("react", ["^17.0.0", "^18.0.0"])
        assert result["compatible"] is False


class TestPackageJsonGenerator:
    def test_generates_valid_json(self):
        deps = {"react": "18.3.1", "zustand": "5.0.2"}
        result = generate_package_json(deps)
        parsed = json.loads(result)
        assert parsed["name"] == "forge-generated-app"
        assert parsed["private"] is True
        assert parsed["type"] == "module"
        assert "react" in parsed["dependencies"]

    def test_deterministic_output(self):
        deps = {"zustand": "5.0.2", "react": "18.3.1"}
        a = generate_package_json(deps)
        b = generate_package_json(deps)
        assert a == b

    def test_includes_dev_deps(self):
        deps = {"react": "18.3.1"}
        dev = {"typescript": "5.4.0"}
        result = json.loads(generate_package_json(deps, dev))
        assert "typescript" in result["devDependencies"]

    def test_no_fake_integrity_hashes(self):
        """CRITICAL: We no longer generate fake lockfiles with bogus integrity."""
        deps = {"react": "18.3.1"}
        result = generate_package_json(deps)
        assert "integrity" not in result
        assert "sha512" not in result

    def test_custom_scripts(self):
        deps = {"next": "14.0.0"}
        scripts = {"dev": "next dev", "build": "next build"}
        result = json.loads(generate_package_json(deps, scripts=scripts))
        assert result["scripts"]["dev"] == "next dev"

    def test_default_scripts(self):
        result = json.loads(generate_package_json({"react": "18.3.1"}))
        assert "dev" in result["scripts"]
        assert "build" in result["scripts"]

    def test_legacy_alias_works(self):
        """generate_lockfile still works as backward-compat alias."""
        result = generate_lockfile({"react": "18.3.1"})
        parsed = json.loads(result)
        assert parsed["name"] == "forge-generated-app"

    def test_install_command(self):
        cmd = generate_install_command({"react": "18.3.1"})
        assert "npm install" in cmd
        assert "--no-audit" in cmd


class TestEnvContractValidator:
    def test_passes_with_all_required(self):
        env = {
            "DATABASE_URL": "postgres://...",
            "NEXT_PUBLIC_SUPABASE_URL": "https://...",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": "key",
            "VITE_API_URL": "http://localhost:8000",
        }
        result = validate_env_contract("vite_react", env)
        assert result["passed"] is True
        assert result["missing"] == []

    def test_fails_missing_required(self):
        result = validate_env_contract("vite_react", {})
        assert result["passed"] is False
        assert "DATABASE_URL" in result["missing"]

    def test_warns_placeholder_values(self):
        env = {
            "DATABASE_URL": "changeme",
            "NEXT_PUBLIC_SUPABASE_URL": "https://...",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": "key",
        }
        result = validate_env_contract("vite_react", env)
        assert len(result["warnings"]) > 0

    def test_framework_specific_vars(self):
        env = {
            "DATABASE_URL": "x",
            "NEXT_PUBLIC_SUPABASE_URL": "x",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": "x",
        }
        result = validate_env_contract("nextjs", env)
        assert "NEXTAUTH_SECRET" in result["missing"]

    def test_get_env_template(self):
        template = get_env_template("fastapi")
        assert "DATABASE_URL" in template
        assert "SECRET_KEY" in template

    def test_scan_process_env(self):
        files = {
            "src/config.ts": 'const url = process.env.API_URL;\nconst key = process.env.STRIPE_SECRET_KEY;',
        }
        found = scan_generated_code(files)
        assert "API_URL" in found
        assert "STRIPE_SECRET_KEY" in found

    def test_scan_import_meta_env(self):
        files = {
            "src/App.tsx": 'const url = import.meta.env.VITE_API_URL;',
        }
        found = scan_generated_code(files)
        assert "VITE_API_URL" in found

    def test_scan_python_os_environ(self):
        files = {
            "app/config.py": 'db = os.environ.get("DATABASE_URL")\nsecret = os.getenv("SECRET_KEY")',
        }
        found = scan_generated_code(files)
        assert "DATABASE_URL" in found
        assert "SECRET_KEY" in found

    def test_scan_excludes_runtime_vars(self):
        files = {
            "src/config.ts": 'const env = process.env.NODE_ENV;',
        }
        found = scan_generated_code(files)
        assert "NODE_ENV" not in found

    def test_validate_against_code_finds_missing(self):
        env = {"DATABASE_URL": "postgres://..."}
        files = {
            "src/config.ts": 'const url = process.env.DATABASE_URL;\nconst key = process.env.STRIPE_KEY;',
        }
        result = validate_env_against_code(env, files)
        assert result["passed"] is False
        assert "STRIPE_KEY" in result["missing"]

    def test_validate_against_code_passes(self):
        env = {"API_URL": "http://localhost", "SECRET": "abc"}
        files = {
            "src/config.ts": 'const url = process.env.API_URL;\nconst s = process.env.SECRET;',
        }
        result = validate_env_against_code(env, files)
        assert result["passed"] is True

    def test_scan_ignores_non_source_files(self):
        files = {
            "README.md": "process.env.FAKE_VAR",
            "src/app.ts": "process.env.REAL_VAR",
        }
        found = scan_generated_code(files)
        assert "FAKE_VAR" not in found
        assert "REAL_VAR" in found


# ── Layer 2: Schema-Driven ───────────────────────────────────────

from app.reliability.layer2_schema_driven.openapi_injector import (
    generate_openapi_spec,
    openapi_to_yaml,
)
from app.reliability.layer2_schema_driven.zod_schema_injector import generate_zod_schemas
from app.reliability.layer2_schema_driven.pydantic_schema_injector import (
    extract_model_defs,
    generate_pydantic_models,
)
from app.reliability.layer2_schema_driven.db_type_injector import generate_ts_interfaces


class TestOpenAPIInjector:
    def test_generates_valid_spec(self):
        plan = {
            "cpo": {
                "user_stories": [
                    {"title": "Create task"},
                    {"title": "View dashboard"},
                ]
            },
            "cto": {},
        }
        spec = generate_openapi_spec(plan)
        assert spec["openapi"] == "3.1.0"
        assert "paths" in spec
        assert len(spec["paths"]) > 0

    def test_empty_plan(self):
        spec = generate_openapi_spec({})
        assert spec["openapi"] == "3.1.0"
        assert spec["paths"] == {}

    def test_openapi_to_yaml_is_json(self):
        spec = {"openapi": "3.1.0", "info": {"title": "Test"}, "paths": {}}
        result = openapi_to_yaml(spec)
        parsed = json.loads(result)
        assert parsed["openapi"] == "3.1.0"

    def test_generates_schemas_from_model_defs(self):
        """CRITICAL: When model_defs provided, spec has real $ref schemas."""
        plan = {
            "cpo": {"user_stories": [{"title": "Create task"}]},
        }
        model_defs = [{
            "name": "Task",
            "fields": [
                {"name": "id", "type": "uuid", "required": True},
                {"name": "title", "type": "str", "required": True},
                {"name": "description", "type": "Optional[str]", "required": False},
            ],
        }]
        spec = generate_openapi_spec(plan, model_defs=model_defs)
        # Should have schemas in components
        assert "schemas" in spec["components"]
        assert "Task" in spec["components"]["schemas"]
        assert "TaskCreate" in spec["components"]["schemas"]
        # Task schema should have proper properties
        task_schema = spec["components"]["schemas"]["Task"]
        assert "id" in task_schema["properties"]
        assert task_schema["properties"]["id"]["format"] == "uuid"
        # TaskCreate should NOT have id/timestamps
        create_schema = spec["components"]["schemas"]["TaskCreate"]
        assert "id" not in create_schema["properties"]

    def test_schema_refs_in_paths(self):
        """Paths should reference schemas via $ref."""
        plan = {"cpo": {"user_stories": [{"title": "Create task"}]}}
        model_defs = [{"name": "Task", "fields": [{"name": "id", "type": "uuid", "required": True}]}]
        spec = generate_openapi_spec(plan, model_defs=model_defs)
        # Find the POST endpoint and check for requestBody
        task_list_path = spec["paths"].get("/api/task", {})
        if "post" in task_list_path:
            post = task_list_path["post"]
            assert "requestBody" in post
            body_schema = post["requestBody"]["content"]["application/json"]["schema"]
            assert "$ref" in body_schema

    def test_optional_types_nullable(self):
        """Optional fields should be nullable in OpenAPI schema."""
        model_defs = [{"name": "X", "fields": [
            {"name": "bio", "type": "Optional[str]", "required": False},
        ]}]
        spec = generate_openapi_spec({}, model_defs=model_defs)
        if "schemas" in spec["components"]:
            x_schema = spec["components"]["schemas"]["X"]
            assert x_schema["properties"]["bio"].get("nullable") is True


class TestZodSchemaInjector:
    def test_generates_zod_schemas(self):
        models = [{
            "name": "User",
            "fields": [
                {"name": "id", "type": "uuid", "required": True},
                {"name": "name", "type": "str", "required": True},
                {"name": "bio", "type": "Optional[str]", "required": False},
            ],
        }]
        result = generate_zod_schemas(models)
        assert "UserSchema" in result
        assert "z.string().uuid()" in result
        assert ".nullable()" in result
        assert 'import { z } from "zod"' in result

    def test_optional_nullable(self):
        models = [{
            "name": "Item",
            "fields": [
                {"name": "desc", "type": "str | None", "required": False},
            ],
        }]
        result = generate_zod_schemas(models)
        assert ".nullable()" in result

    def test_type_inference(self):
        result = generate_zod_schemas([{
            "name": "T",
            "fields": [{"name": "x", "type": "int", "required": True}],
        }])
        assert "z.number().int()" in result


class TestPydanticSchemaInjector:
    def test_generates_models(self):
        spec = {"db": {"tables": [{
            "name": "users",
            "columns": [
                {"name": "id", "type": "uuid", "nullable": False},
                {"name": "email", "type": "str", "nullable": False},
            ],
        }]}}
        code = generate_pydantic_models(spec)
        assert "class Users(BaseModel):" in code
        assert "pydantic" in code

    def test_extract_model_defs(self):
        spec = {"db": {"tables": [{
            "name": "tasks",
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "title", "type": "str"},
            ],
        }]}}
        defs = extract_model_defs(spec)
        assert len(defs) >= 1
        assert defs[0]["name"] == "Tasks"

    def test_fallback_model(self):
        """No db tables → generates default Item model."""
        defs = extract_model_defs({})
        assert len(defs) == 1
        assert defs[0]["name"] == "Item"


class TestDBTypeInjector:
    def test_generates_ts_interfaces(self):
        models = [{
            "name": "User",
            "fields": [
                {"name": "id", "type": "uuid", "required": True},
                {"name": "name", "type": "str", "required": True},
                {"name": "bio", "type": "Optional[str]", "required": False},
            ],
        }]
        result = generate_ts_interfaces(models)
        assert "export interface User" in result
        assert "id: string;" in result
        assert "bio?: string | null;" in result

    def test_optional_is_null_not_string(self):
        """CRITICAL: Optional[str] → string | null, NOT just string."""
        models = [{
            "name": "T",
            "fields": [
                {"name": "x", "type": "Optional[str]", "required": False},
            ],
        }]
        result = generate_ts_interfaces(models)
        assert "string | null" in result

    def test_union_none_type(self):
        """str | None → string | null."""
        models = [{
            "name": "T",
            "fields": [
                {"name": "x", "type": "str | None", "required": False},
            ],
        }]
        result = generate_ts_interfaces(models)
        assert "string | null" in result


# ── Layer 4: Coherence ───────────────────────────────────────────

from app.reliability.layer4_coherence.barrel_validator import validate_barrels
from app.reliability.layer4_coherence.seam_checker import check_seams
from app.reliability.layer4_coherence.file_coherence_engine import (
    _levenshtein,
    _parse_exports,
    _parse_imports,
    _find_case_match,
    _find_close_match,
)


class TestBarrelValidator:
    def test_passes_when_all_exported(self):
        files = {
            "src/components/index.ts": "export * from './Button'\nexport * from './Card'",
            "src/components/Button.tsx": "export const Button = () => {}",
            "src/components/Card.tsx": "export const Card = () => {}",
        }
        result = validate_barrels(files)
        assert result["passed"] is True
        assert result["missing_exports"] == []

    def test_fails_missing_export(self):
        files = {
            "src/components/index.ts": "export * from './Button'",
            "src/components/Button.tsx": "export const Button = () => {}",
            "src/components/Card.tsx": "export const Card = () => {}",
        }
        result = validate_barrels(files)
        assert result["passed"] is False
        assert len(result["missing_exports"]) == 1
        assert result["missing_exports"][0]["missing_module"] == "Card"

    def test_ignores_test_files(self):
        files = {
            "src/components/index.ts": "export * from './Button'",
            "src/components/Button.tsx": "export const Button = () => {}",
            "src/components/Button.test.tsx": "test('Button', () => {})",
        }
        result = validate_barrels(files)
        assert result["passed"] is True

    def test_no_barrels(self):
        files = {
            "src/App.tsx": "export default function App() {}",
        }
        result = validate_barrels(files)
        assert result["passed"] is True


class TestSeamChecker:
    def test_passes_matching_routes(self):
        files = {
            "backend/app/api/routes.py": '@router.get("/api/tasks")\nasync def list_tasks(): ...',
            "frontend/src/api.ts": 'api.get("/api/tasks")',
        }
        result = check_seams(files)
        assert result["passed"] is True

    def test_fails_missing_route(self):
        files = {
            "backend/app/api/routes.py": '@router.get("/api/tasks")\nasync def list_tasks(): ...',
            "frontend/src/api.ts": 'api.get("/api/users")',
        }
        result = check_seams(files)
        assert result["passed"] is False
        assert len(result["broken_seams"]) == 1
        assert result["broken_seams"][0]["type"] == "missing_route"

    def test_no_api_calls(self):
        files = {
            "frontend/src/App.tsx": "export default function App() { return <div /> }",
        }
        result = check_seams(files)
        assert result["passed"] is True

    def test_parameterized_routes_match(self):
        files = {
            "backend/app/api/routes.py": '@router.get("/api/tasks/{id}")\nasync def get_task(): ...',
            "frontend/src/api.ts": 'api.get(`/api/tasks/${taskId}`)',
        }
        result = check_seams(files)
        assert result["passed"] is True


class TestCoherenceHelpers:
    def test_levenshtein_identical(self):
        assert _levenshtein("hello", "hello") == 0

    def test_levenshtein_one_char(self):
        assert _levenshtein("hello", "helo") == 1

    def test_levenshtein_two_chars(self):
        assert _levenshtein("Button", "Buton") == 1

    def test_find_case_match(self):
        available = {"Button", "Card"}
        assert _find_case_match("button", available) == "Button"
        assert _find_case_match("CARD", available) == "Card"
        assert _find_case_match("Foo", available) is None

    def test_find_close_match(self):
        available = {"Button", "Card", "Input"}
        assert _find_close_match("Buton", available) == "Button"
        assert _find_close_match("xyz", available) is None


class TestParseExportsImports:
    def test_parse_exports(self, tmp_path):
        (tmp_path / "comp.ts").write_text(
            "export const Button = () => {}\nexport function useHook() {}\nexport { Card, Input }"
        )
        result = _parse_exports(str(tmp_path), ["comp.ts"])
        assert "Button" in result["comp.ts"]
        assert "useHook" in result["comp.ts"]
        assert "Card" in result["comp.ts"]
        assert "Input" in result["comp.ts"]

    def test_parse_exports_default(self, tmp_path):
        (tmp_path / "App.tsx").write_text("export default function App() {}")
        result = _parse_exports(str(tmp_path), ["App.tsx"])
        assert "App" in result["App.tsx"]
        assert "default" in result["App.tsx"]

    def test_parse_exports_as_alias(self, tmp_path):
        (tmp_path / "mod.ts").write_text("export { Foo as Bar, Baz }")
        result = _parse_exports(str(tmp_path), ["mod.ts"])
        assert "Bar" in result["mod.ts"]
        assert "Foo" in result["mod.ts"]
        assert "Baz" in result["mod.ts"]

    def test_parse_imports(self, tmp_path):
        (tmp_path / "App.tsx").write_text(
            "import { Button, Card } from './components'\nimport React from 'react'"
        )
        result = _parse_imports(str(tmp_path), ["App.tsx"])
        local = [i for i in result if i["from_module"].startswith(".")]
        assert len(local) == 1
        assert "Button" in local[0]["names"]
        assert "Card" in local[0]["names"]

    def test_parse_import_type(self, tmp_path):
        """import type { X } from '...' should be caught."""
        (tmp_path / "comp.ts").write_text("import type { User } from './types'")
        result = _parse_imports(str(tmp_path), ["comp.ts"])
        local = [i for i in result if i["from_module"].startswith(".")]
        assert len(local) == 1
        assert "User" in local[0]["names"]

    def test_parse_import_default_and_named(self, tmp_path):
        """import X, { Y, Z } from '...' should catch all three."""
        (tmp_path / "comp.ts").write_text("import React, { useState, useEffect } from './react-shim'")
        result = _parse_imports(str(tmp_path), ["comp.ts"])
        local = [i for i in result if i["from_module"].startswith(".")]
        assert len(local) == 1
        names = local[0]["names"]
        assert "React" in names
        assert "useState" in names
        assert "useEffect" in names


class TestCoherenceEngine:
    @pytest.mark.asyncio
    async def test_coherence_check_passes(self):
        """Clean files with valid imports should pass."""
        files = {
            "src/components/Button.tsx": "export const Button = () => {}",
            "src/App.tsx": "import { Button } from './components/Button'",
        }
        build_id = uuid.uuid4()
        with patch("app.reliability.layer4_coherence.file_coherence_engine._store_report", new_callable=AsyncMock):
            report = await run_coherence_check(build_id, files)
        assert report["passed"] is True
        assert report["critical_errors"] == 0

    @pytest.mark.asyncio
    async def test_coherence_check_auto_fixes_typo(self):
        """Typo within levenshtein ≤2 should auto-fix."""
        files = {
            "src/components/Button.tsx": "export const Button = () => {}",
            "src/App.tsx": "import { Buton } from './components/Button'",
        }
        build_id = uuid.uuid4()
        with patch("app.reliability.layer4_coherence.file_coherence_engine._store_report", new_callable=AsyncMock):
            report = await run_coherence_check(build_id, files)
        assert report["auto_fixes"] >= 1

    @pytest.mark.asyncio
    async def test_coherence_check_escalates_missing(self):
        """Import from nonexistent file → critical error."""
        files = {
            "src/App.tsx": "import { Foo } from './nonexistent'",
        }
        build_id = uuid.uuid4()
        with patch("app.reliability.layer4_coherence.file_coherence_engine._store_report", new_callable=AsyncMock):
            report = await run_coherence_check(build_id, files)
        assert report["critical_errors"] >= 1
        assert report["passed"] is False

    @pytest.mark.asyncio
    async def test_coherence_check_empty_files(self):
        """No TS files → passes trivially."""
        build_id = uuid.uuid4()
        with patch("app.reliability.layer4_coherence.file_coherence_engine._store_report", new_callable=AsyncMock):
            report = await run_coherence_check(build_id, {})
        assert report["passed"] is True


# ── Graph integration smoke test ─────────────────────────────────

from app.reliability.layer4_coherence.file_coherence_engine import run_coherence_check


class TestGraphIntegration:
    def test_imports_resolve(self):
        """Verify graph.py can import all reliability modules."""
        from app.agents.graph import (
            build,
            build_pipeline_graph,
            input_layer,
            spec_layer,
        )
        # If we get here, all imports resolved
        assert callable(build_pipeline_graph)
        assert callable(input_layer)
        assert callable(spec_layer)
        assert callable(build)
