"""Agent 7: Auth — Layer 5 auth pattern from pattern library."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


class AuthAgent(BaseBuildAgent):
    name = "auth"
    agent_number = 7

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        idea_spec = state.get("idea_spec", {})

        # Determine auth strategy from plan
        auth_strategy = plan.get("auth_strategy", idea_spec.get("auth_strategy", "supabase"))

        files: dict[str, str] = {}

        # Auth context provider
        files["src/lib/auth.ts"] = """import { supabase } from './supabase';
import type { User, Session } from '@supabase/supabase-js';

export type AuthState = {
  user: User | null;
  session: Session | null;
  loading: boolean;
};

export async function signIn(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
}

export async function signUp(email: string, password: string) {
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw error;
  return data;
}

export async function signOut() {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

export async function getSession() {
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session;
}

export function onAuthStateChange(callback: (session: Session | null) => void) {
  return supabase.auth.onAuthStateChange((_event, session) => {
    callback(session);
  });
}
"""

        # Auth hook
        files["src/hooks/useAuth.ts"] = """import { useState, useEffect } from 'react';
import type { User, Session } from '@supabase/supabase-js';
import { getSession, onAuthStateChange } from '../lib/auth';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSession().then((s) => {
      setSession(s);
      setUser(s?.user ?? null);
      setLoading(false);
    });

    const { data: { subscription } } = onAuthStateChange((s) => {
      setSession(s);
      setUser(s?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  return { user, session, loading };
}
"""

        # Protected route component
        files["src/components/protectedRoute.tsx"] = """import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
"""

        return files
