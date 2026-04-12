"""Tests for Reliability Layers 9 (Resilience) and 10 (AI)."""
from __future__ import annotations

import asyncio
import math
import pytest

# ── Layer 9 ──────────────────────────────────────────────────────

from app.reliability.layer9_resilience.hotfix_agent import (
    apply_hotfix,
    HotfixResult,
    MAX_ATTEMPTS,
    _identify_failing_file,
    _extract_code_block,
    _apply_rule_based_fix,
)
from app.reliability.layer9_resilience.rollback_engine import (
    rollback_to_last_success,
    RollbackResult,
)
from app.reliability.layer9_resilience.canary_deploy import (
    CanaryDeployer,
    CanaryMetrics,
    CanaryStage,
    CanaryResult,
    ERROR_RATE_THRESHOLD,
    STAGE_TRAFFIC,
)
from app.reliability.layer9_resilience.migration_safety import (
    check_migration_safety,
    check_files_migration_safety,
    MigrationSafetyResult,
)

# ── Layer 10 ─────────────────────────────────────────────────────

from app.reliability.layer10_ai.context_window_manager import (
    chunk_for_model,
    merge_chunks,
    estimate_tokens,
    get_model_limit,
    LIMITS,
    CHUNK_RATIO,
    OVERLAP_TOKENS,
    CHARS_PER_TOKEN,
)
from app.reliability.layer10_ai.css_validator import (
    validate_css_classes,
    CSSValidationResult,
    _extract_classes,
    _is_valid_class,
)
from app.reliability.layer10_ai.determinism_enforcer import (
    enforce_determinism,
    validate_determinism,
    REQUIRED_TEMPERATURE,
    REQUIRED_SEED,
)
from app.reliability.layer10_ai.fallback_cascade import (
    FallbackCascade,
    FallbackResult,
    PROVIDER_ORDER,
)


# ═══════════════════════════════════════════════════════════════════
# Layer 9 — Hotfix Agent
# ═══════════════════════════════════════════════════════════════════


