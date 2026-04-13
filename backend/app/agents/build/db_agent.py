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
            "You are a senior full-stack developer. Generate the database types and Supabase client "
            "for a React + TypeScript app.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- src/types/database.ts: TypeScript interfaces for all data entities\n"
            "- src/lib/supabase.ts: Supabase client using createClient from @supabase/supabase-js\n"
            "  with VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY env vars\n"
            "- Interfaces should include id, created_at, updated_at fields where appropriate\n"
            "- Use proper TypeScript types (no 'any')\n"
            "- If Pydantic models are provided, mirror their structure exactly in TypeScript\n"
            "- If entities are provided, generate interfaces for each entity\n"
            "- Add helper type for Supabase query results"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Entities from plan: {json.dumps(entities, default=str)}\n"
            f"Model definitions: {json.dumps(model_defs, default=str) if model_defs else '(none)'}\n"
            f"Pydantic code:\n{pydantic_code or '(none)'}\n\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
