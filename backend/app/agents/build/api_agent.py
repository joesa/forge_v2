"""Agent 5: API — Layer 2 inject OpenAPI spec, generate typed API client."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class APIAgent(BaseBuildAgent):
    name = "api"
    agent_number = 5

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        spec_outputs = state.get("spec_outputs", {})
        existing_files = state.get("generated_files", {})

        openapi_spec = spec_outputs.get("openapi_spec", {})
        entities = plan.get("entities", [])
        features = plan.get("features", [])

        system_prompt = (
            "You are a senior frontend developer. Generate a typed API client layer.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "IMPORTANT: This app uses Supabase as the backend — there is NO separate REST API server.\n"
            "All data operations go through the Supabase client directly.\n\n"
            "Required files:\n"
            "- src/lib/api.ts: Typed helper functions wrapping Supabase queries for each entity.\n"
            "  Each function should use the supabase client from './supabase'.\n"
            "  Example:\n"
            "    import { supabase } from './supabase'\n"
            "    import type { Task } from '../types/database'\n"
            "    export async function getTasks() {\n"
            "      const { data, error } = await supabase.from('tasks').select('*').order('created_at', { ascending: false })\n"
            "      if (error) throw error\n"
            "      return data as Task[]\n"
            "    }\n"
            "    export async function createTask(task: Omit<Task, 'id' | 'created_at' | 'updated_at'>) {\n"
            "      const { data, error } = await supabase.from('tasks').insert(task).select().single()\n"
            "      if (error) throw error\n"
            "      return data as Task\n"
            "    }\n"
            "- src/lib/types.ts: Export TypeScript interfaces for create/update payloads\n\n"
            "Requirements:\n"
            "- Generate CRUD functions (list, getById, create, update, delete) for EACH entity\n"
            "- All functions must have proper TypeScript types — no 'any'\n"
            "- Use supabase.from('table').select/insert/update/delete patterns\n"
            "- Include proper error handling (throw on error)\n"
            "- Add user_id filtering where appropriate: .eq('user_id', userId)\n"
            "- Support ordering and pagination parameters"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n\n"
            f"Entities (Supabase tables):\n{json.dumps(entities, indent=2, default=str)}\n\n"
            f"Features:\n{json.dumps(features, indent=2, default=str)}\n\n"
            f"OpenAPI spec (for reference):\n"
            f"{json.dumps(openapi_spec, default=str) if openapi_spec else '(none)'}\n\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
