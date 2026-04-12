"""Tests for Layer 8 — Post-build Verification Suite."""
from __future__ import annotations

import json

import pytest

from app.reliability.layer8_verification.visual_regression import (
    _extract_routes_from_files,
    _placeholder_png,
    _compute_diff_percentage,
    run_visual_regression,
)
from app.reliability.layer8_verification.sast_scanner import (
    SASTFinding,
    _scan_secrets,
    _scan_security,
    _is_scannable,
    run_sast_scan,
)
from app.reliability.layer8_verification.perf_budget import (
    PerfBudget,
    _estimate_bundle_size,
    _estimate_lcp,
    _estimate_cls,
    _estimate_fid,
    run_perf_budget,
)
from app.reliability.layer8_verification.accessibility_audit import (
    _check_images_alt,
    _check_form_labels,
    _check_heading_order,
    _check_interactive_roles,
    _check_lang_attribute,
    run_accessibility_audit,
)
from app.reliability.layer8_verification.dead_code_detector import (
    _parse_exports,
    _parse_imports,
    run_dead_code_detection,
)
from app.reliability.layer8_verification.seed_generator import (
    FakerLite,
    _extract_schemas,
    _topological_sort,
    run_seed_generator,
)


# ══════════════════════════════════════════════════════════════════
# 8a — Visual Regression
# ══════════════════════════════════════════════════════════════════


class TestVisualRegression:
    def test_extract_routes_from_router(self):
        files = {
            "src/App.tsx": '''
                <Route path="/" element={<Home />} />
                <Route path="/login" element={<Login />} />
                <Route path="/dashboard" element={<Dashboard />} />
            ''',
        }
        routes = _extract_routes_from_files(files)
        assert "/" in routes
        assert "/login" in routes
        assert "/dashboard" in routes

    def test_extract_routes_default_when_empty(self):
        routes = _extract_routes_from_files({})
        assert "/" in routes
        assert "/login" in routes

    def test_placeholder_png_valid(self):
        png = _placeholder_png()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 20

    def test_diff_percentage_identical(self):
        data = b"identical bytes here"
        assert _compute_diff_percentage(data, data) == 0.0

    def test_diff_percentage_different(self):
        a = b"\x00" * 100
        b = b"\xff" * 100
        assert _compute_diff_percentage(a, b) == 100.0

    def test_diff_percentage_empty_baseline(self):
        assert _compute_diff_percentage(b"", b"something") == 100.0

    @pytest.mark.asyncio
    async def test_run_without_preview_url(self):
        files = {"src/App.tsx": '<Route path="/home" element={<Home />} />'}
        result = await run_visual_regression(
            build_id="test-build-1",
            generated_files=files,
            preview_url=None,
        )
        assert result["passed"] is True
        assert result["baselines_created"] > 0
        assert all(r["status"] == "baseline_created" for r in result["results"])

    @pytest.mark.asyncio
    async def test_run_with_preview_url_no_playwright(self):
        """Without playwright installed, falls back to placeholder PNG."""
        files = {"src/App.tsx": '<Route path="/" element={<Home />} />'}
        result = await run_visual_regression(
            build_id="test-build-2",
            generated_files=files,
            preview_url="http://localhost:3000",
        )
        # Should still return a result (baseline_created since no prior baseline)
        assert "results" in result
        assert result["total_pages"] >= 1


# ══════════════════════════════════════════════════════════════════
# 8b — SAST Scanner
# ══════════════════════════════════════════════════════════════════


