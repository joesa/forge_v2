"""Agent 6: DB — Layer 2 inject Pydantic schemas, generate database types + client."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class DBAgent(BaseBuildAgent):
    name = "db"
    agent_number = 6

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        spec_outputs = state.get("spec_outputs", {})
        existing_files = state.get("generated_files", {})

        pydantic_code = spec_outputs.get("pydantic_code", "")
        model_defs = spec_outputs.get("model_defs", {})
        entities = plan.get("entities", [])

        system_prompt = (
            "You are a senior full-stack developer. Generate the database types and Supabase client\n"
            "for a React + TypeScript app.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Required files:\n"
            "- src/types/database.ts: TypeScript interfaces for ALL entities listed below.\n"
            "  Each interface must include: id (string), created_at (string), updated_at (string)\n"
            "  plus all entity-specific fields.\n"
            "  Also export Create and Update types (Omit<Entity, 'id'|'created_at'|'updated_at'>).\n\n"
            "- src/lib/supabase.ts: Supabase client setup.\n"
            "  MUST use import.meta.env (NOT process.env):\n"
            "    const supabaseUrl = import.meta.env.VITE_SUPABASE_URL\n"
            "    const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY\n"
            "  Export the client as: export const supabase = createClient(supabaseUrl, supabaseAnonKey)\n\n"
            "Requirements:\n"
            "- Use proper TypeScript types (no 'any')\n"
            "- If entities have relationships, include foreign key fields (e.g. user_id: string)\n"
            "- Export all interfaces and types\n"
            "- Add a Database type mapping table names to row types for type-safe queries"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n\n"
            f"Entities:\n{json.dumps(entities, indent=2, default=str)}\n\n"
            f"Model definitions: {json.dumps(model_defs, default=str) if model_defs else '(none)'}\n"
            f"Pydantic code:\n{pydantic_code or '(none)'}\n\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
