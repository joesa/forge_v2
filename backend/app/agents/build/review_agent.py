"""Agent 10: Review — VALIDATES ONLY. Layer 4 coherence, gates, snapshot, mark COMPLETED."""
from __future__ import annotations

import logging
import uuid

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState
from app.agents.validators import validate_g7, validate_g8, validate_g11, validate_g12
from app.reliability.layer4_coherence.file_coherence_engine import run_coherence_check
from app.reliability.layer4_coherence.barrel_validator import validate_barrels
from app.reliability.layer4_coherence.seam_checker import check_seams
from app.reliability.layer8_verification.visual_regression import run_visual_regression
from app.reliability.layer8_verification.sast_scanner import run_sast_scan
from app.reliability.layer8_verification.perf_budget import run_perf_budget
from app.reliability.layer8_verification.accessibility_audit import run_accessibility_audit
from app.reliability.layer8_verification.dead_code_detector import run_dead_code_detection
from app.reliability.layer8_verification.seed_generator import run_seed_generator

logger = logging.getLogger(__name__)


class ReviewAgent(BaseBuildAgent):
    """Agent 10 — validates the full build, never modifies files.

    File coherence engine runs HERE ONLY (Architecture Rule 7).
    """

    name = "review"
    agent_number = 10

    async def _run(self, state: PipelineState) -> dict[str, str]:
        """Returns empty dict — ReviewAgent does not generate files."""
        return {}

    async def review(self, state: PipelineState) -> dict:
        """Run all validation layers and return a review report.

        Returns dict with keys: passed, coherence, barrels, seams, gates.
        """
        generated_files = state.get("generated_files", {})
        build_id = uuid.UUID(state.get("build_id") or state.get("pipeline_id", str(uuid.uuid4())))

        report: dict = {"passed": True, "issues": []}

        # Layer 4a: File coherence engine (import/export validation)
        coherence_report = await run_coherence_check(build_id, generated_files)
        report["coherence"] = coherence_report
        if coherence_report.get("unresolved"):
            report["issues"].append(
                f"coherence: {len(coherence_report['unresolved'])} unresolved imports"
            )

        # Layer 4b: Barrel validation
        barrel_result = validate_barrels(generated_files)
        report["barrels"] = barrel_result
        if not barrel_result.get("valid", True):
            report["issues"].append(
                f"barrels: {len(barrel_result.get('missing', []))} missing exports"
            )

        # Layer 4c: Seam check (frontend↔backend routes)
        seam_result = check_seams(generated_files)
        report["seams"] = seam_result
        if seam_result.get("mismatches"):
            report["issues"].append(
                f"seams: {len(seam_result['mismatches'])} route mismatches"
            )

        # ── Layer 8: Verification suite ────────────────────────
        # Order: visual_regression → sast → perf → a11y → dead_code → seed

        build_id_str = str(build_id)

        # 8a: Visual regression (Playwright screenshots)
        visual_report = await run_visual_regression(
            build_id=build_id_str,
            generated_files=generated_files,
            preview_url=state.get("preview_url"),
        )
        report["visual_regression"] = visual_report
        if not visual_report.get("passed", True):
            report["issues"].append(
                f"visual_regression: {visual_report.get('diffs', 0)} screenshot diffs"
            )

        # 8b: SAST scanner (Semgrep + detect-secrets) — critical/high → G11 failure
        sast_report = await run_sast_scan(generated_files)
        report["sast"] = sast_report
        if not sast_report.get("passed", True):
            report["issues"].append(
                f"sast: {sast_report.get('critical', 0)} critical, "
                f"{sast_report.get('high', 0)} high findings"
            )

        # 8c: Performance budget (Lighthouse CI)
        perf_report = await run_perf_budget(generated_files)
        report["perf_budget"] = perf_report
        if not perf_report.get("passed", True):
            report["issues"].append(
                f"perf_budget: {len(perf_report.get('violations', []))} violations"
            )

        # 8d: Accessibility audit (axe-core WCAG 2.1 AA)
        a11y_report = await run_accessibility_audit(generated_files)
        report["accessibility"] = a11y_report
        if not a11y_report.get("passed", True):
            report["issues"].append(
                f"accessibility: {a11y_report.get('critical', 0)} critical violations"
            )

        # 8e: Dead code detector — WARNING ONLY, never fails
        dead_code_report = await run_dead_code_detection(generated_files)
        report["dead_code"] = dead_code_report
        # Never fails the build — warnings only

        # 8f: Seed data generator
        seed_report = await run_seed_generator(generated_files)
        report["seed"] = seed_report

        # Merge seed files into generated_files
        if seed_report.get("seed_files"):
            state.setdefault("generated_files", {}).update(seed_report["seed_files"])

        # ── Gates ────────────────────────────────────────────────
        g7 = validate_g7(state)
        g8 = validate_g8(state)
        g11 = validate_g11(state)
        g12 = validate_g12(state)

        # G11: incorporate SAST results — critical/high → failure
        if not sast_report.get("passed", True):
            g11 = {
                "passed": False,
                "reason": (
                    f"SAST: {sast_report.get('critical', 0)} critical, "
                    f"{sast_report.get('high', 0)} high security findings"
                ),
            }

        report["gates"] = {
            "g7": g7,
            "g8": g8,
            "g11": g11,
            "g12": g12,
        }

        for gate_name, gate_result in report["gates"].items():
            if not gate_result.get("passed", False):
                report["passed"] = False
                report["issues"].append(f"{gate_name}: {gate_result.get('reason', 'failed')}")

        if report["issues"]:
            report["passed"] = False
            logger.warning("ReviewAgent found %d issues: %s", len(report["issues"]), report["issues"])
        else:
            logger.info("ReviewAgent: all checks passed")

        return report
