"""Agent 5: API — Layer 2 inject OpenAPI spec, implement to spec, Layer 5 validate."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


class APIAgent(BaseBuildAgent):
    name = "api"
    agent_number = 5

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        spec_outputs = state.get("spec_outputs", {})

        # Layer 2: Get OpenAPI spec
        openapi_spec = spec_outputs.get("openapi_spec", {})
        paths = openapi_spec.get("paths", {})

        files: dict[str, str] = {}

        # Generate API client with typed functions
        api_functions: list[str] = []
        type_imports: list[str] = []

        for path, methods in paths.items():
            for method, spec in methods.items():
                op_id = spec.get("operationId", f"{method}_{path.replace('/', '_')}")
                func_name = _to_camel(op_id)

                # Determine response type
                resp_schema = (
                    spec.get("responses", {})
                    .get("200", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                )
                resp_type = resp_schema.get("$ref", "").split("/")[-1] or "unknown"

                # Determine request body
                req_schema = (
                    spec.get("requestBody", {})
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                )
                has_body = bool(req_schema)

                if has_body:
                    body_type = req_schema.get("$ref", "").split("/")[-1] or "Record<string, unknown>"
                    api_functions.append(
                        f"export async function {func_name}(data: {body_type}): "
                        f"Promise<{resp_type}> {{\n"
                        f"  const res = await fetch(API_BASE + '{path}', {{\n"
                        f"    method: '{method.upper()}',\n"
                        f"    headers: {{ 'Content-Type': 'application/json', ...authHeaders() }},\n"
                        f"    body: JSON.stringify(data),\n"
                        f"  }});\n"
                        f"  if (!res.ok) throw new Error(`API error: ${{res.status}}`);\n"
                        f"  return res.json();\n"
                        f"}}"
                    )
                else:
                    api_functions.append(
                        f"export async function {func_name}(): Promise<{resp_type}> {{\n"
                        f"  const res = await fetch(API_BASE + '{path}', {{\n"
                        f"    method: '{method.upper()}',\n"
                        f"    headers: authHeaders(),\n"
                        f"  }});\n"
                        f"  if (!res.ok) throw new Error(`API error: ${{res.status}}`);\n"
                        f"  return res.json();\n"
                        f"}}"
                    )

        funcs_str = "\n\n".join(api_functions) if api_functions else (
            "// No API endpoints defined in spec\n"
            "export async function healthCheck(): Promise<{ status: string }> {\n"
            "  const res = await fetch(API_BASE + '/health');\n"
            "  return res.json();\n"
            "}"
        )

        files["src/lib/api.ts"] = f"""const API_BASE = import.meta.env.VITE_API_URL ?? '';

function authHeaders(): Record<string, string> {{
  const token = localStorage.getItem('access_token');
  return token ? {{ Authorization: `Bearer ${{token}}` }} : {{}};
}}

{funcs_str}
"""

        return files


def _to_camel(s: str) -> str:
    """Convert snake_case or kebab-case to camelCase."""
    parts = s.replace("-", "_").split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
