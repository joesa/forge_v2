from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def generate_pydantic_models(spec_outputs: dict) -> str:
    """Generate Pydantic v2 model code from spec outputs.

    Injected into APIAgent + DBAgent context.
    """
    db_spec = spec_outputs.get("db", {})
    api_spec = spec_outputs.get("api", {})

    models: list[dict] = _extract_models_from_specs(db_spec, api_spec)

    lines: list[str] = [
        "from __future__ import annotations",
        "",
        "from datetime import datetime",
        "from uuid import UUID",
        "",
        "from pydantic import BaseModel, Field",
        "",
    ]

    for model in models:
        name = model["name"]
        fields = model.get("fields", [])

        lines.append(f"class {name}(BaseModel):")
        if not fields:
            lines.append("    pass")
        else:
            for f in fields:
                fname = f["name"]
                ftype = _to_python_type(f.get("type", "str"), f.get("required", True))
                default = f.get("default", "...")
                if not f.get("required", True) and default == "...":
                    default = "None"
                lines.append(f"    {fname}: {ftype} = {default}")
        lines.append("")

    result = "\n".join(lines)
    logger.info("Generated %d Pydantic models", len(models))
    return result


def extract_model_defs(spec_outputs: dict) -> list[dict]:
    """Extract model definitions for use by other injectors.

    Returns list of {"name": str, "fields": [{"name", "type", "required"}]}
    """
    db_spec = spec_outputs.get("db", {})
    api_spec = spec_outputs.get("api", {})
    return _extract_models_from_specs(db_spec, api_spec)


def _extract_models_from_specs(db_spec: dict, api_spec: dict) -> list[dict]:
    """Extract model definitions from db and api specs."""
    models: list[dict] = []

    # Extract from db spec tables
    tables = db_spec.get("tables", [])
    for table in tables:
        name = _to_class_name(table.get("name", "unknown"))
        columns = table.get("columns", [])
        fields = []
        for col in columns:
            fields.append({
                "name": col.get("name", "field"),
                "type": col.get("type", "str"),
                "required": not col.get("nullable", False),
            })
        models.append({"name": name, "fields": fields})

    # If no db spec tables, generate a basic CRUD model
    if not models:
        models.append({
            "name": "Item",
            "fields": [
                {"name": "id", "type": "uuid", "required": True},
                {"name": "title", "type": "str", "required": True},
                {"name": "description", "type": "Optional[str]", "required": False},
                {"name": "created_at", "type": "datetime", "required": True},
                {"name": "updated_at", "type": "datetime", "required": True},
            ],
        })

    return models


def _to_python_type(type_str: str, required: bool) -> str:
    """Convert type string to Python annotation."""
    type_map = {
        "uuid": "UUID",
        "str": "str",
        "int": "int",
        "float": "float",
        "bool": "bool",
        "datetime": "datetime",
        "date": "str",
        "dict": "dict",
        "list": "list",
    }

    if type_str.startswith("Optional["):
        return type_str

    base = type_map.get(type_str, "str")
    if not required:
        return f"{base} | None"
    return base


def _to_class_name(name: str) -> str:
    """Convert snake_case table name to PascalCase class name."""
    return "".join(word.capitalize() for word in name.replace("-", "_").split("_"))
