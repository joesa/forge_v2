"""Layer 8e — Dead Code Detector.

ts-prune static analysis on generated TypeScript code.
WARNING ONLY — never fails the build.

Called from ReviewAgent only.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DeadCodeItem:
    """A single unused export."""

    file: str
    line: int
    symbol: str
    export_type: str  # "function" | "class" | "const" | "type" | "interface" | "default"


@dataclass
class DeadCodeReport:
    """Dead code detection report. WARNING ONLY — never fails build."""

    passed: bool = True  # Always True — never fails
    total_unused: int = 0
    items: list[DeadCodeItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Export/import tracking ───────────────────────────────────────

_EXPORT_PATTERN = re.compile(
    r"export\s+(?:"
    r"(?:default\s+)?(?:function|class|const|let|var|type|interface|enum)\s+(\w+)"  # named
    r"|default\s+(\w+)"  # export default identifier
    r"|{\s*([^}]+)\s*}"  # export { a, b, c }
    r")",
)

_REEXPORT_PATTERN = re.compile(
    r"export\s+(?:"
    r"{\s*([^}]+)\s*}\s+from"  # export { x } from
    r"|\*\s+from"  # export * from
    r")",
)

_IMPORT_PATTERN = re.compile(
    r"import\s+(?:"
    r"(\w+)"  # default import
    r"|{\s*([^}]+)\s*}"  # named imports
    r"|(\w+)\s*,\s*{\s*([^}]+)\s*}"  # default + named
    r")\s+from\s+['\"]([^'\"]+)['\"]",
)

_TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}

# Symbols that are entry points and should not be flagged
_ENTRY_POINT_PATTERNS = {
    "App", "main", "index", "Root", "Layout", "default",
}


def _parse_exports(filepath: str, content: str) -> list[tuple[str, int, str]]:
    """Parse exported symbols from a file.

    Returns list of (symbol_name, line_number, export_type).
    """
    exports: list[tuple[str, int, str]] = []
    lines = content.split("\n")

    for line_no, line in enumerate(lines, 1):
        # export default function/class/const
        match = re.search(
            r"export\s+default\s+(?:function|class|const|let|var)\s+(\w+)", line
        )
        if match:
            exports.append((match.group(1), line_no, "default"))
            continue

        # export default <identifier>
        match = re.search(r"export\s+default\s+(\w+)\s*;?\s*$", line)
        if match:
            exports.append((match.group(1), line_no, "default"))
            continue

        # export function/class/const/type/interface/enum
        match = re.search(
            r"export\s+(function|class|const|let|var|type|interface|enum)\s+(\w+)", line
        )
        if match:
            exports.append((match.group(2), line_no, match.group(1)))
            continue

        # export { a, b, c }  (not re-exports)
        match = re.search(r"export\s+{\s*([^}]+)\s*}\s*;?\s*$", line)
        if match and "from" not in line:
            for name in match.group(1).split(","):
                name = name.strip().split(" as ")[0].strip()
                if name:
                    exports.append((name, line_no, "const"))

    return exports


def _parse_imports(content: str) -> set[str]:
    """Parse all imported symbol names from content."""
    imported: set[str] = set()

    for match in _IMPORT_PATTERN.finditer(content):
        # default import
        if match.group(1):
            imported.add(match.group(1))
        # named imports
        if match.group(2):
            for name in match.group(2).split(","):
                name = name.strip().split(" as ")[-1].strip()
                if name:
                    imported.add(name)
        # default + named
        if match.group(3):
            imported.add(match.group(3))
        if match.group(4):
            for name in match.group(4).split(","):
                name = name.strip().split(" as ")[-1].strip()
                if name:
                    imported.add(name)

    # Also catch JSX usage: <ComponentName
    for match in re.finditer(r"<(\w+)(?:\s|/|>)", content):
        tag = match.group(1)
        if tag[0].isupper():  # React components
            imported.add(tag)

    return imported


def _parse_reexports(content: str) -> set[str]:
    """Parse re-exported symbols."""
    reexported: set[str] = set()

    for match in _REEXPORT_PATTERN.finditer(content):
        if match.group(1):
            for name in match.group(1).split(","):
                name = name.strip().split(" as ")[0].strip()
                if name:
                    reexported.add(name)

    # export * from '...' re-exports everything — we can't easily track
    if "export * from" in content:
        reexported.add("__star_reexport__")

    return reexported


async def run_dead_code_detection(
    generated_files: dict[str, str],
) -> dict:
    """Detect unused exports in generated TypeScript/JS files.

    WARNING ONLY — never fails the build.

    Args:
        generated_files: Dict of filepath → content.

    Returns:
        Dict with passed (always True), total_unused, items, warnings.
    """
    report = DeadCodeReport()

    # Step 1: Collect all exports per file
    file_exports: dict[str, list[tuple[str, int, str]]] = {}
    for filepath, content in generated_files.items():
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in _TS_EXTENSIONS:
            continue
        if not isinstance(content, str):
            continue
        exports = _parse_exports(filepath, content)
        if exports:
            file_exports[filepath] = exports

    if not file_exports:
        return _report_to_dict(report)

    # Step 2: Collect all imports across all files
    all_imported: set[str] = set()
    has_star_reexport = False
    for content in generated_files.values():
        if not isinstance(content, str):
            continue
        all_imported.update(_parse_imports(content))
        if "__star_reexport__" in _parse_reexports(content):
            has_star_reexport = True

    # If there's a star re-export, we can't be certain — skip
    if has_star_reexport:
        report.warnings.append(
            "Star re-exports detected — dead code analysis may be incomplete"
        )

    # Step 3: Find unused exports
    for filepath, exports in file_exports.items():
        for symbol, line_no, export_type in exports:
            # Skip entry points
            if symbol in _ENTRY_POINT_PATTERNS:
                continue
            # Skip if the file is an index/barrel file
            basename = os.path.basename(filepath)
            if basename.startswith("index."):
                continue

            if symbol not in all_imported:
                report.items.append(DeadCodeItem(
                    file=filepath,
                    line=line_no,
                    symbol=symbol,
                    export_type=export_type,
                ))

    report.total_unused = len(report.items)
    if report.total_unused > 0:
        report.warnings.append(
            f"{report.total_unused} unused exports detected (warning only)"
        )

    # NEVER fail — warning only
    report.passed = True

    logger.info(
        "Dead code: %d unused exports — WARNING ONLY (build not affected)",
        report.total_unused,
    )

    return _report_to_dict(report)


def _report_to_dict(report: DeadCodeReport) -> dict:
    """Convert report to plain dict."""
    return {
        "passed": report.passed,
        "total_unused": report.total_unused,
        "items": [
            {
                "file": item.file,
                "line": item.line,
                "symbol": item.symbol,
                "export_type": item.export_type,
            }
            for item in report.items
        ],
        "warnings": report.warnings,
    }