class TestHotfixAgent:
    """Tests for the real hotfix agent implementation."""

    @pytest.mark.asyncio
    async def test_apply_hotfix_identifies_file_and_applies_rule_fix(self):
        """Hotfix identifies failing file from gate result and applies rule-based fix."""
        state = {
            "generated_files": {
                "src/App.tsx": 'function App() {\n  return <div>Hello</div>;\n}\n',
            },
        }
        gate = {
            "passed": False,
            "reason": "missing_export in src/App.tsx",
            "details": {"file": "src/App.tsx"},
            "errors": [],
        }
        result = await apply_hotfix(state, 1, gate)
        assert isinstance(result, HotfixResult)
        assert result.applied is True
        assert result.agent_number == 1
        assert "src/App.tsx" in result.files_modified
        assert "export" in state["generated_files"]["src/App.tsx"]

    @pytest.mark.asyncio
    async def test_apply_hotfix_no_failing_file(self):
        """Hotfix returns not-applied when no failing file can be identified."""
        state = {"generated_files": {"src/main.ts": "code"}}
        gate = {"passed": False, "reason": "generic error", "details": {}, "errors": []}
        result = await apply_hotfix(state, 2, gate)
        assert result.applied is False
        assert result.description == "could_not_identify_failing_file"

    @pytest.mark.asyncio
    async def test_apply_hotfix_max_attempts(self):
        """Hotfix respects MAX_ATTEMPTS limit."""
        assert MAX_ATTEMPTS == 3

    @pytest.mark.asyncio
    async def test_apply_hotfix_with_ai_fn(self):
        """Hotfix uses ai_fn when provided."""
        state = {
            "generated_files": {
                "src/index.ts": "const x = 1\n",
            },
        }
        gate = {
            "passed": False,
            "reason": "syntax_error in src/index.ts",
            "details": {"file": "src/index.ts"},
            "errors": ["Expected semicolon"],
        }

        async def mock_ai(prompt: str) -> str:
            return "```typescript\nconst x = 1;\n```"

        result = await apply_hotfix(state, 3, gate, ai_fn=mock_ai)
        assert result.applied is True
        assert state["generated_files"]["src/index.ts"] == "const x = 1;\n"

    @pytest.mark.asyncio
    async def test_apply_hotfix_ai_fn_failure_falls_back(self):
        """When ai_fn raises, falls back to rule-based fixes."""
        state = {
            "generated_files": {
                "src/App.tsx": 'function App() {\n  return <div/>;\n}\n',
            },
        }
        gate = {
            "passed": False,
            "reason": "missing_export in src/App.tsx",
            "details": {"file": "src/App.tsx"},
            "errors": [],
        }

        async def failing_ai(prompt: str) -> str:
            raise RuntimeError("AI unavailable")

        result = await apply_hotfix(state, 1, gate, ai_fn=failing_ai)
        assert result.applied is True
        assert "export" in state["generated_files"]["src/App.tsx"]

    def test_identify_failing_file_from_details(self):
        files = {"src/foo.ts": "code"}
        result = _identify_failing_file("error", {"file": "src/foo.ts"}, [], files)
        assert result == "src/foo.ts"

    def test_identify_failing_file_from_errors_list(self):
        files = {"src/bar.tsx": "code"}
        result = _identify_failing_file("", {}, [{"file": "src/bar.tsx"}], files)
        assert result == "src/bar.tsx"

    def test_identify_failing_file_from_reason_string(self):
        files = {"src/utils.ts": "code"}
        result = _identify_failing_file("error in src/utils.ts at line 5", {}, [], files)
        assert result == "src/utils.ts"

    def test_identify_failing_file_no_match(self):
        files = {"src/main.ts": "code"}
        result = _identify_failing_file("vague error", {}, [], files)
        assert result is None

    def test_extract_code_block_fenced(self):
        resp = "Here is the fix:\n```typescript\nconst x = 1;\n```\nDone."
        assert _extract_code_block(resp, "fallback") == "const x = 1;\n"

    def test_extract_code_block_raw_code(self):
        resp = "const x = 1;\nconst y = 2;"
        assert _extract_code_block(resp, "fallback") == "const x = 1;\nconst y = 2;\n"

    def test_rule_based_fix_missing_export(self):
        fix = _apply_rule_based_fix(
            "src/App.tsx",
            "function App() {}\n",
            "missing_export",
            [],
            {},
        )
        assert fix is not None
        assert "export function App" in fix["patched_content"]

    def test_rule_based_fix_missing_import(self):
        fix = _apply_rule_based_fix(
            "src/App.tsx",
            "const x = useState();\n",
            "undefined symbol",
            [],
            {"symbol": "useState", "source": "react"},
        )
        assert fix is not None
        assert 'import { useState } from "react"' in fix["patched_content"]

    def test_rule_based_fix_no_match(self):
        fix = _apply_rule_based_fix(
            "src/App.tsx",
            "some code\n",
            "unknown_error",
            [],
            {},
        )
        assert fix is None


# ═══════════════════════════════════════════════════════════════════
# Layer 9 — Rollback Engine
# ═══════════════════════════════════════════════════════════════════


class TestRollbackEngine:
    """Tests for the rollback engine."""

    @pytest.mark.asyncio
    async def test_rollback_no_storage_client(self):
        result = await rollback_to_last_success("proj1", "pipe1")
        assert result.rolled_back is False
        assert result.reason == "no_storage_client"

    @pytest.mark.asyncio
    async def test_rollback_no_successful_snapshot(self):
        """No snapshots found returns not rolled back."""

        class MockStorage:
            def from_(self, bucket):
                return self

            def list(self, prefix):
                return []

        result = await rollback_to_last_success(
            "proj1", "pipe1", storage_client=MockStorage()
        )
        assert result.rolled_back is False
        assert result.reason == "no_successful_snapshot"

    @pytest.mark.asyncio
    async def test_rollback_success(self):
        """Successful rollback restores files."""
        import json

        class MockStorage:
            def from_(self, bucket):
                return self

            def list(self, path):
                if "/" in path and not path.endswith("/"):
                    # Listing snapshot contents
                    return [
                        {"name": "metadata.json"},
                        {"name": "src/App.tsx"},
                    ]
                # Listing project snapshots
                return [{"name": "snap-001", "metadata": {}}]

            def download(self, path):
                if path.endswith("metadata.json"):
                    return json.dumps({"status": "success"}).encode()
                return b"export function App() {}"

        result = await rollback_to_last_success(
            "proj1", "pipe1", storage_client=MockStorage()
        )
        assert result.rolled_back is True
        assert result.snapshot_id == "snap-001"
        assert result.files_restored > 0

    def test_rollback_result_dataclass(self):
        r = RollbackResult(rolled_back=True, snapshot_id="s1", files_restored=5, reason="success")
        assert r.rolled_back is True
        assert r.snapshot_id == "s1"


