from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def generate_package_json(
    dependencies: dict[str, str],
    dev_dependencies: dict[str, str] | None = None,
    *,
    name: str = "forge-generated-app",
    scripts: dict[str, str] | None = None,
) -> str:
    """Generate a deterministic package.json.

    The sandbox runs `npm install` which creates the real lockfile
    with real integrity hashes. We never fabricate a lockfile.

    Produces consistent output for the same input regardless of ordering.
    Returns JSON string.
    """
    all_deps = dict(sorted(dependencies.items()))
    all_dev = dict(sorted((dev_dependencies or {}).items()))

    default_scripts = {
        "dev": "vite --host 0.0.0.0 --port 3000",
        "build": "tsc -b && vite build",
        "preview": "vite preview",
        "lint": "eslint .",
    }

    pkg = {
        "name": name,
        "version": "0.1.0",
        "private": True,
        "type": "module",
        "scripts": scripts or default_scripts,
        "dependencies": all_deps,
        "devDependencies": all_dev,
    }

    return json.dumps(pkg, indent=2, sort_keys=False)


def generate_install_command(
    dependencies: dict[str, str],
    dev_dependencies: dict[str, str] | None = None,
) -> str:
    """Generate the npm install command for the sandbox.

    Returns the shell command string that the sandbox executor should run
    to install deps and produce a real lockfile.
    """
    # npm ci is faster but requires a lockfile. Since we're generating from
    # scratch, use npm install which creates the lockfile.
    return "npm install --prefer-offline --no-audit --no-fund"


# ── Legacy alias ─────────────────────────────────────────────────
# Tests and callers that used the old name still work.
def generate_lockfile(
    dependencies: dict[str, str],
    dev_dependencies: dict[str, str] | None = None,
) -> str:
    """DEPRECATED: Use generate_package_json instead.

    Kept for backward compatibility — now generates package.json, not a fake lockfile.
    """
    return generate_package_json(dependencies, dev_dependencies)
