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

        system_prompt = (
            "You are a senior frontend developer. Generate a typed API client layer for a React + TypeScript app.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- src/lib/api.ts: Main API client with typed functions for each endpoint\n"
            "- Use fetch with proper error handling and auth headers from localStorage\n"
            "- API_BASE should come from import.meta.env.VITE_API_URL\n"
            "- Each function should have proper TypeScript return types\n"
            "- Include request/response type interfaces inline or in a separate types file\n"
            "- Group related endpoints logically\n"
            "- Handle authentication headers (Bearer token from localStorage)\n"
            "- If no OpenAPI spec is provided, generate a reasonable API client based on the app description"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"OpenAPI spec: {json.dumps(openapi_spec, default=str) if openapi_spec else '(none — infer endpoints from description)'}\n"
            f"Plan entities: {json.dumps(plan.get('entities', []), default=str)}\n"
            f"Existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