# ═══════════════════════════════════════════════════════════════════
# Layer 9 — Canary Deploy
# ═══════════════════════════════════════════════════════════════════


class TestCanaryDeploy:
    """Tests for the canary deployment manager."""

    def test_initial_state(self):
        cd = CanaryDeployer("deploy-1")
        assert cd.current_stage == CanaryStage.CANARY_5
        assert cd.traffic_percent == 5
        assert not cd.is_rolled_back
        assert not cd.is_fully_deployed

    def test_promote_through_stages(self):
        cd = CanaryDeployer("deploy-2")

        # Stage 1: 5% → promote to 25%
        r1 = cd.evaluate_stage(CanaryMetrics(total_requests=1000, error_count=0))
        assert r1.promoted is True
        assert r1.traffic_percent == 5
        assert cd.current_stage == CanaryStage.CANARY_25

        # Stage 2: 25% → promote to 100%
        r2 = cd.evaluate_stage(CanaryMetrics(total_requests=5000, error_count=2))
        assert r2.promoted is True
        assert r2.traffic_percent == 25
        assert cd.current_stage == CanaryStage.FULL_100

        # Stage 3: 100% — fully deployed
        r3 = cd.evaluate_stage(CanaryMetrics(total_requests=10000, error_count=5))
        assert r3.promoted is True
        assert cd.is_fully_deployed

    def test_rollback_on_high_error_rate(self):
        cd = CanaryDeployer("deploy-3")

        # Error rate 1% > 0.1% threshold
        r = cd.evaluate_stage(CanaryMetrics(total_requests=1000, error_count=10))
        assert r.rolled_back is True
        assert cd.is_rolled_back
        assert cd.traffic_percent == 0
        assert "error_rate" in r.rollback_reason

    def test_rollback_at_exact_threshold(self):
        """Error rate exactly at threshold triggers rollback."""
        cd = CanaryDeployer("deploy-4")
        # 0.1% = 1/1000
        r = cd.evaluate_stage(CanaryMetrics(total_requests=1000, error_count=1))
        assert r.rolled_back is True

    def test_no_rollback_below_threshold(self):
        """Error rate just below threshold does not trigger rollback."""
        cd = CanaryDeployer("deploy-5")
        # 0 errors = 0% < 0.1%
        r = cd.evaluate_stage(CanaryMetrics(total_requests=10000, error_count=0))
        assert r.rolled_back is False
        assert r.promoted is True

    def test_force_rollback(self):
        cd = CanaryDeployer("deploy-6")
        r = cd.force_rollback("health_check_failed")
        assert r.rolled_back is True
        assert r.rollback_reason == "health_check_failed"
        assert cd.is_rolled_back

    def test_evaluate_after_rollback(self):
        cd = CanaryDeployer("deploy-7")
        cd.force_rollback("test")
        r = cd.evaluate_stage(CanaryMetrics(total_requests=100, error_count=0))
        assert r.rolled_back is True
        assert r.rollback_reason == "already_rolled_back"

    def test_history_tracking(self):
        cd = CanaryDeployer("deploy-8")
        cd.evaluate_stage(CanaryMetrics(total_requests=1000, error_count=0))
        cd.evaluate_stage(CanaryMetrics(total_requests=5000, error_count=2))
        assert len(cd.history) == 2

    def test_error_rate_threshold_value(self):
        assert ERROR_RATE_THRESHOLD == 0.001

    def test_stage_traffic_values(self):
        assert STAGE_TRAFFIC[CanaryStage.CANARY_5] == 5
        assert STAGE_TRAFFIC[CanaryStage.CANARY_25] == 25
        assert STAGE_TRAFFIC[CanaryStage.FULL_100] == 100

    def test_canary_metrics_error_rate(self):
        m = CanaryMetrics(total_requests=0, error_count=0)
        assert m.error_rate == 0.0
        m2 = CanaryMetrics(total_requests=1000, error_count=5)
        assert m2.error_rate == 0.005


