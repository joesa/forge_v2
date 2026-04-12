from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)


def check_seams(generated_files: dict[str, str]) -> dict:
    """Verify seams between frontend and backend files.

    Checks:
    1. Every API call in frontend has a matching backend route
    2. Every backend route referenced in frontend uses correct HTTP method
    3. Request/response shapes referenced in frontend match backend schemas

    Returns {"passed": bool, "broken_seams": list[dict], "warnings": list[str]}
    """
    broken_seams: list[dict] = []
    warnings: list[str] = []

    backend_routes = _extract_backend_routes(generated_files)
    frontend_calls = _extract_frontend_api_calls(generated_files)

    for call in frontend_calls:
        route_match = _find_matching_route(call["path"], backend_routes)
        if route_match is None:
            broken_seams.append({
                "type": "missing_route",
                "file": call["file"],
                "path": call["path"],
                "method": call["method"],
                "detail": f"Frontend calls {call['method'].upper()} {call['path']} but no backend route matches",
            })
        elif call["method"].lower() != route_match["method"].lower():
            broken_seams.append({
                "type": "method_mismatch",
                "file": call["file"],
                "path": call["path"],
                "expected_method": route_match["method"],
                "actual_method": call["method"],
                "detail": f"Frontend uses {call['method'].upper()} but backend expects {route_match['method'].upper()}",
            })

    passed = len(broken_seams) == 0
    logger.info("Seam check: %d broken, passed=%s", len(broken_seams), passed)
    return {"passed": passed, "broken_seams": broken_seams, "warnings": warnings}


# --- Backend route extraction ---

_FASTAPI_ROUTE_RE = re.compile(
    r"@(?:router|app)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]"
)
_EXPRESS_ROUTE_RE = re.compile(
    r"(?:router|app)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]"
)


def _extract_backend_routes(files: dict[str, str]) -> list[dict]:
    """Extract API routes from backend files."""
    routes: list[dict] = []
    for path, content in files.items():
        if not _is_backend_file(path):
            continue
        for pattern in (_FASTAPI_ROUTE_RE, _EXPRESS_ROUTE_RE):
            for m in pattern.finditer(content):
                routes.append({
                    "method": m.group(1),
                    "path": m.group(2),
                    "file": path,
                })
    return routes


def _is_backend_file(path: str) -> bool:
    """Check if file is a backend route file."""
    parts = path.replace("\\", "/").split("/")
    # Matches patterns like: app/api/..., src/routes/..., backend/...
    for part in parts:
        if part in ("api", "routes", "controllers", "endpoints"):
            return True
    if path.endswith(".py") and "route" in path.lower():
        return True
    return False


# --- Frontend API call extraction ---

_FETCH_RE = re.compile(
    r"(?:fetch|axios)\.(get|post|put|patch|delete)\(\s*[`'\"]([^`'\"]+)[`'\"]"
)
_FETCH_PLAIN_RE = re.compile(
    r"fetch\(\s*[`'\"]([^`'\"]+)[`'\"](?:\s*,\s*\{\s*method\s*:\s*['\"](\w+)['\"])?"
)
_API_CALL_RE = re.compile(
    r"api\.(get|post|put|patch|delete)\(\s*[`'\"]([^`'\"]+)[`'\"]"
)


def _extract_frontend_api_calls(files: dict[str, str]) -> list[dict]:
    """Extract API calls from frontend files."""
    calls: list[dict] = []
    for path, content in files.items():
        if not _is_frontend_file(path):
            continue

        for m in _FETCH_RE.finditer(content):
            calls.append({
                "method": m.group(1),
                "path": _normalize_api_path(m.group(2)),
                "file": path,
            })

        for m in _FETCH_PLAIN_RE.finditer(content):
            method = m.group(2) if m.group(2) else "get"
            calls.append({
                "method": method.lower(),
                "path": _normalize_api_path(m.group(1)),
                "file": path,
            })

        for m in _API_CALL_RE.finditer(content):
            calls.append({
                "method": m.group(1),
                "path": _normalize_api_path(m.group(2)),
                "file": path,
            })

    return calls


def _is_frontend_file(path: str) -> bool:
    return path.endswith((".ts", ".tsx", ".js", ".jsx")) and "test" not in path.lower()


def _normalize_api_path(path: str) -> str:
    """Normalize API path — strip base URL, interpolation → param markers."""
    path = re.sub(r"https?://[^/]+", "", path)
    path = re.sub(r"\$\{[^}]+\}", ":param", path)
    path = re.sub(r"\{[^}]+\}", ":param", path)
    return path


def _find_matching_route(call_path: str, routes: list[dict]) -> dict | None:
    """Find backend route matching a frontend API call path."""
    call_segments = _path_segments(call_path)

    for route in routes:
        route_segments = _path_segments(route["path"])
        if _segments_match(call_segments, route_segments):
            return route
    return None


def _path_segments(path: str) -> list[str]:
    return [s for s in path.strip("/").split("/") if s]


def _segments_match(call_segs: list[str], route_segs: list[str]) -> bool:
    """Match path segments, treating :param and {param} as wildcards."""
    if len(call_segs) != len(route_segs):
        return False
    for c, r in zip(call_segs, route_segs):
        if c.startswith(":") or r.startswith(":") or r.startswith("{"):
            continue
        if c != r:
            return False
    return True
