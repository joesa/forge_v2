"""Layer 8d — Accessibility Audit.

axe-core WCAG 2.1 AA compliance checking.
  - Critical violations → fail
  - Serious violations → warning

Called from ReviewAgent only.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Severity mapping ─────────────────────────────────────────────
# axe-core impact levels → our severity
IMPACT_FAIL = {"critical"}  # Fail the build
IMPACT_WARN = {"serious"}  # Warning only
IMPACT_INFO = {"moderate", "minor"}  # Informational


@dataclass
class A11yViolation:
    """A single accessibility violation."""

    rule_id: str
    impact: str  # "critical" | "serious" | "moderate" | "minor"
    file: str
    line: int
    element: str  # The offending HTML/JSX snippet
    message: str
    wcag: list[str] = field(default_factory=list)  # e.g. ["wcag2a", "wcag2aa"]


@dataclass
class A11yReport:
    """Full accessibility audit report."""

    passed: bool = True
    total_violations: int = 0
    critical: int = 0
    serious: int = 0
    moderate: int = 0
    minor: int = 0
    violations: list[A11yViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Built-in WCAG checks ────────────────────────────────────────

def _check_images_alt(filepath: str, content: str) -> list[A11yViolation]:
    """WCAG 1.1.1: Non-text content must have alt text."""
    violations: list[A11yViolation] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, 1):
        # <img without alt
        for match in re.finditer(r"<img\b([^>]*)>", line):
            attrs = match.group(1)
            if "alt=" not in attrs and "alt =" not in attrs:
                violations.append(A11yViolation(
                    rule_id="image-alt",
                    impact="critical",
                    file=filepath,
                    line=line_no,
                    element=match.group(0)[:80],
                    message="Images must have alternate text (WCAG 1.1.1)",
                    wcag=["wcag2a", "wcag111"],
                ))

    return violations


def _check_form_labels(filepath: str, content: str) -> list[A11yViolation]:
    """WCAG 1.3.1 / 4.1.2: Form inputs must have labels."""
    violations: list[A11yViolation] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, 1):
        # <input without aria-label, aria-labelledby, or id (for <label htmlFor>)
        for match in re.finditer(r"<input\b([^>]*)>", line):
            attrs = match.group(1)
            has_label = any(
                attr in attrs
                for attr in ["aria-label", "aria-labelledby", "id=", "placeholder="]
            )
            if not has_label and 'type="hidden"' not in attrs:
                violations.append(A11yViolation(
                    rule_id="label",
                    impact="critical",
                    file=filepath,
                    line=line_no,
                    element=match.group(0)[:80],
                    message="Form elements must have labels (WCAG 1.3.1)",
                    wcag=["wcag2a", "wcag131"],
                ))

    return violations


def _check_heading_order(filepath: str, content: str) -> list[A11yViolation]:
    """WCAG 1.3.1: Heading levels should increase by one."""
    violations: list[A11yViolation] = []

    headings = re.findall(r"<h([1-6])\b", content)
    prev_level = 0
    for i, level_str in enumerate(headings):
        level = int(level_str)
        if prev_level > 0 and level > prev_level + 1:
            # Find line number
            pattern = f"<h{level}\\b"
            line_no = 1
            for j, line in enumerate(content.split("\n"), 1):
                if re.search(pattern, line):
                    line_no = j
                    break

            violations.append(A11yViolation(
                rule_id="heading-order",
                impact="moderate",
                file=filepath,
                line=line_no,
                element=f"<h{level}>",
                message=f"Heading level skipped: h{prev_level} → h{level} (WCAG 1.3.1)",
                wcag=["wcag2a", "wcag131"],
            ))
        prev_level = level

    return violations


def _check_color_contrast_hints(filepath: str, content: str) -> list[A11yViolation]:
    """Heuristic check for potential color contrast issues."""
    violations: list[A11yViolation] = []
    lines = content.split("\n")

    # Check for light text on light backgrounds or dark on dark
    light_colors = {"#fff", "#ffffff", "#fafafa", "#f5f5f5", "white", "#eee", "#eeeeee"}
    dark_colors = {"#000", "#000000", "#111", "#222", "#333", "black", "#1a1a1a"}

    for line_no, line in enumerate(lines, 1):
        lower = line.lower()
        has_light_bg = any(c in lower for c in light_colors) and "background" in lower
        has_light_text = any(c in lower for c in light_colors) and "color" in lower and "background" not in lower

        if has_light_bg and has_light_text:
            violations.append(A11yViolation(
                rule_id="color-contrast",
                impact="serious",
                file=filepath,
                line=line_no,
                element=line.strip()[:80],
                message="Potential low contrast: light text on light background (WCAG 1.4.3)",
                wcag=["wcag2aa", "wcag143"],
            ))

    return violations


def _check_interactive_roles(filepath: str, content: str) -> list[A11yViolation]:
    """Check clickable non-button/link elements have roles."""
    violations: list[A11yViolation] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, 1):
        # onClick on div/span without role
        if re.search(r"<(?:div|span)\b[^>]*onClick", line):
            if 'role="button"' not in line and 'role="link"' not in line and "tabIndex" not in line:
                match = re.search(r"<(?:div|span)\b[^>]*>", line)
                violations.append(A11yViolation(
                    rule_id="interactive-role",
                    impact="serious",
                    file=filepath,
                    line=line_no,
                    element=(match.group(0) if match else line.strip())[:80],
                    message="Interactive elements must have appropriate ARIA roles (WCAG 4.1.2)",
                    wcag=["wcag2a", "wcag412"],
                ))

    return violations


def _check_lang_attribute(filepath: str, content: str) -> list[A11yViolation]:
    """WCAG 3.1.1: Page must have lang attribute."""
    violations: list[A11yViolation] = []

    if "<html" in content and 'lang=' not in content:
        violations.append(A11yViolation(
            rule_id="html-has-lang",
            impact="serious",
            file=filepath,
            line=1,
            element="<html>",
            message="<html> element must have a lang attribute (WCAG 3.1.1)",
            wcag=["wcag2a", "wcag311"],
        ))

    return violations


# ── Main entry point ─────────────────────────────────────────────

async def run_accessibility_audit(
    generated_files: dict[str, str],
    *,
    axe_results: dict | None = None,
) -> dict:
    """Run WCAG 2.1 AA audit on generated files.

    If axe_results are provided (from actual axe-core run), uses those.
    Otherwise performs static analysis on generated source.

    Critical violations → fail. Serious → warning only.

    Args:
        generated_files: Dict of filepath → content.
        axe_results: Actual axe-core results if available.

    Returns:
        Dict with passed, total_violations, critical, serious, etc.
    """
    report = A11yReport()

    if axe_results:
        return _parse_axe_results(axe_results)

    # Static analysis
    all_violations: list[A11yViolation] = []

    for filepath, content in generated_files.items():
        if not isinstance(content, str):
            continue
        if not _is_auditable(filepath):
            continue

        all_violations.extend(_check_images_alt(filepath, content))
        all_violations.extend(_check_form_labels(filepath, content))
        all_violations.extend(_check_heading_order(filepath, content))
        all_violations.extend(_check_color_contrast_hints(filepath, content))
        all_violations.extend(_check_interactive_roles(filepath, content))
        all_violations.extend(_check_lang_attribute(filepath, content))

    report.violations = all_violations
    report.total_violations = len(all_violations)
    report.critical = sum(1 for v in all_violations if v.impact == "critical")
    report.serious = sum(1 for v in all_violations if v.impact == "serious")
    report.moderate = sum(1 for v in all_violations if v.impact == "moderate")
    report.minor = sum(1 for v in all_violations if v.impact == "minor")

    # Critical → fail. Serious → warning only.
    if report.critical > 0:
        report.passed = False

    if report.serious > 0:
        report.warnings.append(
            f"{report.serious} serious a11y violations (WCAG 2.1 AA warnings)"
        )

    logger.info(
        "A11y audit: %d violations (C:%d S:%d M:%d m:%d) — %s",
        report.total_violations, report.critical, report.serious,
        report.moderate, report.minor,
        "PASSED" if report.passed else "FAILED",
    )

    return _report_to_dict(report)


def _is_auditable(filepath: str) -> bool:
    """Check if file should be audited for accessibility."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in {".tsx", ".jsx", ".html", ".vue", ".svelte"}


