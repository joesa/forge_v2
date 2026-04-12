"""Layer 3 — Import Graph Resolver.

Detects circular imports, missing files, and duplicate packages in generated code.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Import extraction patterns ───────────────────────────────────

# ES module: import X from './path'  /  import { X } from './path'
_ES_IMPORT = re.compile(
    r"""import\s+(?:
        (?:type\s+)?                           # optional 'type' keyword
        (?:\{[^}]*\}|\*\s+as\s+\w+|\w+)       # named / namespace / default
        \s+from\s+
    )?['"]([^'"]+)['"]""",
    re.VERBOSE,
)

# Dynamic import: import('./path')
_DYNAMIC_IMPORT = re.compile(r"import\(\s*['\"]([^'\"]+)['\"]\s*\)")

# require('./path')
_REQUIRE = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")

# Known extension resolution order
_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx", ".json", ""]
_INDEX_FILES = ["index.ts", "index.tsx", "index.js", "index.jsx"]


def _extract_imports(content: str) -> list[str]:
    """Extract all import specifiers from file content."""
    specifiers: list[str] = []
    for pattern in (_ES_IMPORT, _DYNAMIC_IMPORT, _REQUIRE):
        specifiers.extend(pattern.findall(content))
    return specifiers


def _is_relative(specifier: str) -> bool:
    return specifier.startswith(".") or specifier.startswith("/")


def _resolve_path(specifier: str, from_file: str, file_set: set[str]) -> str | None:
    """Resolve a relative import specifier to a file in the generated set.

    Tries extension and index file resolution.
    """
    if not _is_relative(specifier):
        return None  # External package — not our concern

    # Build base path relative to the importing file's directory
    from_dir = from_file.rsplit("/", 1)[0] if "/" in from_file else ""
    parts = specifier.split("/")
    resolved_parts = from_dir.split("/") if from_dir else []

    for part in parts:
        if part == ".":
            continue
        elif part == "..":
            if resolved_parts:
                resolved_parts.pop()
        else:
            resolved_parts.append(part)

    base = "/".join(resolved_parts)

    # Direct match
    if base in file_set:
        return base

    # Try extensions
    for ext in _EXTENSIONS:
        candidate = base + ext
        if candidate in file_set:
            return candidate

    # Try index files (directory import)
    for idx in _INDEX_FILES:
        candidate = f"{base}/{idx}"
        if candidate in file_set:
            return candidate

    return None


def resolve_import_graph(generated_files: dict[str, str]) -> dict:
    """Build and validate the import graph.

    Returns:
        {
            "passed": bool,
            "circular_imports": [[file, file, ...], ...],
            "missing_imports": [{"from": file, "specifier": str}, ...],
            "duplicate_packages": [{"package": str, "files": [str, ...]}, ...],
        }
    """
    file_set = set(generated_files.keys())
    graph: dict[str, set[str]] = defaultdict(set)
    missing_imports: list[dict[str, str]] = []
    package_usage: dict[str, list[str]] = defaultdict(list)

    # Build graph
    for filepath, content in generated_files.items():
        if not filepath.endswith((".ts", ".tsx", ".js", ".jsx")):
            continue

        specifiers = _extract_imports(content)

        for spec in specifiers:
            if _is_relative(spec):
                resolved = _resolve_path(spec, filepath, file_set)
                if resolved:
                    graph[filepath].add(resolved)
                else:
                    missing_imports.append({"from": filepath, "specifier": spec})
            else:
                # Track external package usage
                pkg_name = spec.split("/")[0]
                if pkg_name.startswith("@"):
                    pkg_name = "/".join(spec.split("/")[:2])
                package_usage[pkg_name].append(filepath)

    # Detect circular imports via DFS
    circular: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def _dfs(node: str) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                _dfs(neighbor)
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                circular.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for file in generated_files:
        if file not in visited and file.endswith((".ts", ".tsx", ".js", ".jsx")):
            _dfs(file)

    # Detect duplicate package versions (same package imported from different paths)
    # This only flags if a package appears with multiple version specifiers in package.json
    duplicate_packages: list[dict] = []
    pkg_json = generated_files.get("package.json", "")
    if pkg_json:
        import json
        try:
            pkg_data = json.loads(pkg_json)
            all_deps = {}
            all_deps.update(pkg_data.get("dependencies", {}))
            all_deps.update(pkg_data.get("devDependencies", {}))

            # Check for same package in both deps and devDeps
            deps_set = set(pkg_data.get("dependencies", {}).keys())
            dev_set = set(pkg_data.get("devDependencies", {}).keys())
            overlap = deps_set & dev_set
            for pkg in overlap:
                duplicate_packages.append({
                    "package": pkg,
                    "files": ["dependencies", "devDependencies"],
                })
        except (json.JSONDecodeError, AttributeError):
            pass

    passed = len(circular) == 0 and len(missing_imports) == 0

    result = {
        "passed": passed,
        "circular_imports": circular,
        "missing_imports": missing_imports,
        "duplicate_packages": duplicate_packages,
    }

    logger.info(
        "Import graph: %d circular, %d missing, %d duplicates — %s",
        len(circular), len(missing_imports), len(duplicate_packages),
        "PASS" if passed else "FAIL",
    )
    return result
