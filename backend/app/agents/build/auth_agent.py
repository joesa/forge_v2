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
            "You are a senior React + TypeScript developer. Generate the authentication layer\n"
            "using @supabase/supabase-js v2 (NOT v1).\n\n"
            "Return a JSON object where each key is a file path and value is the complete file content.\n\n"
            "Required files:\n"
            "- src/lib/auth.ts: Auth helper functions using the Supabase client from ./supabase.\n"
            "  MUST use Supabase v2 methods:\n"
            "    - signInWithPassword({ email, password }) — NOT signIn()\n"
            "    - signUp({ email, password }) — returns { data, error }\n"
            "    - signOut()\n"
            "    - getSession() — returns { data: { session }, error }\n"
            "    - onAuthStateChange(callback) — returns { data: { subscription } }\n"
            "  Export each function with proper TypeScript types.\n\n"
            "- src/hooks/useAuth.ts: React hook that:\n"
            "    - Tracks user (User | null), session (Session | null), loading (boolean)\n"
            "    - Calls getSession() on mount\n"
            "    - Subscribes to onAuthStateChange and cleans up via subscription.unsubscribe()\n"
            "    - Returns { user, session, loading, signIn, signUp, signOut }\n\n"
            "- src/components/protectedRoute.tsx: ProtectedRoute component that:\n"
            "    - Uses useAuth() hook\n"
            "    - Shows loading spinner while checking auth\n"
            "    - Redirects to / (or /login) if no user\n"
            "    - Renders children if authenticated\n\n"
            "CRITICAL: Use @supabase/supabase-js v2 API. The v1 methods (signIn, signUp without\n"
            "'WithPassword') do NOT exist in v2 and will cause runtime errors.\n"
            "Use import.meta.env for environment variables, NOT process.env.\n"
            "If src/lib/supabase.ts is not in existing files, generate it with:\n"
            "  const url = import.meta.env.VITE_SUPABASE_URL ?? ''\n"
            "  const key = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''\n"
            "  export const supabase = url ? createClient(url, key) : null as any\n"
            "This prevents crashes when env vars are not yet configured.\n\n"
            "CRITICAL: The supabase client CAN be null. Every function in auth.ts that calls\n"
            "supabase.auth.* MUST check `if (!supabase)` first and return a safe default:\n"
            "  - getSession → { data: { session: null }, error: null }\n"
            "  - onAuthStateChange → { data: { subscription: { unsubscribe: () => {} } } }\n"
            "  - signIn/signUp → { data: { user: null, session: null }, error: new Error('Supabase not configured') }\n"
            "  - signOut → { error: null }\n"
            "All exports must use export default or named exports consistently."
        )

        user_prompt = (
            f"App: {idea_spec.get('name', 'App')}\n"
            f"Description: {idea_spec.get('description', '')}\n"
            f"Auth strategy: {auth_strategy}\n"
            f"Existing related files:\n{json.dumps(context_files, default=str)}\n"
            f"All existing files: {json.dumps(list(existing_files.keys()))}"
        )

        return await self._call_llm(system_prompt, user_prompt)