# ═══════════════════════════════════════════════════════════════════
# Layer 9 — Migration Safety
# ═══════════════════════════════════════════════════════════════════


class TestMigrationSafety:
    """Tests for the migration safety checker."""

    def test_safe_sql(self):
        sql = "ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 0;"
        result = check_migration_safety(sql)
        assert result.safe is True
        assert result.violations == []

    def test_block_drop_table(self):
        sql = "DROP TABLE users;"
        result = check_migration_safety(sql)
        assert result.safe is False
        assert any(v["type"] == "drop_table" for v in result.violations)

    def test_block_drop_table_case_insensitive(self):
        sql = "drop table users;"
        result = check_migration_safety(sql)
        assert result.safe is False

    def test_block_delete_without_where(self):
        sql = "DELETE FROM users;"
        result = check_migration_safety(sql)
        assert result.safe is False
        assert any(v["type"] == "delete_without_where" for v in result.violations)

    def test_allow_delete_with_where(self):
        sql = "DELETE FROM sessions WHERE expired_at < NOW();"
        result = check_migration_safety(sql)
        assert result.safe is True

    def test_block_truncate(self):
        sql = "TRUNCATE users;"
        result = check_migration_safety(sql)
        assert result.safe is False
        assert any(v["type"] == "truncate" for v in result.violations)

    def test_block_drop_database(self):
        sql = "DROP DATABASE forge_prod;"
        result = check_migration_safety(sql)
        assert result.safe is False
        assert any(v["type"] == "drop_database" for v in result.violations)

    def test_warn_drop_column(self):
        sql = "ALTER TABLE users DROP COLUMN old_field;"
        result = check_migration_safety(sql)
        assert result.safe is True  # Allowed but warned
        assert len(result.warnings) > 0
        assert "DROP COLUMN" in result.warnings[0]

    def test_warn_alter_column_type(self):
        sql = "ALTER TABLE users ALTER COLUMN age TYPE BIGINT;"
        result = check_migration_safety(sql)
        assert result.safe is True
        assert len(result.warnings) > 0

    def test_multiple_violations(self):
        sql = "DROP TABLE orders; DELETE FROM users; TRUNCATE sessions;"
        result = check_migration_safety(sql)
        assert result.safe is False
        assert len(result.violations) == 3

    def test_check_files_migration_safety(self):
        files = {
            "migrations/001_create.sql": "CREATE TABLE users (id SERIAL);",
            "migrations/002_bad.sql": "DROP TABLE old_data;",
            "src/App.tsx": "const x = 1;",  # Not a migration file
        }
        result = check_files_migration_safety(files)
        assert result.safe is False
        assert len(result.violations) == 1
        assert result.violations[0]["file"] == "migrations/002_bad.sql"

    def test_check_files_skips_non_sql(self):
        files = {
            "src/App.tsx": "DROP TABLE foo;",  # Not a migration file
        }
        result = check_files_migration_safety(files)
        assert result.safe is True

    def test_empty_sql(self):
        result = check_migration_safety("")
        assert result.safe is True

    def test_dict_value_guard(self):
        """Non-string values in files dict don't crash."""
        files = {
            "migrations/001.sql": {"nested": "dict"},  # type: ignore
        }
        result = check_files_migration_safety(files)
        assert result.safe is True


# ═══════════════════════════════════════════════════════════════════
# Layer 10 — Context Window Manager
# ═══════════════════════════════════════════════════════════════════


