from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import uuid

from app.core.database import get_write_session
from app.models.coherence_report import CoherenceReport

logger = logging.getLogger(__name__)


async def run_coherence_check(build_id: uuid.UUID, generated_files: dict[str, str]) -> dict:
    """Run file coherence check on generated TypeScript/React files.

    CRITICAL: Called ONLY from ReviewAgent (build agent 10). Never from agents 1-9.

    1. Write .ts/.tsx files to temp dir
    2. Parse exports/imports via regex (ts-morph subprocess in production)
    3. Auto-fix: levenshtein ≤2 typos, case mismatches
    4. Escalate: missing source files, wrong export names
    5. Store CoherenceReport via get_write_session()
    6. Clean up temp in finally block
    """
    tmp_dir: str | None = None
    try:
        # 1. Write files to temp dir
        tmp_dir = tempfile.mkdtemp(prefix="forge_coherence_")
        ts_files = _write_files_to_temp(tmp_dir, generated_files)

        if not ts_files:
            report = _build_report(build_id, [], [], 0, 0, True)
            await _store_report(report)
            return report

        # 2. Parse exports and imports
        exports_map = _parse_exports(tmp_dir, ts_files)
        imports_list = _parse_imports(tmp_dir, ts_files)

        # 3+4. Check coherence: auto-fix typos, escalate missing
        auto_fixes: list[dict] = []
        critical_errors: list[dict] = []

        for imp in imports_list:
            source_file = imp["source_file"]
            imported_from = imp["from_module"]
            imported_names = imp["names"]

            # Resolve target file
            target = _resolve_import_path(tmp_dir, source_file, imported_from)
            if target is None:
                critical_errors.append({
                    "type": "missing_source",
                    "file": source_file,
                    "import": imported_from,
                    "message": f"Cannot resolve import '{imported_from}' from {source_file}",
                })
                continue

            # Check each imported name
            available = exports_map.get(target, set())
            for name in imported_names:
                if name in available:
                    continue  # OK

                # Try auto-fix: case mismatch
                case_match = _find_case_match(name, available)
                if case_match:
                    auto_fixes.append({
                        "type": "case_mismatch",
                        "file": source_file,
                        "wrong": name,
                        "correct": case_match,
                    })
                    continue

                # Try auto-fix: levenshtein ≤2
                close_match = _find_close_match(name, available, max_distance=2)
                if close_match:
                    auto_fixes.append({
                        "type": "typo",
                        "file": source_file,
                        "wrong": name,
                        "correct": close_match,
                        "distance": _levenshtein(name, close_match),
                    })
                    continue

                # Escalate
                critical_errors.append({
                    "type": "wrong_export",
                    "file": source_file,
                    "import": imported_from,
                    "name": name,
                    "available": sorted(available),
                    "message": f"'{name}' not exported from {imported_from}",
                })

        passed = len(critical_errors) == 0

        # 5. Store report
        report = _build_report(
            build_id, critical_errors, auto_fixes,
            len(critical_errors), len(auto_fixes), passed,
        )
        await _store_report(report)

        logger.info(
            "Coherence check: %d errors, %d auto-fixes, passed=%s",
            len(critical_errors), len(auto_fixes), passed,
        )
        return report

    finally:
        # 6. Clean up temp dir
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _write_files_to_temp(tmp_dir: str, files: dict[str, str]) -> list[str]:
    """Write .ts/.tsx files to temp directory. Returns list of relative paths."""
    written: list[str] = []
    for path, content in files.items():
        if not path.endswith((".ts", ".tsx", ".js", ".jsx")):
            continue
        full = os.path.join(tmp_dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        written.append(path)
    return written


# ── Export parsing ───────────────────────────────────────────────

_EXPORT_RE = re.compile(
    r"export\s+(?:default\s+)?(?:function|const|class|type|interface|enum|let|var)\s+(\w+)"
)
_EXPORT_NAMED_RE = re.compile(r"export\s*\{([^}]+)\}")
# export default X (bare identifier, not caught by _EXPORT_RE)
_EXPORT_DEFAULT_RE = re.compile(r"export\s+default\s+(\w+)\s*[;\n]")


def _parse_exports(tmp_dir: str, files: list[str]) -> dict[str, set[str]]:
    """Map file path → set of exported names."""
    exports: dict[str, set[str]] = {}
    for rel_path in files:
        full = os.path.join(tmp_dir, rel_path)
        try:
            with open(full) as f:
                content = f.read()
        except OSError:
            continue

        names: set[str] = set()
        for m in _EXPORT_RE.finditer(content):
            names.add(m.group(1))
        for m in _EXPORT_NAMED_RE.finditer(content):
            for name in m.group(1).split(","):
                # Handle "Foo as Bar" → export name is "Bar", original is "Foo"
                parts = name.strip().split(" as ")
                original = parts[0].strip()
                alias = parts[-1].strip()
                if alias:
                    names.add(alias)
                if original and original != alias:
                    names.add(original)
        for m in _EXPORT_DEFAULT_RE.finditer(content):
            names.add(m.group(1))
            names.add("default")
        # If file has any "export default" at all, mark 'default' as exported
        if re.search(r"export\s+default\s+", content):
            names.add("default")
        exports[rel_path] = names
    return exports


# ── Import parsing ───────────────────────────────────────────────

# Matches:
#   import { A, B } from '...'
#   import X from '...'
#   import X, { A, B } from '...'   (default + named)
#   import type { A } from '...'    (type imports)
_IMPORT_NAMED_RE = re.compile(
    r"import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]"
)
_IMPORT_DEFAULT_RE = re.compile(
    r"import\s+(?:type\s+)?(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
)
_IMPORT_DEFAULT_AND_NAMED_RE = re.compile(
    r"import\s+(?:type\s+)?(\w+)\s*,\s*\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]"
)


def _parse_imports(tmp_dir: str, files: list[str]) -> list[dict]:
    """List all imports from local modules."""
    imports: list[dict] = []
    for rel_path in files:
        full = os.path.join(tmp_dir, rel_path)
        try:
            with open(full) as f:
                content = f.read()
        except OSError:
            continue

        # Track what we've already parsed to avoid duplicates
        parsed_lines: set[int] = set()

        # 1. import Default, { Named } from '...' (most specific first)
        for m in _IMPORT_DEFAULT_AND_NAMED_RE.finditer(content):
            if m.start() in parsed_lines:
                continue
            parsed_lines.add(m.start())
            default_name = m.group(1)
            named_str = m.group(2)
            from_mod = m.group(3)

            if not from_mod.startswith((".", "/")):
                continue

            names: list[str] = [default_name]
            for n in named_str.split(","):
                n = n.strip().split(" as ")[0].strip()
                if n:
                    names.append(n)

            imports.append({
                "source_file": rel_path,
                "from_module": from_mod,
                "names": names,
            })

        # 2. import { Named } from '...' or import type { Named } from '...'
        for m in _IMPORT_NAMED_RE.finditer(content):
            if m.start() in parsed_lines:
                continue
            parsed_lines.add(m.start())
            named_str = m.group(1)
            from_mod = m.group(2)

            if not from_mod.startswith((".", "/")):
                continue

            names = []
            for n in named_str.split(","):
                n = n.strip().split(" as ")[0].strip()
                if n:
                    names.append(n)

            imports.append({
                "source_file": rel_path,
                "from_module": from_mod,
                "names": names,
            })

        # 3. import Default from '...'
        for m in _IMPORT_DEFAULT_RE.finditer(content):
            if m.start() in parsed_lines:
                continue
            parsed_lines.add(m.start())
            default_name = m.group(1)
            from_mod = m.group(2)

            if not from_mod.startswith((".", "/")):
                continue

            # Skip if this is actually part of a "import X, { Y } from" that was already caught
            imports.append({
                "source_file": rel_path,
                "from_module": from_mod,
                "names": [default_name],
            })

    return imports


# ── Import resolution ────────────────────────────────────────────

def _resolve_import_path(tmp_dir: str, source_file: str, import_path: str) -> str | None:
    """Resolve a relative import to a file path."""
    source_dir = os.path.dirname(source_file)
    resolved = os.path.normpath(os.path.join(source_dir, import_path))

    extensions = ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"]
    for ext in extensions:
        candidate = resolved + ext
        if os.path.isfile(os.path.join(tmp_dir, candidate)):
            return candidate
    return None


# ── Fuzzy matching ───────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(b)]


def _find_case_match(name: str, available: set[str]) -> str | None:
    """Find a case-insensitive match."""
    lower = name.lower()
    for candidate in available:
        if candidate.lower() == lower:
            return candidate
    return None


def _find_close_match(name: str, available: set[str], max_distance: int = 2) -> str | None:
    """Find closest match within max_distance."""
    best: str | None = None
    best_dist = max_distance + 1
    for candidate in available:
        d = _levenshtein(name, candidate)
        if d <= max_distance and d < best_dist:
            best = candidate
            best_dist = d
    return best


# ── Report helpers ───────────────────────────────────────────────

def _build_report(
    build_id: uuid.UUID,
    critical_errors: list[dict],
    auto_fixes: list[dict],
    error_count: int,
    fix_count: int,
    passed: bool,
) -> dict:
    return {
        "build_id": str(build_id),
        "critical_errors": error_count,
        "auto_fixes": fix_count,
        "passed": passed,
        "report_data": {
            "errors": critical_errors,
            "fixes": auto_fixes,
        },
    }


async def _store_report(report: dict) -> None:
    """Store coherence report in DB via get_write_session()."""
    try:
        async with get_write_session() as session:
            row = CoherenceReport(
                build_id=uuid.UUID(report["build_id"]),
                critical_errors=report["critical_errors"],
                auto_fixes=report["auto_fixes"],
                report_data=report["report_data"],
                passed=report["passed"],
            )
            session.add(row)
    except Exception as e:
        logger.warning("Failed to store coherence report: %s", e)
