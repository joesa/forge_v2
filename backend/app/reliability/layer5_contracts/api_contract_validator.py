"""Layer 5 — API Contract Validator.

Validate generated route handlers against their OpenAPI spec.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ContractViolation:
    """A single contract violation between spec and implementation."""

    path: str
    method: str
    violation_type: str  # MISSING_ROUTE, MISSING_RESPONSE, WRONG_PARAM, etc.
    severity: str  # "error" | "warning"
    message: str


def validate_api_contracts(
    openapi_spec: dict,
    generated_files: dict[str, str],
) -> dict:
    """Validate generated route files against the OpenAPI spec.

    Returns {
        "passed": bool,
        "total_violations": int,
        "errors": int,
        "warnings": int,
        "violations": [ContractViolation, ...],
    }
    """
    violations: list[ContractViolation] = []

    spec_paths = openapi_spec.get("paths", {})
    if not spec_paths:
        return {
            "passed": True,
            "total_violations": 0,
            "errors": 0,
            "warnings": 0,
            "violations": [],
        }

    # Collect all route-like files
    route_files = {
        fp: content
        for fp, content in generated_files.items()
        if _is_route_file(fp)
    }

    # Collect all implemented routes from source
    implemented_routes = _extract_implemented_routes(route_files)

    # Check each spec path has a matching implementation
    for path, methods in spec_paths.items():
        for method, operation in methods.items():
            method_upper = method.upper()
            if method_upper in ("PARAMETERS", "SERVERS", "SUMMARY", "DESCRIPTION"):
                continue

            # Check route exists
            if not _route_implemented(path, method_upper, implemented_routes):
                violations.append(ContractViolation(
                    path=path,
                    method=method_upper,
                    violation_type="MISSING_ROUTE",
                    severity="error",
                    message=f"Route {method_upper} {path} defined in spec but not implemented",
                ))
                continue

            # Check required parameters
            params = operation.get("parameters", [])
            for param in params:
                if param.get("required", False):
                    param_name = param.get("name", "")
                    if not _param_used_in_routes(param_name, path, route_files):
                        violations.append(ContractViolation(
                            path=path,
                            method=method_upper,
                            violation_type="MISSING_PARAM",
                            severity="warning",
                            message=f"Required parameter '{param_name}' not found in implementation",
                        ))

            # Check request body referenced
            if "requestBody" in operation:
                if not _request_body_handled(path, method_upper, route_files):
                    violations.append(ContractViolation(
                        path=path,
                        method=method_upper,
                        violation_type="MISSING_REQUEST_BODY",
                        severity="warning",
                        message=f"Request body for {method_upper} {path} not handled in implementation",
                    ))

            # Check response codes
            responses = operation.get("responses", {})
            for status_code in responses:
                if status_code.startswith("4") or status_code.startswith("5"):
                    if not _error_response_handled(path, status_code, route_files):
                        violations.append(ContractViolation(
                            path=path,
                            method=method_upper,
                            violation_type="MISSING_ERROR_HANDLER",
                            severity="warning",
                            message=f"Error response {status_code} for {method_upper} {path} not handled",
                        ))

    # Check for unreferenced routes (implemented but not in spec)
    for route_path, route_method in implemented_routes:
        if not _spec_has_route(route_path, route_method, spec_paths):
            violations.append(ContractViolation(
                path=route_path,
                method=route_method,
                violation_type="EXTRA_ROUTE",
                severity="warning",
                message=f"Route {route_method} {route_path} implemented but not in spec",
            ))

    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")

    return {
        "passed": errors == 0,
        "total_violations": len(violations),
        "errors": errors,
        "warnings": warnings,
        "violations": [
            {
                "path": v.path,
                "method": v.method,
                "violation_type": v.violation_type,
                "severity": v.severity,
                "message": v.message,
            }
            for v in violations
        ],
    }


# ── Internal helpers ─────────────────────────────────────────────

_ROUTE_PATTERNS = [
    # Express-style: app.get('/path', ...)  or  router.post('/path', ...)
    re.compile(r'(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]'),
    # Next.js API routes — file-based routing convention
    re.compile(r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)'),
    # FastAPI-style: @router.get("/path")
    re.compile(r'@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]'),
]


def _is_route_file(filepath: str) -> bool:
    """Check if a file is likely a route handler."""
    lower = filepath.lower()
    return any(
        kw in lower
        for kw in ("route", "api", "endpoint", "handler", "controller")
    ) or lower.endswith(("/route.ts", "/route.tsx", "/route.js"))


def _extract_implemented_routes(
    route_files: dict[str, str],
) -> list[tuple[str, str]]:
    """Extract (path, METHOD) tuples from route files."""
    routes: list[tuple[str, str]] = []

    for filepath, content in route_files.items():
        for pattern in _ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                groups = match.groups()
                if len(groups) == 2:
                    method, path = groups
                    routes.append((path, method.upper()))
                elif len(groups) == 1:
                    # File-based routing (Next.js) — derive path from filepath
                    method = groups[0].upper()
                    path = _filepath_to_api_path(filepath)
                    routes.append((path, method))

    return routes


def _filepath_to_api_path(filepath: str) -> str:
    """Convert file path to API path for file-based routing."""
    # e.g. src/app/api/users/[id]/route.ts → /api/users/{id}
    path = filepath
    for prefix in ("src/app", "app", "pages"):
        if prefix in path:
            path = path[path.index(prefix) + len(prefix):]
            break
    # Remove /route.ts, /route.tsx etc.
    path = re.sub(r'/route\.(ts|tsx|js|jsx)$', '', path)
    # Convert [param] to {param}
    path = re.sub(r'\[([^\]]+)\]', r'{\1}', path)
    return path


def _route_implemented(
    spec_path: str,
    method: str,
    implemented_routes: list[tuple[str, str]],
) -> bool:
    """Check if a spec path+method is implemented."""
    normalised_spec = _normalise_path(spec_path)
    for imp_path, imp_method in implemented_routes:
        if imp_method == method and _normalise_path(imp_path) == normalised_spec:
            return True
    return False


def _spec_has_route(
    route_path: str,
    route_method: str,
    spec_paths: dict,
) -> bool:
    """Check if a route is defined in the spec."""
    normalised = _normalise_path(route_path)
    for spec_path, methods in spec_paths.items():
        if _normalise_path(spec_path) == normalised:
            if route_method.lower() in methods:
                return True
    return False


def _normalise_path(path: str) -> str:
    """Normalise path for comparison: /api/users/{id} → /api/users/:param."""
    path = path.strip("/")
    path = re.sub(r'\{[^}]+\}', ':param', path)
    path = re.sub(r'\[[^\]]+\]', ':param', path)
    path = re.sub(r':[a-zA-Z_]+', ':param', path)
    return "/" + path


def _param_used_in_routes(
    param_name: str,
    spec_path: str,
    route_files: dict[str, str],
) -> bool:
    """Check if a parameter name appears in route file content."""
    for content in route_files.values():
        if param_name in content:
            return True
    return False


def _request_body_handled(
    path: str,
    method: str,
    route_files: dict[str, str],
) -> bool:
    """Check if request body is referenced in route files."""
    body_patterns = ["req.body", "request.body", "body", "json()", "formData"]
    for content in route_files.values():
        if any(bp in content for bp in body_patterns):
            return True
    return False


def _error_response_handled(
    path: str,
    status_code: str,
    route_files: dict[str, str],
) -> bool:
    """Check if an error status code is handled in routes."""
    for content in route_files.values():
        if status_code in content:
            return True
    return False