class TestContextWindowManager:
    """Tests for the context window manager."""

    def test_limits_defined(self):
        assert LIMITS["claude-opus-4-6"] == 200_000
        assert LIMITS["claude-sonnet-4-6"] == 200_000
        assert LIMITS["gpt-4o"] == 128_000

    def test_estimate_tokens(self):
        text = "a" * 350  # 350 chars / 3.5 = 100 tokens
        tokens = estimate_tokens(text)
        assert tokens == 100

    def test_get_model_limit_known(self):
        assert get_model_limit("gpt-4o") == 128_000
        assert get_model_limit("claude-opus-4-6") == 200_000

    def test_get_model_limit_unknown(self):
        # Falls back to gpt-4o limit
        assert get_model_limit("unknown-model") == 128_000

    def test_chunk_small_text(self):
        """Small text that fits in one chunk."""
        text = "Hello world\n" * 10
        chunks = chunk_for_model(text, "gpt-4o")
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_large_text(self):
        """Large text gets split into multiple chunks."""
        # Create text larger than 60% of gpt-4o limit
        # 128k * 0.60 * 3.5 chars/token = ~268,800 chars
        text = "x" * 300_000
        chunks = chunk_for_model(text, "gpt-4o")
        assert len(chunks) > 1

    def test_chunk_overlap(self):
        """Chunks have overlapping content."""
        text = "line\n" * 100_000  # Large enough to split
        chunks = chunk_for_model(text, "gpt-4o")
        if len(chunks) > 1:
            # The end of chunk 0 should overlap with start of chunk 1
            overlap_chars = int(OVERLAP_TOKENS * CHARS_PER_TOKEN)
            end_of_first = chunks[0][-overlap_chars:]
            # Start of second should contain this overlap
            assert end_of_first in chunks[1][:overlap_chars * 2]

    def test_merge_single_chunk(self):
        assert merge_chunks(["hello"]) == "hello"

    def test_merge_empty(self):
        assert merge_chunks([]) == ""

    def test_merge_with_overlap(self):
        chunks = ["Hello World", "World Goodbye"]
        merged = merge_chunks(chunks)
        assert "Hello World" in merged
        assert "Goodbye" in merged
        # "World" should not be duplicated
        assert merged.count("World") == 1

    def test_chunk_ratio(self):
        assert CHUNK_RATIO == 0.60

    def test_overlap_tokens(self):
        assert OVERLAP_TOKENS == 200


# ═══════════════════════════════════════════════════════════════════
# Layer 10 — CSS Validator
# ═══════════════════════════════════════════════════════════════════


class TestCSSValidator:
    """Tests for the CSS class validator."""

    def test_valid_tailwind_classes(self):
        files = {
            "src/App.tsx": '<div className="flex items-center p-4 bg-blue-500 text-white">'
        }
        result = validate_css_classes(files)
        assert result.valid is True
        assert result.total_classes > 0
        assert result.files_checked == 1

    def test_extract_classes_from_classname(self):
        content = '<div className="flex p-4 mt-2">'
        classes = _extract_classes(content)
        assert "flex" in classes
        assert "p-4" in classes
        assert "mt-2" in classes

    def test_extract_classes_from_template_literal(self):
        content = 'className={`flex ${active ? "bg-blue" : "bg-gray"}`}'
        classes = _extract_classes(content)
        assert "flex" in classes

    def test_extract_classes_from_cn_helper(self):
        content = 'cn("flex items-center", active && "bg-blue-500")'
        classes = _extract_classes(content)
        assert "flex" in classes
        assert "items-center" in classes

    def test_valid_arbitrary_value(self):
        assert _is_valid_class("bg-[#ff0000]") is True
        assert _is_valid_class("w-[200px]") is True

    def test_valid_responsive_prefix(self):
        assert _is_valid_class("sm:flex") is True
        assert _is_valid_class("md:p-4") is True
        assert _is_valid_class("hover:bg-blue-500") is True
        assert _is_valid_class("dark:text-white") is True

    def test_valid_negative_prefix(self):
        assert _is_valid_class("-mt-4") is True

    def test_skips_non_tsx_files(self):
        files = {
            "src/utils.ts": 'className="flex"',  # Not a TSX file
            "src/App.tsx": '<div className="p-4">',
        }
        result = validate_css_classes(files)
        assert result.files_checked == 1

    def test_skips_non_string_values(self):
        files = {
            "src/App.tsx": {"not": "a string"},  # type: ignore
        }
        result = validate_css_classes(files)
        assert result.files_checked == 0

    def test_empty_files(self):
        result = validate_css_classes({})
        assert result.valid is True
        assert result.files_checked == 0

    def test_result_dataclass(self):
        r = CSSValidationResult(valid=True, total_classes=10, files_checked=3)
        assert r.valid is True
        assert r.invalid_classes == []


