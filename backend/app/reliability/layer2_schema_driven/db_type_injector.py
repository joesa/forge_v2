from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# CRITICAL: Pydantic Optional[str] → TypeScript string | null (not just string)
_TYPE_MAP: dict[str, str] = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "datetime": "string",
    "date": "string",
    "uuid": "string",
    "dict": "Record<string, unknown>",
    "list": "unknown[]",
    "Any": "unknown",
}


def generate_ts_interfaces(model_defs: list[dict]) -> str:
    """Generate TypeScript interfaces from model definitions.

    CRITICAL: Optional[str] → string | null (NOT just string).
    Run AFTER DBAgent, inject BEFORE PageAgent + ComponentAgent.
    """
    lines: list[str] = ["// Auto-generated TypeScript interfaces", ""]

    for model in model_defs:
        name = model.get("name", "Unknown")
        fields = model.get("fields", [])

        lines.append(f"export interface {name} {{")
        for field in fields:
            fname = field["name"]
            ftype = field.get("type", "str")
            required = field.get("required", True)

            ts_type = _python_type_to_ts(ftype)

            # CRITICAL: Optional types must be `type | null`
            if not required:
                if "| null" not in ts_type:
                    ts_type = f"{ts_type} | null"

            optional_marker = "" if required else "?"
            lines.append(f"  {fname}{optional_marker}: {ts_type};")

        lines.append("}")
        lines.append("")

    result = "\n".join(lines)
    logger.info("Generated %d TypeScript interfaces", len(model_defs))
    return result


def _python_type_to_ts(python_type: str) -> str:
    """Convert Python type string to TypeScript type.

    CRITICAL: Optional[str] → string | null (not just string)
    """
    # Handle Optional[X]
    if python_type.startswith("Optional[") and python_type.endswith("]"):
        inner = python_type[9:-1]
        base = _TYPE_MAP.get(inner, "unknown")
        return f"{base} | null"

    # Handle X | None
    if " | None" in python_type:
        inner = python_type.replace(" | None", "").strip()
        base = _TYPE_MAP.get(inner, "unknown")
        return f"{base} | null"

    return _TYPE_MAP.get(python_type, "unknown")
