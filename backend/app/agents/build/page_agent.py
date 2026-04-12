"""Agent 4: Page — Layer 2 inject prop types, Layer 6 ErrorBoundary injection."""
from __future__ import annotations

from app.agents.build.base import BaseBuildAgent, TEMPERATURE, SEED
from app.agents.state import PipelineState


class PageAgent(BaseBuildAgent):
    name = "page"
    agent_number = 4

    async def _run(self, state: PipelineState) -> dict[str, str]:
        plan = state.get("comprehensive_plan", {})
        spec_outputs = state.get("spec_outputs", {})
        existing_files = state.get("generated_files", {})

        pages = plan.get("pages", [
            {"name": "Home", "path": "/", "component": "HomePage"},
            {"name": "Dashboard", "path": "/dashboard", "component": "DashboardPage"},
            {"name": "NotFound", "path": "*", "component": "NotFoundPage"},
        ])

        files: dict[str, str] = {}

        # Layer 6: Generate ErrorBoundary component
        files["src/components/errorBoundary.tsx"] = """import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="p-4 text-center">
          <h2 className="text-xl font-bold text-red-500">Something went wrong</h2>
          <p className="text-gray-400 mt-2">{this.state.error?.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}"""

        # Generate full page implementations with ErrorBoundary wrapping
        for page in pages:
            component = page.get("component", page.get("name", "Page"))
            module = component[0].lower() + component[1:]
            path = page.get("path", "/")

            page_content = f"""import {{ ErrorBoundary }} from '../components/errorBoundary';

export function {component}() {{
  return (
    <ErrorBoundary>
      <div className="min-h-screen p-8">
        <h1 className="text-2xl font-bold">{component.replace('Page', '')}</h1>
      </div>
    </ErrorBoundary>
  );
}}"""
            files[f"src/pages/{module}.tsx"] = page_content

        return files