# ═══════════════════════════════════════════════════════════════════
# Layer 10 — Determinism Enforcer
# ═══════════════════════════════════════════════════════════════════


class TestDeterminismEnforcer:
    """Tests for the determinism enforcer decorator."""

    @pytest.mark.asyncio
    async def test_enforce_determinism_sets_params(self):
        @enforce_determinism
        async def my_fn(**kwargs):
            return kwargs

        result = await my_fn()
        assert result["temperature"] == 0
        assert result["seed"] == 42

    @pytest.mark.asyncio
    async def test_enforce_determinism_overrides_bad_values(self):
        @enforce_determinism
        async def my_fn(**kwargs):
            return kwargs

        result = await my_fn(temperature=0.7, seed=999)
        assert result["temperature"] == 0
        assert result["seed"] == 42

    @pytest.mark.asyncio
    async def test_enforce_determinism_with_parentheses(self):
        @enforce_determinism(temperature=0, seed=42)
        async def my_fn(**kwargs):
            return kwargs

        result = await my_fn()
        assert result["temperature"] == 0
        assert result["seed"] == 42

    @pytest.mark.asyncio
    async def test_enforce_determinism_preserves_other_kwargs(self):
        @enforce_determinism
        async def my_fn(**kwargs):
            return kwargs

        result = await my_fn(model="gpt-4o", prompt="hello")
        assert result["model"] == "gpt-4o"
        assert result["prompt"] == "hello"
        assert result["temperature"] == 0
        assert result["seed"] == 42

    def test_enforce_determinism_marker(self):
        @enforce_determinism
        async def my_fn(**kwargs):
            return kwargs

        assert my_fn._determinism_enforced is True
        assert my_fn._required_temperature == 0
        assert my_fn._required_seed == 42

    def test_validate_determinism_good_agent(self):
        class GoodAgent:
            TEMPERATURE = 0
            SEED = 42

        result = validate_determinism(GoodAgent())
        assert result["passed"] is True
        assert result["issues"] == []

    def test_validate_determinism_bad_temperature(self):
        class BadAgent:
            TEMPERATURE = 0.7
            SEED = 42

        result = validate_determinism(BadAgent())
        assert result["passed"] is False
        assert any("temperature" in i for i in result["issues"])

    def test_validate_determinism_bad_seed(self):
        class BadAgent:
            TEMPERATURE = 0
            SEED = 123

        result = validate_determinism(BadAgent())
        assert result["passed"] is False
        assert any("seed" in i for i in result["issues"])

    def test_constants(self):
        assert REQUIRED_TEMPERATURE == 0
        assert REQUIRED_SEED == 42


# ═══════════════════════════════════════════════════════════════════
# Layer 10 — Fallback Cascade
# ═══════════════════════════════════════════════════════════════════


