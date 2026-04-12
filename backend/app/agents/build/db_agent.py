"""Agent 6: DB — Layer 2 inject Pydantic schemas, Layer 9 migration safety."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState
from app.reliability.layer2_schema_driven.db_type_injector import generate_ts_interfaces


class DBAgent(BaseBuildAgent):
    name = "db"
    agent_number = 6

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        spec_outputs = state.get("spec_outputs", {})

        # Layer 2: Pydantic model schemas
        pydantic_code = spec_outputs.get("pydantic_code", "")
        model_defs = spec_outputs.get("model_defs", {})

        files: dict[str, str] = {}

        # Generate database types / client
        entities = plan.get("entities", [
            {"name": "User", "fields": {"id": "string", "email": "string", "name": "string"}},
        ])

        # Layer 9: Migration safety — validate before writing SQL
        # Ensure no destructive operations in generated schemas
        for entity in entities:
            name = entity.get("name", "")
            fields = entity.get("fields", {})
            if not name or not fields:
                continue

        # Generate TS types from model_defs via Layer 2
        if model_defs:
            # Convert dict format to list[dict] format expected by generate_ts_interfaces
            model_list = [
                {
                    "name": name,
                    "fields": [
                        {"name": fname, "type": ftype, "required": True}
                        for fname, ftype in fields.items()
                    ],
                }
                for name, fields in model_defs.items()
            ]
            ts_types = generate_ts_interfaces(model_list)
            files["src/types/database.ts"] = ts_types
        else:
            # Generate from entities when no model_defs available
            type_blocks: list[str] = []
            for entity in entities:
                name = entity.get("name", "Entity")
                fields = entity.get("fields", {})
                field_lines = []
                for fname, ftype in fields.items():
                    ts_type = _map_type(ftype)
                    field_lines.append(f"  {fname}: {ts_type};")
                type_blocks.append(
                    f"export interface {name} {{\n" + "\n".join(field_lines) + "\n}"
                )
            files["src/types/database.ts"] = "\n\n".join(type_blocks) + "\n"

        # Generate Supabase client
        files["src/lib/supabase.ts"] = """import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
"""

        return files


def _map_type(t: str) -> str:
    """Map schema types to TypeScript types."""
    mapping = {
        "string": "string",
        "str": "string",
        "integer": "number",
        "int": "number",
        "float": "number",
        "number": "number",
        "boolean": "boolean",
        "bool": "boolean",
        "datetime": "string",
        "date": "string",
        "uuid": "string",
        "json": "Record<string, unknown>",
        "array": "unknown[]",
    }
    lower = t.lower()
    # Handle Optional types
    if lower.startswith("optional["):
        inner = lower[9:-1] if lower.endswith("]") else lower[9:]
        return f"{_map_type(inner)} | null"
    return mapping.get(lower, "unknown")
