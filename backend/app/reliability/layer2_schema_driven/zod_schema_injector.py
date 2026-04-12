from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Python type → Zod mapping
_TYPE_MAP: dict[str, str] = {
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
}


def generate_zod_schemas(pydantic_models: list[dict]) -> str:
    """Generate Zod schemas from Pydantic model definitions.

    Injected into ComponentAgent + PageAgent context.
    Each model dict: {"name": str, "fields": [{"name": str, "type": str, "required": bool}]}
    """
    lines: list[str] = ['import { z } from "zod";', ""]

    for model in pydantic_models:
        name = model.get("name", "Unknown")
        fields = model.get("fields", [])
        schema_name = f"{name}Schema"

        lines.append(f"export const {schema_name} = z.object({{")
        for field in fields:
            fname = field["name"]
            ftype = field.get("type", "str")
            required = field.get("required", True)

            zod_type = _python_type_to_zod(ftype)
            if not required:
                zod_type = f"{zod_type}.nullable().optional()"

            lines.append(f"  {fname}: {zod_type},")
        lines.append("});")
        lines.append(f"export type {name} = z.infer<typeof {schema_name}>;")
        lines.append("")

    result = "\n".join(lines)
    logger.info("Generated %d Zod schemas", len(pydantic_models))
    return result


def _python_type_to_zod(python_type: str) -> str:
    """Convert a Python type string to Zod validator.

    Handles Optional[X] → z.X().nullable()
    """
    # Handle Optional[X]
    if python_type.startswith("Optional[") and python_type.endswith("]"):
        inner = python_type[9:-1]
        base = _TYPE_MAP.get(inner, "z.unknown()")
        return f"{base}.nullable()"

    # Handle X | None
    if " | None" in python_type:
        inner = python_type.replace(" | None", "").strip()
        base = _TYPE_MAP.get(inner, "z.unknown()")
        return f"{base}.nullable()"

    return _TYPE_MAP.get(python_type, "z.unknown()")