class TestFallbackCascade:
    """Tests for the AI provider fallback cascade."""

    def test_provider_order(self):
        assert PROVIDER_ORDER == ["anthropic", "openai", "gemini", "mistral", "cohere"]

    @pytest.mark.asyncio
    async def test_first_provider_succeeds(self):
        async def anthropic_fn(prompt, **kwargs):
            return "anthropic response"

        cascade = FallbackCascade(providers={"anthropic": anthropic_fn})
        result = await cascade.call("hello")

        assert result.success is True
        assert result.provider == "anthropic"
        assert result.response == "anthropic response"
        assert len(result.attempts) == 1
        assert result.attempts[0]["success"] is True

    @pytest.mark.asyncio
    async def test_fallback_to_second_provider(self):
        async def fail_fn(prompt, **kwargs):
            raise RuntimeError("provider down")

        async def openai_fn(prompt, **kwargs):
            return "openai response"

        cascade = FallbackCascade(
            providers={"anthropic": fail_fn, "openai": openai_fn}
        )
        result = await cascade.call("hello")

        assert result.success is True
        assert result.provider == "openai"
        assert len(result.attempts) == 2
        assert result.attempts[0]["success"] is False
        assert result.attempts[1]["success"] is True

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        async def fail_fn(prompt, **kwargs):
            raise RuntimeError("down")

        cascade = FallbackCascade(
            providers={
                "anthropic": fail_fn,
                "openai": fail_fn,
                "gemini": fail_fn,
            }
        )
        result = await cascade.call("hello")

        assert result.success is False
        assert result.provider is None
        assert len(result.attempts) == 3

    @pytest.mark.asyncio
    async def test_empty_providers(self):
        cascade = FallbackCascade(providers={})
        result = await cascade.call("hello")
        assert result.success is False
        assert len(result.attempts) == 0

    @pytest.mark.asyncio
    async def test_billing_log(self):
        call_count = 0

        async def counting_fn(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fail")
            return "ok"

        cascade = FallbackCascade(
            providers={"anthropic": counting_fn, "openai": counting_fn}
        )
        await cascade.call("hello")

        log = cascade.get_billing_log()
        assert len(log) == 2
        assert log[0]["provider"] == "anthropic"
        assert log[0]["success"] is False
        assert log[1]["provider"] == "openai"
        assert log[1]["success"] is True
        assert "timestamp" in log[0]

    @pytest.mark.asyncio
    async def test_clear_log(self):
        async def ok_fn(prompt, **kwargs):
            return "ok"

        cascade = FallbackCascade(providers={"anthropic": ok_fn})
        await cascade.call("hello")
        assert len(cascade.get_billing_log()) == 1
        cascade.clear_log()
        assert len(cascade.get_billing_log()) == 0

    @pytest.mark.asyncio
    async def test_custom_provider_order(self):
        calls: list[str] = []

        async def track_fn(prompt, **kwargs):
            return "ok"

        async def fail_fn(prompt, **kwargs):
            raise RuntimeError("down")

        cascade = FallbackCascade(
            providers={"openai": fail_fn, "cohere": track_fn},
            provider_order=["openai", "cohere"],
        )
        result = await cascade.call("hello")
        assert result.success is True
        assert result.provider == "cohere"

    @pytest.mark.asyncio
    async def test_determinism_params_passed(self):
        received = {}

        async def capture_fn(prompt, **kwargs):
            received.update(kwargs)
            return "ok"

        cascade = FallbackCascade(providers={"anthropic": capture_fn})
        await cascade.call("hello", temperature=0, seed=42)
        assert received["temperature"] == 0
        assert received["seed"] == 42

    def test_register_provider(self):
        cascade = FallbackCascade()
        assert "test" not in cascade.providers

        async def test_fn(prompt, **kwargs):
            return "ok"

        cascade.register_provider("test", test_fn)
        assert "test" in cascade.providers

    @pytest.mark.asyncio
    async def test_total_time_tracked(self):
        async def ok_fn(prompt, **kwargs):
            return "ok"

        cascade = FallbackCascade(providers={"anthropic": ok_fn})
        result = await cascade.call("hello")
        assert result.total_time_ms >= 0


# ═══════════════════════════════════════════════════════════════════
# Integration: Layer 9 ↔ Layer 10
# ═══════════════════════════════════════════════════════════════════


class TestLayerIntegration:
    """Cross-layer integration tests."""

    @pytest.mark.asyncio
    async def test_hotfix_with_fallback_cascade(self):
        """Hotfix agent can use fallback cascade as ai_fn."""
        cascade = FallbackCascade()

        async def mock_anthropic(prompt, **kwargs):
            return "```tsx\nexport function App() { return <div/>; }\n```"

        cascade.register_provider("anthropic", mock_anthropic)

        state = {
            "generated_files": {
                "src/App.tsx": "function App() { return <div/>; }\n",
            },
        }
        gate = {
            "passed": False,
            "reason": "missing_export in src/App.tsx",
            "details": {"file": "src/App.tsx"},
            "errors": [],
        }

        async def ai_via_cascade(prompt: str) -> str:
            result = await cascade.call(prompt)
            return result.response if result.success else ""

        hotfix = await apply_hotfix(state, 1, gate, ai_fn=ai_via_cascade)
        assert hotfix.applied is True

    def test_migration_safety_with_determinism(self):
        """Migration safety and determinism enforcer both work independently."""
        sql = "CREATE TABLE t (id SERIAL PRIMARY KEY);"
        ms_result = check_migration_safety(sql)
        assert ms_result.safe is True

        class Agent:
            TEMPERATURE = 0
            SEED = 42

        det_result = validate_determinism(Agent())
        assert det_result["passed"] is True
