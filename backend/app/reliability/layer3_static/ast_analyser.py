"""Layer 3 — Static AST Analysis.

Detect null refs, unhandled async, missing error boundaries in TS/TSX files.
Uses regex-based analysis (no ts-morph dependency — runs server-side in Python).
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Patterns ─────────────────────────────────────────────────────

# Nullable access without optional chaining: foo.bar where foo could be null
_NULLABLE_ACCESS = re.compile(
    r"""
    (?:                              # match variable declarations that might be null
      (?:const|let|var)\s+(\w+)      # capture var name
      \s*(?::\s*[^=]*\|\s*null)?     # optional type annotation with | null
      \s*=\s*                        # assignment
      (?:
        null                         # literal null
        |undefined                   # literal undefined
        |.*\?\.\w+                   # optional chain (result might be undefined)
        |.*\.find\(                  # .find() returns T | undefined
        |.*\.get\(                   # Map.get() returns T | undefined
        |.*as\s+\w+\s*\|\s*null     # cast to nullable
      )
    )
    """,
    re.VERBOSE,
)

# Accessing .property on potentially null variable without ?. or null check
_UNSAFE_ACCESS = re.compile(r"(\w+)\.(\w+)")

# Unhandled async: async function or await without try/catch in scope
_ASYNC_NO_CATCH = re.compile(
    r"(?:async\s+function\s+(\w+)|const\s+(\w+)\s*=\s*async)"
)

# Missing error boundary: pages exporting JSX without ErrorBoundary wrapper
_JSX_RETURN = re.compile(r"return\s*\(\s*<")
_ERROR_BOUNDARY_IMPORT = re.compile(r"import\s+.*ErrorBoundary")

# useEffect without cleanup for subscriptions
_USE_EFFECT_NO_CLEANUP = re.compile(
    r"useEffect\(\s*\(\)\s*=>\s*\{[^}]*"
    r"(?:subscribe|addEventListener|setInterval|setTimeout)"
    r"[^}]*\}\s*,",
)

# useState without type annotation (leads to implicit any)
_USE_STATE_NO_TYPE = re.compile(r"useState\(\s*\)")


class ASTIssue:
    """Represents a detected static analysis issue."""

    __slots__ = ("file", "line", "severity", "code", "message")

    def __init__(self, file: str, line: int, severity: str, code: str, message: str):
        self.file = file
        self.line = line
        self.severity = severity
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


def analyse_file(filepath: str, content: str) -> list[ASTIssue]:
    """Analyse a single TS/TSX file for common issues."""
    if not filepath.endswith((".ts", ".tsx")):
        return []

    issues: list[ASTIssue] = []
    lines = content.split("\n")
    is_page = filepath.startswith("src/pages/")
    is_tsx = filepath.endswith(".tsx")

    # Track nullable variables
    nullable_vars: set[str] = set()
    in_try_block = False
    brace_depth = 0
    try_depth = -1

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track brace depth for try/catch scope
        brace_depth += stripped.count("{") - stripped.count("}")
        if stripped.startswith("try"):
            in_try_block = True
            try_depth = brace_depth
        if in_try_block and brace_depth < try_depth:
            in_try_block = False
            try_depth = -1

        # Detect nullable variable declarations
        m = _NULLABLE_ACCESS.search(line)
        if m:
            var_name = m.group(1)
            if var_name:
                nullable_vars.add(var_name)

        # Detect | null or | undefined in type annotations
        if re.search(r":\s*\w+\s*\|\s*(?:null|undefined)", line):
            type_match = re.search(r"(?:const|let|var)\s+(\w+)\s*:", line)
            if type_match:
                nullable_vars.add(type_match.group(1))

        # Detect unsafe access on nullable vars
        for access_match in _UNSAFE_ACCESS.finditer(line):
            var = access_match.group(0)
            var_name = access_match.group(1)
            if var_name in nullable_vars and "?." not in line[max(0, access_match.start() - 2):access_match.end()]:
                # Exclude common safe patterns
                if not re.search(rf"if\s*\(\s*{re.escape(var_name)}\s*\)", line):
                    issues.append(ASTIssue(
                        filepath, i, "error", "NULL_REF",
                        f"Potentially null variable '{var_name}' accessed without optional chaining",
                    ))

        # Detect await without try/catch
        if "await " in stripped and not in_try_block and not stripped.startswith("//"):
            # Ignore top-level awaits in non-function context and simple assignments
            if not stripped.startswith("import") and not stripped.startswith("export"):
                issues.append(ASTIssue(
                    filepath, i, "warning", "UNHANDLED_ASYNC",
                    "await without try/catch — unhandled rejection risk",
                ))

        # useEffect without cleanup
        if _USE_EFFECT_NO_CLEANUP.search(line):
            issues.append(ASTIssue(
                filepath, i, "warning", "EFFECT_NO_CLEANUP",
                "useEffect with subscription/timer but no cleanup return",
            ))

        # useState without type
        if _USE_STATE_NO_TYPE.search(line):
            issues.append(ASTIssue(
                filepath, i, "warning", "UNTYPED_STATE",
                "useState() without type annotation — implicit any risk",
            ))

    # Page-level: missing ErrorBoundary
    if is_page and is_tsx:
        has_boundary = bool(_ERROR_BOUNDARY_IMPORT.search(content))
        has_jsx = bool(_JSX_RETURN.search(content))
        if has_jsx and not has_boundary:
            issues.append(ASTIssue(
                filepath, 1, "error", "MISSING_ERROR_BOUNDARY",
                "Page component returns JSX but does not import ErrorBoundary",
            ))

    return issues


def analyse_files(generated_files: dict[str, str]) -> dict:
    """Analyse all generated files.

    Returns:
        {
            "passed": bool,
            "total_issues": int,
            "errors": int,
            "warnings": int,
            "issues": [ASTIssue.to_dict(), ...],
        }
    """
    all_issues: list[ASTIssue] = []

    for filepath, content in generated_files.items():
        all_issues.extend(analyse_file(filepath, content))

    errors = sum(1 for i in all_issues if i.severity == "error")
    warnings = sum(1 for i in all_issues if i.severity == "warning")

    result = {
        "passed": errors == 0,
        "total_issues": len(all_issues),
        "errors": errors,
        "warnings": warnings,
        "issues": [i.to_dict() for i in all_issues],
    }

    logger.info(
        "AST analysis: %d errors, %d warnings across %d files",
        errors, warnings, len(generated_files),
    )
    return result
