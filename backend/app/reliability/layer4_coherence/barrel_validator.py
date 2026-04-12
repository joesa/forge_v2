from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)


def validate_barrels(generated_files: dict[str, str]) -> dict:
    """Validate barrel (index.ts) files re-export all sibling modules.

    Returns {"passed": bool, "missing_exports": list[dict], "extra_exports": list[dict]}
    """
    missing_exports: list[dict] = []
    extra_exports: list[dict] = []

    # Find all index.ts/index.tsx files
    barrels = {p: c for p, c in generated_files.items() if _is_barrel(p)}

    for barrel_path, barrel_content in barrels.items():
        barrel_dir = os.path.dirname(barrel_path)

        # Find sibling files (same directory, not the barrel itself)
        siblings = [
            p for p in generated_files
            if os.path.dirname(p) == barrel_dir
            and p != barrel_path
            and p.endswith((".ts", ".tsx"))
            and not p.endswith(".test.ts")
            and not p.endswith(".test.tsx")
            and not p.endswith(".spec.ts")
        ]

        # Parse what the barrel re-exports
        exported_modules = _parse_barrel_exports(barrel_content)

        # Check each sibling is re-exported
        for sibling in siblings:
            module_name = _path_to_module_name(sibling, barrel_dir)
            if module_name not in exported_modules:
                missing_exports.append({
                    "barrel": barrel_path,
                    "missing_module": module_name,
                    "file": sibling,
                })

    passed = len(missing_exports) == 0
    logger.info("Barrel validation: %d missing, passed=%s", len(missing_exports), passed)
    return {"passed": passed, "missing_exports": missing_exports, "extra_exports": extra_exports}


def _is_barrel(path: str) -> bool:
    base = os.path.basename(path)
    return base in ("index.ts", "index.tsx")


_BARREL_EXPORT_RE = re.compile(r"export\s+\*\s+from\s+['\"]\.\/([^'\"]+)['\"]")
_BARREL_NAMED_RE = re.compile(r"export\s+\{[^}]*\}\s+from\s+['\"]\.\/([^'\"]+)['\"]")


def _parse_barrel_exports(content: str) -> set[str]:
    """Parse module names from barrel export statements."""
    modules: set[str] = set()
    for m in _BARREL_EXPORT_RE.finditer(content):
        modules.add(m.group(1).replace(".ts", "").replace(".tsx", ""))
    for m in _BARREL_NAMED_RE.finditer(content):
        modules.add(m.group(1).replace(".ts", "").replace(".tsx", ""))
    return modules


def _path_to_module_name(path: str, barrel_dir: str) -> str:
    """Convert file path to the module name used in barrel exports."""
    rel = os.path.relpath(path, barrel_dir)
    return rel.replace(".tsx", "").replace(".ts", "").replace("\\", "/")