def _parse_axe_results(axe_results: dict) -> dict:
    """Parse actual axe-core results into our report format."""
    violations: list[A11yViolation] = []

    for v in axe_results.get("violations", []):
        impact = v.get("impact", "moderate")
        for node in v.get("nodes", []):
            violations.append(A11yViolation(
                rule_id=v.get("id", "unknown"),
                impact=impact,
                file="(runtime)",
                line=0,
                element=node.get("html", "")[:80],
                message=v.get("description", ""),
                wcag=[t.get("id", "") for t in v.get("tags", []) if "wcag" in t.get("id", "")],
            ))

    critical = sum(1 for v in violations if v.impact == "critical")
    serious = sum(1 for v in violations if v.impact == "serious")

    return {
        "passed": critical == 0,
        "total_violations": len(violations),
        "critical": critical,
        "serious": serious,
        "moderate": sum(1 for v in violations if v.impact == "moderate"),
        "minor": sum(1 for v in violations if v.impact == "minor"),
        "violations": [
            {
                "rule_id": v.rule_id,
                "impact": v.impact,
                "file": v.file,
                "line": v.line,
                "element": v.element,
                "message": v.message,
                "wcag": v.wcag,
            }
            for v in violations
        ],
        "warnings": [f"{serious} serious a11y violations"] if serious > 0 else [],
    }


def _report_to_dict(report: A11yReport) -> dict:
    """Convert report to plain dict."""
    return {
        "passed": report.passed,
        "total_violations": report.total_violations,
        "critical": report.critical,
        "serious": report.serious,
        "moderate": report.moderate,
        "minor": report.minor,
        "violations": [
            {
                "rule_id": v.rule_id,
                "impact": v.impact,
                "file": v.file,
                "line": v.line,
                "element": v.element,
                "message": v.message,
                "wcag": v.wcag,
            }
            for v in report.violations
        ],
        "warnings": report.warnings,
    }
