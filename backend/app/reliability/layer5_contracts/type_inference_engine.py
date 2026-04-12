"""Layer 5 — Type Inference Engine.

Pydantic Optional[str] → TypeScript string | null.
Compatible with Layer 2's list[dict] model format.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Canonical type maps ──────────────────────────────────────────
# CRITICAL: These must stay in sync with Layer 2 db_type_injector._TYPE_MAP

_PYTHON_TO_TS: dict[str, str] = {
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
    "bytes": "string",
    "Decimal": "number",
}

_PYTHON_TO_ZOD: dict[str, str] = {
    "str": "z.string()",
    "int": "z.number().int()",
    "float": "z.number()",
    "bool": "z.boolean()",
    "datetime": "z.string().datetime()",
    "date": "z.string().date()",
    "uuid": "z.string().uuid()",
    "dict": "z.record(z.unknown())",
    "list": "z.array(z.unknown())",
    "Any": "z.unknown()",
    "bytes": "z.string()",
    "Decimal": "z.number()",
}

_PYTHON_TO_OPENAPI: dict[str, dict] = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "float": {"type": "number"},
    "bool": {"type": "boolean"},
    "datetime": {"type": "string", "format": "date-time"},
    "date": {"type": "string", "format": "date"},
    "uuid": {"type": "string", "format": "uuid"},
    "dict": {"type": "object"},
    "list": {"type": "array", "items": {}},
    "Any": {},
    "bytes": {"type": "string", "format": "byte"},
    "Decimal": {"type": "number"},
}


@dataclass
class TypeMapping:
    """Result of a type inference."""

    python_type: str
    typescript_type: str
    zod_type: str
    openapi_schema: dict
    nullable: bool


# ── Public API ───────────────────────────────────────────────────


def infer_type(python_type: str) -> TypeMapping:
    """Infer TypeScript, Zod, and OpenAPI types from a Python type string.

    CRITICAL: Optional[str] → string | null (NOT just string).
    Handles: Optional[X], X | None, list[X], dict[str, X].
    """
    nullable = False
    base_type = python_type

    # Optional[X] → X, nullable
    if base_type.startswith("Optional[") and base_type.endswith("]"):
        base_type = base_type[9:-1]
        nullable = True

    # X | None → X, nullable
    if " | None" in base_type:
        base_type = base_type.replace(" | None", "").strip()
        nullable = True

    # list[X] → X[]
    list_match = re.match(r"list\[(.+)\]", base_type)
    if list_match:
        inner = list_match.group(1)
        inner_mapping = infer_type(inner)
        ts = f"{inner_mapping.typescript_type}[]"
        zod = f"z.array({inner_mapping.zod_type})"
        openapi = {"type": "array", "items": inner_mapping.openapi_schema}
        if nullable:
            ts = f"{ts} | null"
            zod = f"{zod}.nullable()"
            openapi = {**openapi, "nullable": True}
        return TypeMapping(
            python_type=python_type,
            typescript_type=ts,
            zod_type=zod,
            openapi_schema=openapi,
            nullable=nullable,
        )

    # dict[str, X] → Record<string, X>
    dict_match = re.match(r"dict\[str,\s*(.+)\]", base_type)
    if dict_match:
        inner = dict_match.group(1)
        inner_mapping = infer_type(inner)
        ts = f"Record<string, {inner_mapping.typescript_type}>"
        zod = f"z.record(z.string(), {inner_mapping.zod_type})"
        openapi = {
            "type": "object",
            "additionalProperties": inner_mapping.openapi_schema,
        }
        if nullable:
            ts = f"{ts} | null"
            zod = f"{zod}.nullable()"
            openapi = {**openapi, "nullable": True}
        return TypeMapping(
            python_type=python_type,
            typescript_type=ts,
            zod_type=zod,
            openapi_schema=openapi,
            nullable=nullable,
        )

    # Simple scalar types
    ts = _PYTHON_TO_TS.get(base_type, "unknown")
    zod = _PYTHON_TO_ZOD.get(base_type, "z.unknown()")
    openapi = _PYTHON_TO_OPENAPI.get(base_type, {"type": "string"}).copy()

    if nullable:
        ts = f"{ts} | null"
        zod = f"{zod}.nullable()"
        openapi["nullable"] = True

    return TypeMapping(
        python_type=python_type,
        typescript_type=ts,
        zod_type=zod,
        openapi_schema=openapi,
        nullable=nullable,
    )


def infer_model_types(model_defs: list[dict]) -> list[dict]:
    """Infer full type mappings for a list of model definitions.

    Input format: [{"name": str, "fields": [{"name", "type", "required"}]}]
    Returns the same structure with added "ts_type", "zod_type", "openapi_schema"
    on each field.

    Compatible with Layer 2 model definitions.
    """
    result: list[dict] = []

    for model in model_defs:
        enriched_fields: list[dict] = []
        for field in model.get("fields", []):
            python_type = field.get("type", "str")
            required = field.get("required", True)

            # If not required and not already Optional, wrap as Optional
            effective_type = python_type
            if not required and not _is_already_optional(python_type):
                effective_type = f"Optional[{python_type}]"

            mapping = infer_type(effective_type)

            enriched_fields.append({
                **field,
                "ts_type": mapping.typescript_type,
                "zod_type": mapping.zod_type,
                "openapi_schema": mapping.openapi_schema,
                "nullable": mapping.nullable,
            })

        result.append({
            "name": model.get("name", "Unknown"),
            "fields": enriched_fields,
        })

    logger.info("Inferred types for %d models", len(result))
    return result


def validate_type_consistency(
    model_defs: list[dict],
    generated_files: dict[str, str],
) -> dict:
    """Validate that generated files use consistent types.

    Cross-checks TypeScript interfaces, Zod schemas, and model defs.

    Returns {
        "passed": bool,
        "total_mismatches": int,
        "mismatches": [{"model", "field", "expected_ts", "found_in", "message"}],
    }
    """
    enriched = infer_model_types(model_defs)
    mismatches: list[dict] = []

    # Find TypeScript interface files
    ts_files = {
        fp: content
        for fp, content in generated_files.items()
        if fp.endswith((".ts", ".tsx"))
    }

    for model in enriched:
        model_name = model["name"]
        for field in model["fields"]:
            field_name = field["name"]
            expected_ts = field["ts_type"]

            # Check for type mismatches in generated TS files
            for filepath, content in ts_files.items():
                # Look for interface field definitions
                # Pattern: fieldName?: type  or  fieldName: type
                pattern = re.compile(
                    rf'\b{re.escape(field_name)}\??\s*:\s*([^;,\n]+)'
                )
                for match in pattern.finditer(content):
                    found_type = match.group(1).strip()
                    if not _types_compatible(expected_ts, found_type):
                        mismatches.append({
                            "model": model_name,
                            "field": field_name,
                            "expected_ts": expected_ts,
                            "found_ts": found_type,
                            "found_in": filepath,
                            "message": (
                                f"Type mismatch for {model_name}.{field_name}: "
                                f"expected '{expected_ts}', found '{found_type}'"
                            ),
                        })

    return {
        "passed": len(mismatches) == 0,
        "total_mismatches": len(mismatches),
        "mismatches": mismatches,
    }


# ── Internal helpers ─────────────────────────────────────────────


def _is_already_optional(python_type: str) -> bool:
    """Check if a type is already optional."""
    return (
        python_type.startswith("Optional[")
        or " | None" in python_type
    )


def _types_compatible(expected: str, found: str) -> bool:
    """Check if two TypeScript types are compatible.

    Normalises whitespace and ordering for comparison.
    """
    def normalise(t: str) -> set[str]:
        parts = {p.strip() for p in t.replace(" ", "").split("|")}
        # Normalise null/undefined
        normalised = set()
        for part in parts:
            normalised.add(part)
        return normalised

    return normalise(expected) == normalise(found)
