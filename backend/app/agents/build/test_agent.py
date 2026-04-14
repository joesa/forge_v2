"""Agent 9: Test — generate unit + integration tests."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent, build_design_context
from app.agents.state import PipelineState


class TestAgent(BaseBuildAgent):
    name = "test"
    agent_number = 9

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        existing_files = state.get("generated_files", {})

        # Provide all component and page source code as context
        testable_files = {
            k: v for k, v in existing_files.items()
            if (k.startswith("src/components/") or k.startswith("src/pages/") or k.startswith("src/lib/") or k.startswith("src/hooks/"))
            and k.endswith((".ts", ".tsx"))
            and not k.endswith(".test.tsx")
            and not k.endswith(".test.ts")
        }

        system_prompt = (
            "You are a senior QA/test engineer. Generate comprehensive tests for a React + TypeScript app "
            "using Vitest and React Testing Library.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- vitest.config.ts: Vitest config with jsdom environment and react plugin\n"
            "- src/test/setup.ts: Test setup importing @testing-library/jest-dom\n"
            "- Generate test files in src/test/ mirroring the source structure\n"
            "- Test each component renders without crashing\n"
            "- Test each page renders (wrap in MemoryRouter)\n"
            "- Test hook behavior where applicable\n"
            "- Include at least one integration test for App\n"
            "- Use proper TypeScript types in tests\n"
            "- Test meaningful behavior, not just smoke tests"
        )

        design_context = build_design_context(state)
        user_prompt = (
            f"{design_context}\n\n"
            f"=== TEST-SPECIFIC ===\n"
            f"Source files to test:\n{json.dumps(testable_files, default=str)}\n"
            f"All files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
