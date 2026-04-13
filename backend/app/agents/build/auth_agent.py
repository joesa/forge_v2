"""Agent 7: Auth — generate authentication layer."""
from __future__ import annotations

import json

from app.agents.build.base import BaseBuildAgent
from app.agents.state import PipelineState


class AuthAgent(BaseBuildAgent):
    name = "auth"
    agent_number = 7

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})
        existing_files = state.get("generated_files", {})

        auth_strategy = plan.get("auth_strategy", idea_spec.get("auth_strategy", "supabase"))

        # Provide the supabase client code as context if it exists
        context_files = {
            k: v for k, v in existing_files.items()
            if k in ("src/lib/supabase.ts", "src/types/database.ts", "src/routes.tsx")
        }

        system_prompt = (
            "You are a senior React + TypeScript developer. Generate the authentication layer.\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Requirements:\n"
            "- src/lib/auth.ts: Auth functions (signIn, signUp, signOut, getSession, onAuthStateChange)\n"
            "  using the Supabase client from ./supabase\n"
            "- src/hooks/useAuth.ts: React hook that tracks user, session, loading state\n"
            "- src/components/protectedRoute.tsx: ProtectedRoute component that redirects to /login\n"
            "- All functions must have proper TypeScript types\n"
            "- Use @supabase/supabase-js types (User, Session)\n"
            "- The hook should subscribe to auth state changes and clean up on unmount\n"
            "- ProtectedRoute should show a loading state while checking auth"
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Auth strategy: {auth_strategy}\n"
            f"Existing related files:\n{json.dumps(context_files, default=str)}\n"
            f"All existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
