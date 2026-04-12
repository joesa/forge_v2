"""Agent 3: Component — Layer 2 inject Zod schemas, generate UI components."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


class ComponentAgent(BaseBuildAgent):
    name = "component"
    agent_number = 3

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        spec_outputs = state.get("spec_outputs", {})

        # Layer 2: Get Zod schemas and TS interfaces from spec
        zod_schemas = spec_outputs.get("zod_schemas", "")
        ts_interfaces = spec_outputs.get("ts_interfaces", "")

        # Extract components from plan
        components = plan.get("components", [
            {"name": "Header", "props": []},
            {"name": "Footer", "props": []},
            {"name": "Layout", "props": ["children"]},
        ])

        files: dict[str, str] = {}

        # Write shared types from Layer 2
        if ts_interfaces:
            files["src/types/models.ts"] = ts_interfaces

        if zod_schemas:
            files["src/lib/schemas.ts"] = f"import {{ z }} from 'zod';\n\n{zod_schemas}"

        # Generate components
        for comp in components:
            name = comp.get("name", "Component")
            props = comp.get("props", [])
            filename = name[0].lower() + name[1:]

            if props:
                props_type = f"interface {name}Props {{\n"
                for p in props:
                    if p == "children":
                        props_type += "  children: React.ReactNode;\n"
                    else:
                        props_type += f"  {p}: string;\n"
                props_type += "}"
                props_param = f"{{ {', '.join(props)} }}: {name}Props"
                props_block = f"\n{props_type}\n\n"
            else:
                props_param = ""
                props_block = "\n"

            files[f"src/components/{filename}.tsx"] = f"""{props_block}export function {name}({props_param}) {{
  return (
    <div className="{filename}">
      {name}
    </div>
  );
}}"""

        # Barrel export
        export_lines = []
        for comp in components:
            name = comp.get("name", "Component")
            filename = name[0].lower() + name[1:]
            export_lines.append(f"export {{ {name} }} from './{filename}';")

        if export_lines:
            files["src/components/index.ts"] = "\n".join(export_lines) + "\n"

        return files