class TestSASTScanner:
    def test_detect_hardcoded_api_key(self):
        code = 'const API_KEY = "sk_live_abc123456789012345678";'
        findings = _scan_secrets("src/config.ts", code)
        assert len(findings) >= 1
        assert any(f.rule_id == "hardcoded_api_key" for f in findings)

    def test_detect_private_key(self):
        code = "-----BEGIN RSA PRIVATE KEY-----\nMIIBogIBAAJ..."
        findings = _scan_secrets("certs/key.pem", code)
        assert any(f.rule_id == "private_key_pem" for f in findings)

    def test_skip_env_references(self):
        code = 'const key = process.env.API_KEY;'
        findings = _scan_secrets("src/config.ts", code)
        assert len(findings) == 0

    def test_skip_comments(self):
        code = '// api_key = "sk_live_abc123456789012345678"'
        findings = _scan_secrets("src/config.ts", code)
        assert len(findings) == 0

    def test_detect_sql_injection(self):
        code = 'db.query(f"SELECT * FROM users WHERE id = {user_id}")'
        findings = _scan_security("src/db.py", code)
        assert any(f.rule_id == "sql_injection" for f in findings)

    def test_detect_eval(self):
        code = "const result = eval(userInput);"
        findings = _scan_security("src/utils.ts", code)
        assert any(f.rule_id == "eval_usage" for f in findings)

    def test_detect_xss_dangerously(self):
        code = '<div dangerouslySetInnerHTML={{ __html: content }} />'
        findings = _scan_security("src/Page.tsx", code)
        assert any(f.rule_id == "xss_dangerously_set" for f in findings)

    def test_is_scannable(self):
        assert _is_scannable("src/app.ts") is True
        assert _is_scannable("src/app.tsx") is True
        assert _is_scannable("src/app.py") is True
        assert _is_scannable("image.png") is False
        assert _is_scannable("font.woff2") is False

    @pytest.mark.asyncio
    async def test_sast_clean_code_passes(self):
        files = {
            "src/app.ts": "export function hello() { return 'world'; }",
            "src/utils.ts": "export const add = (a: number, b: number) => a + b;",
        }
        result = await run_sast_scan(files)
        assert result["passed"] is True
        assert result["critical"] == 0
        assert result["high"] == 0

    @pytest.mark.asyncio
    async def test_sast_critical_fails_g11(self):
        files = {
            "src/vulns.py": 'db.query(f"SELECT * FROM users WHERE id={uid}")',
        }
        result = await run_sast_scan(files)
        assert result["passed"] is False
        assert result["critical"] >= 1

    @pytest.mark.asyncio
    async def test_sast_deduplication(self):
        code = 'eval(x); eval(y);'
        files = {"src/bad.ts": code}
        result = await run_sast_scan(files)
        # Two eval usages on different conceptual lines — both found
        eval_findings = [f for f in result["findings"] if f["rule_id"] == "eval_usage"]
        assert len(eval_findings) >= 1


# ══════════════════════════════════════════════════════════════════
# 8c — Performance Budget
# ══════════════════════════════════════════════════════════════════


class TestPerfBudget:
    def test_estimate_bundle_size_small(self):
        files = {"src/app.ts": "export const x = 1;"}
        size = _estimate_bundle_size(files)
        assert size < 10  # Very small

    def test_estimate_bundle_size_heavy_imports(self):
        files = {
            "src/app.ts": 'import moment from "moment";\nimport _ from "lodash";\nimport * as THREE from "three";',
        }
        size = _estimate_bundle_size(files)
        assert size >= 200  # Heavy imports add up: moment(70)+lodash(70)+three(150)

    def test_estimate_lcp_small_bundle(self):
        files = {"src/app.tsx": "const App = () => <div>Hello</div>;"}
        lcp = _estimate_lcp(files, 50)
        assert lcp <= 2500  # Should be within budget

    def test_estimate_lcp_with_lazy_loading(self):
        files = {"src/app.tsx": "const Page = React.lazy(() => import('./Page'));"}
        lcp_lazy = _estimate_lcp(files, 100)
        files_no_lazy = {"src/app.tsx": "import Page from './Page';"}
        lcp_no_lazy = _estimate_lcp(files_no_lazy, 100)
        assert lcp_lazy < lcp_no_lazy  # Lazy loading reduces LCP

    def test_estimate_cls_base(self):
        files = {"src/app.tsx": "<div>Simple page</div>"}
        cls = _estimate_cls(files)
        assert cls <= 0.1  # Simple page should be fine

    def test_estimate_cls_images_without_dimensions(self):
        files = {"src/page.tsx": '<img src="photo.jpg"><img src="hero.png">'}
        cls = _estimate_cls(files)
        assert cls > 0.1  # Images without dimensions increase CLS

    def test_estimate_fid_small(self):
        fid = _estimate_fid(50)
        assert fid <= 100  # Small bundle → low FID

    def test_estimate_fid_large(self):
        fid = _estimate_fid(1000)
        assert fid > 100  # Huge bundle → high FID

    @pytest.mark.asyncio
    async def test_perf_budget_passes_small_app(self):
        files = {
            "src/App.tsx": "const App = () => <div>Hello</div>; export default App;",
            "src/index.ts": "import App from './App';",
        }
        result = await run_perf_budget(files)
        assert result["passed"] is True
        assert result["bundle_size_kb"] < 500

    @pytest.mark.asyncio
    async def test_perf_budget_fails_huge_bundle(self):
        files = {
            "src/app.ts": (
                'import moment from "moment";\n'
                'import _ from "lodash";\n'
                'import * as THREE from "three";\n'
                'import firebase from "firebase";\n'
                'import * as d3 from "d3";\n'
            ) + "x" * 500_000,  # Huge file
        }
        result = await run_perf_budget(files)
        assert result["passed"] is False
        assert result["bundle_size_kb"] > 500

    @pytest.mark.asyncio
    async def test_perf_budget_custom_thresholds(self):
        # ~1KB raw * 0.6 = ~0.6KB — exceeds 0.1KB budget
        files = {"src/app.ts": "x" * 1500}
        result = await run_perf_budget(files, budget=PerfBudget(bundle_kb=0.1))
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_perf_budget_lighthouse_results(self):
        files = {"src/app.ts": "x"}
        lighthouse = {"lcp_ms": 1500, "cls": 0.05, "fid_ms": 50, "bundle_size_kb": 200}
        result = await run_perf_budget(files, lighthouse_results=lighthouse)
        assert result["passed"] is True
        assert result["estimated_lcp_ms"] == 1500


