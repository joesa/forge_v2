from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Semver parsing ───────────────────────────────────────────────

_SEMVER_RE = re.compile(
    r"^(?P<op>[~^>=<]*)(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?(?:-(?P<pre>[a-zA-Z0-9.]+))?"
)


def _parse_semver(version: str) -> tuple[str, int, int, int]:
    """Parse a version string into (operator, major, minor, patch)."""
    m = _SEMVER_RE.match(version.strip())
    if not m:
        return ("", 0, 0, 0)
    return (
        m.group("op") or "",
        int(m.group("major") or 0),
        int(m.group("minor") or 0),
        int(m.group("patch") or 0),
    )


def _satisfies(version: str, constraint: str) -> bool:
    """Check if an exact version satisfies a constraint range.

    Supports ^, ~, >=, >, <=, <, and exact match.
    """
    _, v_maj, v_min, v_pat = _parse_semver(version)
    op, c_maj, c_min, c_pat = _parse_semver(constraint)

    if op == "^":
        # ^1.2.3 means >=1.2.3 <2.0.0; ^0.2.3 means >=0.2.3 <0.3.0
        if c_maj != 0:
            return v_maj == c_maj and (v_min, v_pat) >= (c_min, c_pat)
        return v_maj == 0 and v_min == c_min and v_pat >= c_pat
    elif op == "~":
        # ~1.2.3 means >=1.2.3 <1.3.0
        return v_maj == c_maj and v_min == c_min and v_pat >= c_pat
    elif op == ">=":
        return (v_maj, v_min, v_pat) >= (c_maj, c_min, c_pat)
    elif op == ">":
        return (v_maj, v_min, v_pat) > (c_maj, c_min, c_pat)
    elif op == "<=":
        return (v_maj, v_min, v_pat) <= (c_maj, c_min, c_pat)
    elif op == "<":
        return (v_maj, v_min, v_pat) < (c_maj, c_min, c_pat)
    else:
        # Exact or no-op — major must match, minor/patch >= constraint
        return (v_maj, v_min, v_pat) == (c_maj, c_min, c_pat)


# ── Known-good version pins for peer-dep ecosystems ─────────────
# These are battle-tested version sets that work together.

_PEER_RESOLUTIONS: dict[str, str] = {
    # React 18 ecosystem
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    # React Router v6
    "react-router-dom": "6.28.0",
    "@types/react-router-dom": "5.3.3",
    # TanStack Query v5
    "@tanstack/react-query": "5.62.0",
    # Zustand
    "zustand": "5.0.2",
}

# Known incompatible pairs: (package_a, package_b, reason)
_INCOMPATIBLE_PAIRS: list[tuple[str, str, str]] = [
    ("react-router-dom", "react-router", "Don't install both — react-router-dom re-exports react-router"),
    ("@emotion/react", "@emotion/css", "Pick one Emotion strategy, not both"),
]

# Packages that MUST share the same major version
_MAJOR_ALIGNED: list[tuple[str, str]] = [
    ("react", "react-dom"),
    ("react", "@types/react"),
    ("@tanstack/react-query", "@tanstack/react-query-devtools"),
    ("next", "eslint-config-next"),
]


def resolve_dependencies(dependencies: dict[str, str]) -> dict[str, str]:
    """Resolve npm dependency conflicts.

    1. Pin known peer-dep ecosystem packages to battle-tested versions
    2. Normalize version ranges — keep range operators for npm install
    3. Skip workspace:/file: local references
    4. Returns clean dependency dict
    """
    resolved: dict[str, str] = {}

    for pkg, version in dependencies.items():
        # Apply known resolutions for peer-dep ecosystems
        if pkg in _PEER_RESOLUTIONS:
            resolved[pkg] = _PEER_RESOLUTIONS[pkg]
            if version != _PEER_RESOLUTIONS[pkg]:
                logger.info("Pinned %s: %s → %s", pkg, version, _PEER_RESOLUTIONS[pkg])
            continue

        # Strip workspace: and file: protocols
        if version.startswith(("workspace:", "file:")):
            logger.warning("Skipping local reference %s: %s", pkg, version)
            continue

        # Keep valid semver ranges as-is for npm install (don't strip ^/~)
        if _SEMVER_RE.match(version.strip()):
            resolved[pkg] = version.strip()
        else:
            # Fallback: try to clean up
            cleaned = re.sub(r"^[\^~>=<]+", "", version).strip()
            if cleaned:
                resolved[pkg] = cleaned
            else:
                logger.warning("Unparseable version for %s: %s — skipping", pkg, version)

    return resolved


def detect_peer_conflicts(dependencies: dict[str, str]) -> list[str]:
    """Detect unresolvable dependency conflicts.

    Checks:
    1. Major version alignment for paired packages
    2. Known incompatible package combinations
    3. Duplicate scope packages (e.g. both @emotion/react and @emotion/css)
    """
    conflicts: list[str] = []

    # Check major-version alignment
    for pkg_a, pkg_b in _MAJOR_ALIGNED:
        ver_a = dependencies.get(pkg_a, "")
        ver_b = dependencies.get(pkg_b, "")
        if ver_a and ver_b:
            _, maj_a, _, _ = _parse_semver(ver_a)
            _, maj_b, _, _ = _parse_semver(ver_b)
            if maj_a != maj_b:
                conflicts.append(
                    f"{pkg_a}@{ver_a} vs {pkg_b}@{ver_b} major version mismatch"
                )

    # Check incompatible pairs
    for pkg_a, pkg_b, reason in _INCOMPATIBLE_PAIRS:
        if pkg_a in dependencies and pkg_b in dependencies:
            conflicts.append(f"{pkg_a} + {pkg_b}: {reason}")

    return conflicts


def check_range_compatibility(pkg: str, ranges: list[str]) -> dict:
    """Check if multiple version ranges for the same package can coexist.

    Used when multiple agents request different versions of the same package.
    Returns {"compatible": bool, "resolved": str | None, "reason": str}
    """
    if not ranges:
        return {"compatible": True, "resolved": None, "reason": "no ranges"}

    if len(ranges) == 1:
        return {"compatible": True, "resolved": ranges[0], "reason": "single range"}

    # Parse all ranges and check if they overlap
    parsed = [_parse_semver(r) for r in ranges]

    # Simple heuristic: if all share the same major, pick the highest minimum
    majors = {p[1] for p in parsed}
    if len(majors) > 1:
        return {
            "compatible": False,
            "resolved": None,
            "reason": f"Conflicting major versions: {sorted(majors)}",
        }

    # Same major — pick highest specified version
    best = max(parsed, key=lambda p: (p[1], p[2], p[3]))
    resolved = f"{best[1]}.{best[2]}.{best[3]}"
    return {"compatible": True, "resolved": resolved, "reason": "highest compatible"}
