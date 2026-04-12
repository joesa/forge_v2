"""Layer 3 — Runtime Error Predictor.

Pattern-match common runtime errors that would crash the generated app.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class RuntimePattern:
    """A known runtime error pattern."""

    __slots__ = ("name", "pattern", "severity", "message", "fix_hint")

    def __init__(
        self,
        name: str,
        pattern: re.Pattern[str],
        severity: str,
        message: str,
        fix_hint: str,
    ):
        self.name = name
        self.pattern = pattern
        self.severity = severity
        self.message = message
        self.fix_hint = fix_hint


# ── Known runtime error patterns ─────────────────────────────────

RUNTIME_PATTERNS: list[RuntimePattern] = [
    RuntimePattern(
        "cannot_read_property",
        re.compile(r"(\w+)\.(\w+)\s*[=(]", re.MULTILINE),
        "info",  # Only flag when combined with nullable source
        "Potential 'Cannot read properties of undefined/null'",
        "Use optional chaining: obj?.prop",
    ),
    RuntimePattern(
        "max_update_depth",
        re.compile(
            r"useEffect\(\s*\(\)\s*=>\s*\{[^}]*set\w+\([^)]*\)[^}]*\}\s*\)\s*;",
        ),
        "error",
        "useEffect without deps array calling setState — causes infinite re-render (Maximum update depth exceeded)",
        "Add a dependency array: useEffect(() => { ... }, [deps])",
    ),
    RuntimePattern(
        "missing_key_prop",
        re.compile(r"\.map\(\s*(?:\([^)]*\)|\w+)\s*=>\s*(?:\(?\s*<[a-zA-Z]\w*)(?!.*\bkey\s*=)"),
        "warning",
        "JSX element in .map() likely missing key prop",
        "Add key={item.id} to the mapped element",
    ),
    RuntimePattern(
        "hooks_conditional",
        re.compile(
            r"if\s*\([^)]*\)\s*\{[^}]*(?:useState|useEffect|useCallback|useMemo|useRef)\s*\(",
        ),
        "error",
        "React Hook called conditionally — violates Rules of Hooks",
        "Move hooks to top level of the component",
    ),
    RuntimePattern(
        "async_useeffect",
        re.compile(r"useEffect\(\s*async\s"),
        "error",
        "async function passed directly to useEffect — returns Promise instead of cleanup",
        "Define async function inside useEffect and call it",
    ),
    RuntimePattern(
        "direct_state_mutation",
        re.compile(r"(\w+)\.push\(|(\w+)\.splice\(|(\w+)\[\w+\]\s*="),
        "warning",
        "Possible direct state mutation — React won't re-render",
        "Use spread operator or functional setState: setItems([...items, newItem])",
    ),
    RuntimePattern(
        "unhandled_promise",
        re.compile(r"(?:fetch|axios\.\w+|supabase\.\w+)\([^)]*\)(?!\s*\.then|\s*\.catch|\s*;?\s*$)"),
        "info",
        "Promise may not have error handling",
        "Add .catch() or wrap in try/catch",
    ),
    RuntimePattern(
        "json_parse_unguarded",
        re.compile(r"JSON\.parse\([^)]*\)(?!\s*catch)"),
        "warning",
        "JSON.parse without try/catch — throws on malformed input",
        "Wrap JSON.parse in try/catch",
    ),
    RuntimePattern(
        "innerhtml_xss",
        re.compile(r"dangerouslySetInnerHTML\s*=\s*\{"),
        "error",
        "dangerouslySetInnerHTML — XSS vulnerability risk",
        "Sanitize HTML with DOMPurify or use safe rendering",
    ),
    RuntimePattern(
        "localstorage_ssr",
        re.compile(r"(?:localStorage|sessionStorage)\.\w+\("),
        "warning",
        "localStorage/sessionStorage access — will crash in SSR/SSG",
        "Guard with typeof window !== 'undefined' check",
    ),
    RuntimePattern(
        "window_reference",
        re.compile(r"(?<!\btypeof\s)window\.(?!location)"),
        "info",
        "Direct window access without typeof guard",
        "Guard with typeof window !== 'undefined'",
    ),
    RuntimePattern(
        "empty_catch",
        re.compile(r"catch\s*\(\s*\w*\s*\)\s*\{\s*\}"),
        "warning",
        "Empty catch block — silently swallows errors",
        "Log the error or re-throw",
    ),
]


class PredictedError:
    """A predicted runtime error."""

    __slots__ = ("file", "line", "pattern_name", "severity", "message", "fix_hint")

    def __init__(
        self,
        file: str,
        line: int,
        pattern_name: str,
        severity: str,
        message: str,
        fix_hint: str,
    ):
        self.file = file
        self.line = line
        self.pattern_name = pattern_name
        self.severity = severity
        self.message = message
        self.fix_hint = fix_hint

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "pattern_name": self.pattern_name,
            "severity": self.severity,
            "message": self.message,
            "fix_hint": self.fix_hint,
        }


def predict_runtime_errors(generated_files: dict[str, str]) -> dict:
    """Scan generated files for patterns that predict runtime errors.

    Returns:
        {
            "passed": bool,
            "total_predictions": int,
            "errors": int,
            "warnings": int,
            "predictions": [PredictedError.to_dict(), ...]
        }
    """
    predictions: list[PredictedError] = []

    # Skip patterns that are too noisy on non-JS/TS files
    skip_patterns = {"cannot_read_property"}
    targeted_patterns = [p for p in RUNTIME_PATTERNS if p.name not in skip_patterns]

    for filepath, content in generated_files.items():
        if not filepath.endswith((".ts", ".tsx", ".js", ".jsx")):
            continue

        lines = content.split("\n")
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue

            for pattern in targeted_patterns:
                if pattern.pattern.search(line):
                    predictions.append(PredictedError(
                        file=filepath,
                        line=i,
                        pattern_name=pattern.name,
                        severity=pattern.severity,
                        message=pattern.message,
                        fix_hint=pattern.fix_hint,
                    ))

    errors = sum(1 for p in predictions if p.severity == "error")
    warnings = sum(1 for p in predictions if p.severity == "warning")

    result = {
        "passed": errors == 0,
        "total_predictions": len(predictions),
        "errors": errors,
        "warnings": warnings,
        "predictions": [p.to_dict() for p in predictions],
    }

    logger.info(
        "Runtime prediction: %d errors, %d warnings, %d info",
        errors, warnings, len(predictions) - errors - warnings,
    )
    return result