# ══════════════════════════════════════════════════════════════════
# 8d — Accessibility Audit
# ══════════════════════════════════════════════════════════════════


class TestAccessibilityAudit:
    def test_images_without_alt(self):
        code = '<img src="photo.jpg" />'
        violations = _check_images_alt("src/Page.tsx", code)
        assert len(violations) == 1
        assert violations[0].rule_id == "image-alt"
        assert violations[0].impact == "critical"

    def test_images_with_alt(self):
        code = '<img src="photo.jpg" alt="A photo" />'
        violations = _check_images_alt("src/Page.tsx", code)
        assert len(violations) == 0

    def test_input_without_label(self):
        code = '<input type="text" />'
        violations = _check_form_labels("src/Form.tsx", code)
        assert len(violations) == 1
        assert violations[0].rule_id == "label"

    def test_input_with_aria_label(self):
        code = '<input type="text" aria-label="Username" />'
        violations = _check_form_labels("src/Form.tsx", code)
        assert len(violations) == 0

    def test_hidden_input_skipped(self):
        code = '<input type="hidden" name="csrf" />'
        violations = _check_form_labels("src/Form.tsx", code)
        assert len(violations) == 0

    def test_heading_order_skip(self):
        code = "<h1>Title</h1>\n<h3>Subtitle</h3>"
        violations = _check_heading_order("src/Page.tsx", code)
        assert len(violations) == 1
        assert violations[0].rule_id == "heading-order"

    def test_heading_order_correct(self):
        code = "<h1>Title</h1>\n<h2>Subtitle</h2>"
        violations = _check_heading_order("src/Page.tsx", code)
        assert len(violations) == 0

    def test_div_onclick_without_role(self):
        code = '<div onClick={handleClick}>Click me</div>'
        violations = _check_interactive_roles("src/Page.tsx", code)
        assert len(violations) == 1
        assert violations[0].rule_id == "interactive-role"

    def test_div_onclick_with_role(self):
        code = '<div onClick={handleClick} role="button" tabIndex={0}>Click</div>'
        violations = _check_interactive_roles("src/Page.tsx", code)
        assert len(violations) == 0

    def test_html_without_lang(self):
        code = "<html><head></head><body></body></html>"
        violations = _check_lang_attribute("src/index.html", code)
        assert len(violations) == 1

    def test_html_with_lang(self):
        code = '<html lang="en"><head></head><body></body></html>'
        violations = _check_lang_attribute("src/index.html", code)
        assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_audit_clean_code_passes(self):
        files = {
            "src/Page.tsx": '<img src="x" alt="desc" />\n<input id="name" />\n<h1>Title</h1>\n<h2>Sub</h2>',
        }
        result = await run_accessibility_audit(files)
        assert result["passed"] is True
        assert result["critical"] == 0

    @pytest.mark.asyncio
    async def test_audit_critical_fails(self):
        files = {
            "src/Page.tsx": '<img src="photo.jpg" />',
        }
        result = await run_accessibility_audit(files)
        assert result["passed"] is False
        assert result["critical"] >= 1

    @pytest.mark.asyncio
    async def test_audit_serious_is_warning_not_failure(self):
        files = {
            "src/Page.tsx": '<div onClick={handleClick}>Click me</div>\n<img alt="ok" src="x" />',
        }
        result = await run_accessibility_audit(files)
        # Serious violations → warning, but don't fail
        if result["serious"] > 0:
            assert result["passed"] is True or result["critical"] > 0
            assert len(result["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_non_tsx_files_skipped(self):
        files = {
            "src/utils.ts": '<img src="not_audited.jpg" />',  # .ts not audited
        }
        result = await run_accessibility_audit(files)
        assert result["total_violations"] == 0


# ══════════════════════════════════════════════════════════════════
# 8e — Dead Code Detector
# ══════════════════════════════════════════════════════════════════


class TestDeadCodeDetector:
    def test_parse_exports_named(self):
        code = "export function hello() {}\nexport const world = 1;"
        exports = _parse_exports("src/utils.ts", code)
        names = [e[0] for e in exports]
        assert "hello" in names
        assert "world" in names

    def test_parse_exports_default(self):
        code = "export default function App() {}"
        exports = _parse_exports("src/App.tsx", code)
        assert any(e[0] == "App" for e in exports)

    def test_parse_exports_braces(self):
        code = "export { foo, bar };"
        exports = _parse_exports("src/index.ts", code)
        names = [e[0] for e in exports]
        assert "foo" in names
        assert "bar" in names

    def test_parse_imports_named(self):
        code = "import { useState, useEffect } from 'react';"
        imported = _parse_imports(code)
        assert "useState" in imported
        assert "useEffect" in imported

    def test_parse_imports_default(self):
        code = "import React from 'react';"
        imported = _parse_imports(code)
        assert "React" in imported

    def test_parse_imports_jsx_usage(self):
        code = "<MyComponent prop={1} />"
        imported = _parse_imports(code)
        assert "MyComponent" in imported

    @pytest.mark.asyncio
    async def test_dead_code_all_used(self):
        files = {
            "src/utils.ts": "export function greet() { return 'hi'; }",
            "src/App.tsx": "import { greet } from './utils';\ngreet();",
        }
        result = await run_dead_code_detection(files)
        assert result["passed"] is True  # Always true
        assert result["total_unused"] == 0

    @pytest.mark.asyncio
    async def test_dead_code_unused_export(self):
        files = {
            "src/helpers.ts": "export function usedFn() {}\nexport function unusedFn() {}",
            "src/App.tsx": "import { usedFn } from './helpers';\nusedFn();",
        }
        result = await run_dead_code_detection(files)
        assert result["passed"] is True  # NEVER fails
        assert result["total_unused"] >= 1
        unused_names = [i["symbol"] for i in result["items"]]
        assert "unusedFn" in unused_names

    @pytest.mark.asyncio
    async def test_dead_code_never_fails(self):
        """Even with many unused exports, passed is always True."""
        files = {
            "src/lib.ts": "\n".join(f"export function fn{i}() {{}}" for i in range(50)),
        }
        result = await run_dead_code_detection(files)
        assert result["passed"] is True
        assert result["total_unused"] > 0

    @pytest.mark.asyncio
    async def test_dead_code_skips_entry_points(self):
        files = {
            "src/App.tsx": "export default function App() {}",
            "src/main.ts": "export function main() {}",
        }
        result = await run_dead_code_detection(files)
        unused_names = [i["symbol"] for i in result["items"]]
        assert "App" not in unused_names
        assert "main" not in unused_names

    @pytest.mark.asyncio
    async def test_dead_code_skips_index_files(self):
        files = {
            "src/index.ts": "export function something() {}",
        }
        result = await run_dead_code_detection(files)
        assert result["total_unused"] == 0

    @pytest.mark.asyncio
    async def test_dead_code_empty_files(self):
        result = await run_dead_code_detection({})
        assert result["passed"] is True
        assert result["total_unused"] == 0


# ══════════════════════════════════════════════════════════════════
# 8f — Seed Generator
# ══════════════════════════════════════════════════════════════════


class TestSeedGenerator:
    def test_faker_lite_deterministic(self):
        f1 = FakerLite(seed=42)
        f2 = FakerLite(seed=42)
        assert f1.full_name() == f2.full_name()
        assert f1.email() == f2.email()
        assert f1.uuid() == f2.uuid()
        assert f1.integer() == f2.integer()

    def test_faker_lite_different_seeds(self):
        f1 = FakerLite(seed=42)
        f2 = FakerLite(seed=99)
        # With different seeds, results should (almost certainly) differ
        names1 = [f1.full_name() for _ in range(10)]
        names2 = [f2.full_name() for _ in range(10)]
        assert names1 != names2

    def test_faker_lite_email_unique(self):
        f = FakerLite(seed=42)
        emails = [f.email() for _ in range(20)]
        assert len(set(emails)) == 20

    def test_extract_prisma_schemas(self):
        prisma = '''
        model User {
            id    String @id @default(uuid())
            email String @unique
            name  String?
            posts Post[]
        }

        model Post {
            id       String @id @default(uuid())
            title    String
            authorId String
            author   User   @relation(fields: [authorId], references: [id])
        }
        '''
        files = {"prisma/schema.prisma": prisma}
        schemas = _extract_schemas(files)
        assert len(schemas) == 2
        names = [s.name for s in schemas]
        assert "User" in names
        assert "Post" in names

    def test_extract_sql_schemas(self):
        sql = '''
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            name TEXT
        );

        CREATE TABLE posts (
            id UUID PRIMARY KEY,
            title TEXT NOT NULL,
            user_id UUID REFERENCES users(id)
        );
        '''
        files = {"db/schema.sql": sql}
        schemas = _extract_schemas(files)
        assert len(schemas) == 2

    def test_topological_sort_fk_order(self):
        from app.reliability.layer8_verification.seed_generator import (
            TableSchema, ForeignKey,
        )
        schemas = [
            TableSchema(
                name="posts",
                foreign_keys=[ForeignKey(column="user_id", references_table="users", references_column="id")],
            ),
            TableSchema(name="users"),
        ]
        order = _topological_sort(schemas)
        assert order.index("users") < order.index("posts")

    def test_topological_sort_no_deps(self):
        from app.reliability.layer8_verification.seed_generator import TableSchema
        schemas = [TableSchema(name="b"), TableSchema(name="a")]
        order = _topological_sort(schemas)
        # Alphabetical when no deps
        assert order == ["a", "b"]

    @pytest.mark.asyncio
    async def test_seed_generator_with_prisma(self):
        prisma = '''
        model User {
            id    String @id @default(uuid())
            email String @unique
            name  String
        }
        '''
        files = {"prisma/schema.prisma": prisma}
        result = await run_seed_generator(files)
        assert result["passed"] is True
        assert result["tables_seeded"] >= 1
        assert result["user_count"] == 10  # Default user count
        assert result["total_records"] >= 10
        assert "prisma/seed.json" in result["seed_files"]
        assert "prisma/seed.ts" in result["seed_files"]

        # Verify JSON is valid
        seed_data = json.loads(result["seed_files"]["prisma/seed.json"])
        assert "User" in seed_data
        assert len(seed_data["User"]) == 10

    @pytest.mark.asyncio
    async def test_seed_generator_no_schemas(self):
        files = {"src/app.ts": "export const x = 1;"}
        result = await run_seed_generator(files)
        assert result["passed"] is True
        assert result["tables_seeded"] == 0
        assert len(result["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_seed_generator_deterministic(self):
        prisma = 'model Item { id String @id\n title String }'
        files = {"prisma/schema.prisma": prisma}
        r1 = await run_seed_generator(files)
        r2 = await run_seed_generator(files)
        assert r1["seed_files"]["prisma/seed.json"] == r2["seed_files"]["prisma/seed.json"]

    @pytest.mark.asyncio
    async def test_seed_generator_fk_order_respected(self):
        prisma = '''
        model Comment {
            id     String @id
            text   String
            postId String
            post   Post   @relation(fields: [postId], references: [id])
        }
        model Post {
            id       String @id
            title    String
            authorId String
            author   User   @relation(fields: [authorId], references: [id])
        }
        model User {
            id   String @id
            name String
        }
        '''
        files = {"prisma/schema.prisma": prisma}
        result = await run_seed_generator(files)
        order = result["table_order"]
        assert order.index("User") < order.index("Post")
        assert order.index("Post") < order.index("Comment")


# ══════════════════════════════════════════════════════════════════
# Integration — ReviewAgent calls all Layer 8 modules
# ══════════════════════════════════════════════════════════════════


class TestReviewAgentLayer8Integration:
    @pytest.mark.asyncio
    async def test_review_agent_includes_all_layer8_keys(self):
        from unittest.mock import AsyncMock, patch

        from app.agents.build.review_agent import ReviewAgent

        agent = ReviewAgent()
        state = {
            "pipeline_id": "00000000-0000-0000-0000-000000000001",
            "generated_files": {
                "src/App.tsx": "export default function App() { return <div>Hello</div>; }",
            },
        }

        with patch(
            "app.reliability.layer4_coherence.file_coherence_engine.run_coherence_check",
            new_callable=AsyncMock,
            return_value={"unresolved": [], "auto_fixed": [], "passed": True},
        ), patch(
            "app.reliability.layer4_coherence.barrel_validator.validate_barrels",
            return_value={"valid": True, "missing": []},
        ), patch(
            "app.reliability.layer4_coherence.seam_checker.check_seams",
            return_value={"mismatches": []},
        ):
            report = await agent.review(state)

        # Layer 8 keys must all be present
        assert "visual_regression" in report
        assert "sast" in report
        assert "perf_budget" in report
        assert "accessibility" in report
        assert "dead_code" in report
        assert "seed" in report
        assert "gates" in report

        # Dead code should never fail
        assert report["dead_code"]["passed"] is True

    @pytest.mark.asyncio
    async def test_review_agent_sast_failure_fails_g11(self):
        from unittest.mock import AsyncMock, patch

        from app.agents.build.review_agent import ReviewAgent

        agent = ReviewAgent()
        state = {
            "pipeline_id": "00000000-0000-0000-0000-000000000002",
            "generated_files": {
                "src/vuln.py": 'db.query(f"SELECT * FROM users WHERE id={uid}")',
            },
        }

        with patch(
            "app.reliability.layer4_coherence.file_coherence_engine.run_coherence_check",
            new_callable=AsyncMock,
            return_value={"unresolved": [], "auto_fixed": [], "passed": True},
        ), patch(
            "app.reliability.layer4_coherence.barrel_validator.validate_barrels",
            return_value={"valid": True, "missing": []},
        ), patch(
            "app.reliability.layer4_coherence.seam_checker.check_seams",
            return_value={"mismatches": []},
        ):
            report = await agent.review(state)

        # SAST critical finding should fail G11
        assert report["sast"]["passed"] is False
        assert report["gates"]["g11"]["passed"] is False
        assert report["passed"] is False

    @pytest.mark.asyncio
    async def test_review_agent_layer8_order(self):
        """Verify Layer 8 modules execute (all keys present in report)."""
        from unittest.mock import AsyncMock, patch

        from app.agents.build.review_agent import ReviewAgent

        agent = ReviewAgent()
        state = {
            "pipeline_id": "00000000-0000-0000-0000-000000000003",
            "generated_files": {},
        }

        with patch(
            "app.reliability.layer4_coherence.file_coherence_engine.run_coherence_check",
            new_callable=AsyncMock,
            return_value={"unresolved": [], "auto_fixed": [], "passed": True},
        ), patch(
            "app.reliability.layer4_coherence.barrel_validator.validate_barrels",
            return_value={"valid": True, "missing": []},
        ), patch(
            "app.reliability.layer4_coherence.seam_checker.check_seams",
            return_value={"mismatches": []},
        ):
            report = await agent.review(state)

        # All Layer 8 reports present
        layer8_keys = ["visual_regression", "sast", "perf_budget", "accessibility", "dead_code", "seed"]
        for key in layer8_keys:
            assert key in report, f"Missing Layer 8 key: {key}"
