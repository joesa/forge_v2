// ── Common ───────────────────────────────────────────────────────
export interface Timestamps {
  created_at: string
  updated_at: string
}

// ── User ─────────────────────────────────────────────────────────
export interface User extends Timestamps {
  id: string
  email: string
  display_name: string | null
  avatar_url: string | null
  onboarded: boolean
  plan: string
  token_limit: number
}

// ── Project ──────────────────────────────────────────────────────
export type ProjectStatus = 'draft' | 'building' | 'live' | 'error' | 'archived'
export type Framework = 'nextjs' | 'vite_react' | 'fastapi' | 'django' | 'express'

export interface Project extends Timestamps {
  id: string
  user_id: string
  name: string
  description: string | null
  status: ProjectStatus
  framework: Framework
}

// ── Idea ─────────────────────────────────────────────────────────
export interface IdeaSession extends Timestamps {
  id: string
  user_id: string
  questionnaire_answers: Record<string, unknown> | null
  completed: boolean
  status: string
}

export interface Idea extends Timestamps {
  id: string
  idea_session_id: string
  user_id: string
  title: string
  description: string
  tech_stack: Record<string, unknown>
  market_analysis: Record<string, unknown> | null
  saved: boolean
  status: string
}

// ── Pipeline / Build ─────────────────────────────────────────────
export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed'
export type BuildStatus = 'pending' | 'building' | 'success' | 'failed'

export interface PipelineRun extends Timestamps {
  id: string
  project_id: string
  user_id: string
  status: PipelineStatus
  current_stage: number
  idea_spec: Record<string, unknown>
  errors: Record<string, unknown> | null
}

export interface AgentOutput extends Timestamps {
  id: string
  pipeline_run_id: string
  agent_name: string
  stage: number
  output_data: Record<string, unknown>
  gate_passed: boolean | null
  duration_ms: number | null
}

export interface Build extends Timestamps {
  id: string
  project_id: string
  user_id: string
  pipeline_run_id: string | null
  status: BuildStatus
  gate_results: Record<string, unknown> | null
  generated_files_key: string | null
}

export interface BuildSnapshot extends Timestamps {
  id: string
  build_id: string
  project_id: string
  agent_number: number
  agent_type: string
  screenshot_url: string
  storage_key: string
}

// ── Sandbox / Editor / Preview ───────────────────────────────────
export type SandboxStatus = 'warm' | 'claimed' | 'building' | 'stopping' | 'stopped' | 'error'
export type ChatRole = 'user' | 'assistant'

export interface Sandbox extends Timestamps {
  id: string
  project_id: string | null
  status: SandboxStatus
  northflank_service_id: string | null
}

export interface EditorSession extends Timestamps {
  id: string
  project_id: string
  user_id: string
  sandbox_id: string | null
  last_active_at: string
  status: string
}

export interface ChatMessage extends Timestamps {
  id: string
  project_id: string
  user_id: string
  session_id: string
  role: ChatRole
  content: string
  model_used: string | null
  status: string
}

export interface PreviewShare extends Timestamps {
  id: string
  sandbox_id: string
  user_id: string
  token: string
  expires_at: string
  revoked: boolean
  status: string
}

// ── Deployment ───────────────────────────────────────────────────
export interface Deployment extends Timestamps {
  id: string
  project_id: string
  user_id: string
  build_id: string
  status: string
  url: string | null
}

// ── AI Provider ──────────────────────────────────────────────────
export type ProviderName = 'anthropic' | 'openai' | 'gemini' | 'grok' | 'mistral' | 'cohere' | 'deepseek' | 'together'

export interface AIProvider extends Timestamps {
  id: string
  user_id: string
  provider_name: ProviderName
  is_default: boolean
  is_connected: boolean
  latency_ms: number | null
  status: string
}

// ── Annotation ───────────────────────────────────────────────────
export interface Annotation extends Timestamps {
  id: string
  project_id: string
  user_id: string
  editor_session_id: string | null
  css_selector: string
  route: string
  comment: string
  x_pct: number
  y_pct: number
  resolved: boolean
  status: string
}

// ── Reports ──────────────────────────────────────────────────────
export interface HotFixRecord extends Timestamps {
  id: string
  build_id: string
  failed_gate: string
  failing_file: string
  fix_applied: string | null
  success: boolean
  attempts: number
}

export interface PerformanceReport extends Timestamps {
  id: string
  build_id: string
  route: string
  lcp_ms: number | null
  cls: number | null
  fid_ms: number | null
  bundle_kb: number | null
  passed: boolean
}

export interface AccessibilityReport extends Timestamps {
  id: string
  build_id: string
  route: string
  critical_count: number
  serious_count: number
  violations: Record<string, unknown>
  passed: boolean
}

export interface CoherenceReport extends Timestamps {
  id: string
  build_id: string
  critical_errors: number
  auto_fixes: number
  report_data: Record<string, unknown>
  passed: boolean
}
