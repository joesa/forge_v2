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
        build_id = uuid.UUID(state.get("pipeline_id", str(uuid.uuid4())))

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

        # Gates
        g7 = validate_g7(state)
        g8 = validate_g8(state)
        g11 = validate_g11(state)
        g12 = validate_g12(state)

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
