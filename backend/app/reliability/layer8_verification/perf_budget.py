"""Layer 8c — Performance Budget Checker.

Lighthouse CI budget enforcement:
  - LCP  <= 2500ms
  - CLS  <= 0.1
  - FID  <= 100ms
  - Bundle size <= 500KB

Called from ReviewAgent only.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Budget targets ───────────────────────────────────────────────

@dataclass
class PerfBudget:
    """Performance budget thresholds."""

    lcp_ms: float = 2500.0  # Largest Contentful Paint
    cls: float = 0.1  # Cumulative Layout Shift
    fid_ms: float = 100.0  # First Input Delay
    bundle_kb: float = 500.0  # Total JS bundle size


@dataclass
class PerfViolation:
    """A single performance budget violation."""

    metric: str  # "lcp" | "cls" | "fid" | "bundle_size"
    actual: float
    budget: float
    unit: str  # "ms" | "" | "KB"
    message: str


@dataclass
class PerfReport:
    """Performance budget report."""

    passed: bool = True
    bundle_size_kb: float = 0.0
    estimated_lcp_ms: float = 0.0
    estimated_cls: float = 0.0
    estimated_fid_ms: float = 0.0
    violations: list[PerfViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Bundle size analysis ─────────────────────────────────────────

_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_HEAVY_IMPORTS = {
    "moment": 70,  # KB estimate
    "lodash": 70,
    "chart.js": 60,
    "three": 150,
    "d3": 80,
    "firebase": 100,
    "aws-sdk": 200,
    "@mui/material": 90,
    "antd": 120,
    "rxjs": 45,
}


def _estimate_bundle_size(generated_files: dict[str, str]) -> float:
    """Estimate total JS bundle size in KB from generated source.

    Accounts for:
    - Raw source size (with ~0.6x minification ratio)
    - Known heavy dependencies
    - Number of routes (code splitting benefit)
    """
    total_raw_bytes = 0
    heavy_imports_kb = 0.0
    route_count = 0
    seen_imports: set[str] = set()

    for filepath, content in generated_files.items():
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in _JS_EXTENSIONS:
            continue
        if not isinstance(content, str):
            continue

        total_raw_bytes += len(content.encode("utf-8"))

        # Detect heavy imports (import X from "pkg" or require("pkg"))
        for match in re.finditer(
            r'''(?:from|require\()\s*["']([^"']+)["']''', content
        ):
            pkg = match.group(1).split("/")[0]
            if pkg.startswith("@"):
                pkg = "/".join(match.group(1).split("/")[:2])
            if pkg in _HEAVY_IMPORTS and pkg not in seen_imports:
                seen_imports.add(pkg)
                heavy_imports_kb += _HEAVY_IMPORTS[pkg]

        # Count route definitions
        route_count += len(re.findall(r'path[=:]\s*["\']/', content))

    # Minification ratio + tree shaking
    minified_kb = (total_raw_bytes / 1024) * 0.6

    # Code splitting benefit: -5% per route beyond 3 (up to 40% max)
    split_discount = min(0.4, max(0, (route_count - 3) * 0.05))
    effective_kb = minified_kb * (1 - split_discount) + heavy_imports_kb

    return round(effective_kb, 1)


# ── LCP / CLS / FID estimation ───────────────────────────────────

def _estimate_lcp(generated_files: dict[str, str], bundle_kb: float) -> float:
    """Estimate LCP in ms based on bundle size and content patterns.

    Heuristic:
    - Base: 800ms (network + parse)
    - +2ms per KB of JS
    - +500ms if no lazy loading detected
    - +300ms if large images without lazy/priority
    """
    base_ms = 800.0
    js_penalty = bundle_kb * 2.0

    has_lazy = False
    has_large_images = False

    combined = " ".join(v for v in generated_files.values() if isinstance(v, str))
    if "lazy(" in combined or "React.lazy" in combined or 'loading="lazy"' in combined:
        has_lazy = True
    if "<img" in combined and 'loading="lazy"' not in combined:
        has_large_images = True

    lazy_penalty = 0.0 if has_lazy else 500.0
    image_penalty = 300.0 if has_large_images else 0.0

    return round(base_ms + js_penalty + lazy_penalty + image_penalty, 0)


def _estimate_cls(generated_files: dict[str, str]) -> float:
    """Estimate CLS based on content patterns.

    Heuristic:
    - Base: 0.02
    - +0.05 per image without explicit dimensions
    - +0.03 per dynamic content area without skeleton/placeholder
    - +0.02 per web font loaded
    """
    cls = 0.02
    combined = " ".join(v for v in generated_files.values() if isinstance(v, str))

    # Images without dimensions
    img_count = len(re.findall(r"<img\b(?![^>]*(?:width|height))[^>]*>", combined))
    cls += img_count * 0.05

    # Web fonts
    font_count = len(re.findall(r"@font-face|fonts\.googleapis", combined))
    cls += font_count * 0.02

    # Dynamic areas without skeleton
    dynamic = len(re.findall(r"(?:isLoading|loading)\s*[?&]{1,2}", combined))
    skeleton = len(re.findall(r"[Ss]keleton|placeholder|shimmer", combined))
    unhandled_dynamic = max(0, dynamic - skeleton)
    cls += unhandled_dynamic * 0.03

    return round(min(cls, 1.0), 3)


def _estimate_fid(bundle_kb: float) -> float:
    """Estimate FID in ms based on bundle size.

    Heuristic:
    - Base: 20ms
    - +0.15ms per KB of JS (main thread parse time)
    """
    return round(20.0 + bundle_kb * 0.15, 0)


# ── Main entry point ─────────────────────────────────────────────

async def run_perf_budget(
    generated_files: dict[str, str],
    *,
    budget: PerfBudget | None = None,
    lighthouse_results: dict | None = None,
) -> dict:
    """Check generated code against performance budgets.

    If lighthouse_results are provided (from actual Lighthouse run),
    uses those. Otherwise estimates from code analysis.

    Args:
        generated_files: Dict of filepath → content.
        budget: Custom budget thresholds (default: standard web vitals).
        lighthouse_results: Actual Lighthouse audit results if available.

    Returns:
        Dict with passed, bundle_size_kb, estimated_lcp_ms, etc.
    """
    if budget is None:
        budget = PerfBudget()

    report = PerfReport()

    if lighthouse_results:
        # Use actual Lighthouse data
        report.bundle_size_kb = lighthouse_results.get("bundle_size_kb", 0)
        report.estimated_lcp_ms = lighthouse_results.get("lcp_ms", 0)
        report.estimated_cls = lighthouse_results.get("cls", 0)
        report.estimated_fid_ms = lighthouse_results.get("fid_ms", 0)
    else:
        # Estimate from source analysis
        report.bundle_size_kb = _estimate_bundle_size(generated_files)
        report.estimated_lcp_ms = _estimate_lcp(generated_files, report.bundle_size_kb)
        report.estimated_cls = _estimate_cls(generated_files)
        report.estimated_fid_ms = _estimate_fid(report.bundle_size_kb)

    # Check budgets
    if report.estimated_lcp_ms > budget.lcp_ms:
        report.violations.append(PerfViolation(
            metric="lcp", actual=report.estimated_lcp_ms,
            budget=budget.lcp_ms, unit="ms",
            message=f"LCP {report.estimated_lcp_ms}ms exceeds budget {budget.lcp_ms}ms",
        ))

    if report.estimated_cls > budget.cls:
        report.violations.append(PerfViolation(
            metric="cls", actual=report.estimated_cls,
            budget=budget.cls, unit="",
            message=f"CLS {report.estimated_cls} exceeds budget {budget.cls}",
        ))

    if report.estimated_fid_ms > budget.fid_ms:
        report.violations.append(PerfViolation(
            metric="fid", actual=report.estimated_fid_ms,
            budget=budget.fid_ms, unit="ms",
            message=f"FID {report.estimated_fid_ms}ms exceeds budget {budget.fid_ms}ms",
        ))

    if report.bundle_size_kb > budget.bundle_kb:
        report.violations.append(PerfViolation(
            metric="bundle_size", actual=report.bundle_size_kb,
            budget=budget.bundle_kb, unit="KB",
            message=f"Bundle {report.bundle_size_kb}KB exceeds budget {budget.bundle_kb}KB",
        ))

    report.passed = len(report.violations) == 0

    logger.info(
        "Perf budget: bundle=%.1fKB LCP=%.0fms CLS=%.3f FID=%.0fms — %s",
        report.bundle_size_kb, report.estimated_lcp_ms,
        report.estimated_cls, report.estimated_fid_ms,
        "PASSED" if report.passed else f"FAILED ({len(report.violations)} violations)",
    )

    return _report_to_dict(report)


def _report_to_dict(report: PerfReport) -> dict:
    """Convert report to plain dict."""
    return {
        "passed": report.passed,
        "bundle_size_kb": report.bundle_size_kb,
        "estimated_lcp_ms": report.estimated_lcp_ms,
        "estimated_cls": report.estimated_cls,
        "estimated_fid_ms": report.estimated_fid_ms,
        "violations": [
            {
                "metric": v.metric,
                "actual": v.actual,
                "budget": v.budget,
                "unit": v.unit,
                "message": v.message,
            }
            for v in report.violations
        ],
        "warnings": report.warnings,
    }
