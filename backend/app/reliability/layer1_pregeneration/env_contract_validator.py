from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Required env vars for every generated app
_REQUIRED_VARS: list[str] = [
    "DATABASE_URL",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
]

# Framework-specific required vars
_FRAMEWORK_VARS: dict[str, list[str]] = {
    "nextjs": ["NEXTAUTH_SECRET", "NEXTAUTH_URL"],
    "vite_react": ["VITE_API_URL"],
    "fastapi": ["SECRET_KEY", "CORS_ORIGINS"],
    "django": ["DJANGO_SECRET_KEY", "ALLOWED_HOSTS"],
    "express": ["PORT", "SESSION_SECRET"],
}

# Regex patterns for env var references in source code
_ENV_PATTERNS: list[re.Pattern[str]] = [
    # JavaScript/TypeScript: process.env.VAR_NAME
    re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)"),
    # JavaScript/TypeScript: import.meta.env.VAR_NAME (Vite)
    re.compile(r"import\.meta\.env\.([A-Z_][A-Z0-9_]*)"),
    # Python: os.environ["VAR"] or os.environ.get("VAR")
    re.compile(r'os\.environ(?:\.get)?\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'),
    # Python: os.getenv("VAR")
    re.compile(r'os\.getenv\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'),
    # Python: settings.VAR (Pydantic Settings pattern)
    re.compile(r'settings?\.\s*([A-Z_][A-Z0-9_]*)'),
    # .env file references: VAR=value
    re.compile(r"^([A-Z_][A-Z0-9_]*)=", re.MULTILINE),
]

# Vars that are always available at runtime and shouldn't be flagged
_RUNTIME_VARS: set[str] = {
    "NODE_ENV", "HOME", "PATH", "PWD", "USER", "SHELL", "LANG",
    "CI", "DEBUG", "HOSTNAME", "TERM",
}


def validate_env_contract(
    framework: str,
    env_vars: dict[str, str] | None = None,
) -> dict:
    """Validate all required .env vars are present before Stage 1.

    Returns {"passed": bool, "missing": list[str], "warnings": list[str]}
    """
    env_vars = env_vars or {}
    missing: list[str] = []
    warnings: list[str] = []

    # Check universal required vars
    for var in _REQUIRED_VARS:
        if var not in env_vars:
            missing.append(var)

    # Check framework-specific vars
    fw_vars = _FRAMEWORK_VARS.get(framework, [])
    for var in fw_vars:
        if var not in env_vars:
            missing.append(var)

    # Warn on suspicious values
    for key, val in env_vars.items():
        if val in ("", "changeme", "your-key-here", "TODO"):
            warnings.append(f"{key} has placeholder value: '{val}'")

    passed = len(missing) == 0
    if not passed:
        logger.warning("Env contract failed: missing %s", missing)

    return {"passed": passed, "missing": missing, "warnings": warnings}


def scan_generated_code(generated_files: dict[str, str]) -> set[str]:
    """Scan generated source files for env var references.

    Finds all process.env.*, import.meta.env.*, os.environ[], os.getenv()
    references and returns the set of var names actually used.
    """
    found: set[str] = set()
    for path, content in generated_files.items():
        # Skip non-source files
        if not path.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".env", ".env.example")):
            continue
        for pattern in _ENV_PATTERNS:
            for m in pattern.finditer(content):
                var = m.group(1)
                if var and var not in _RUNTIME_VARS:
                    found.add(var)
    return found


def validate_env_against_code(
    env_vars: dict[str, str],
    generated_files: dict[str, str],
) -> dict:
    """Validate env vars against what generated code actually references.

    Returns {"passed": bool, "missing": list[str], "unused": list[str], "referenced": list[str]}
    """
    referenced = scan_generated_code(generated_files)
    provided = set(env_vars.keys())

    missing = sorted(referenced - provided)
    unused = sorted(provided - referenced - _RUNTIME_VARS)

    return {
        "passed": len(missing) == 0,
        "missing": missing,
        "unused": unused,
        "referenced": sorted(referenced),
    }


def get_env_template(framework: str) -> dict[str, str]:
    """Generate a .env template with placeholder values for a framework."""
    template: dict[str, str] = {}

    for var in _REQUIRED_VARS:
        template[var] = ""

    for var in _FRAMEWORK_VARS.get(framework, []):
        template[var] = ""

    return template
