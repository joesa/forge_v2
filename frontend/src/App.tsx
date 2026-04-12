import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'

// ── Lazy-loaded pages ───────────────────────────────────────────
const LandingPage = lazy(() => import('@/pages/LandingPage'))
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/pages/auth/ResetPasswordPage'))

const OnboardingPage = lazy(() => import('@/pages/OnboardingPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ProjectsListPage = lazy(() => import('@/pages/projects/ProjectsListPage'))
const NewProjectPage = lazy(() => import('@/pages/projects/NewProjectPage'))
const ProjectDetailPage = lazy(() => import('@/pages/projects/ProjectDetailPage'))
const EditorPage = lazy(() => import('@/pages/projects/EditorPage'))
const BuildsPage = lazy(() => import('@/pages/projects/BuildsPage'))
const DeploymentsPage = lazy(() => import('@/pages/projects/DeploymentsPage'))
const ProjectSettingsPage = lazy(() => import('@/pages/projects/ProjectSettingsPage'))

const IdeatePage = lazy(() => import('@/pages/ideate/IdeatePage'))
const QuestionnairePage = lazy(() => import('@/pages/ideate/QuestionnairePage'))
const IdeaDetailPage = lazy(() => import('@/pages/ideate/IdeaDetailPage'))
const PipelinePage = lazy(() => import('@/pages/PipelinePage'))

const ProfilePage = lazy(() => import('@/pages/settings/ProfilePage'))
const AIProvidersPage = lazy(() => import('@/pages/settings/AIProvidersPage'))
const ModelRoutingPage = lazy(() => import('@/pages/settings/ModelRoutingPage'))
const IntegrationsPage = lazy(() => import('@/pages/settings/IntegrationsPage'))
const APIKeysPage = lazy(() => import('@/pages/settings/APIKeysPage'))
const SecurityPage = lazy(() => import('@/pages/settings/SecurityPage'))
const BillingPage = lazy(() => import('@/pages/settings/BillingPage'))

// ── Layouts + guards ────────────────────────────────────────────
const ProtectedRoute = lazy(() => import('@/components/auth/ProtectedRoute'))
const SettingsLayout = lazy(() => import('@/components/layout/SettingsLayout'))

function PageSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--void)' }}>
      <div
        className="w-8 h-8 rounded-full border-2 border-transparent"
        style={{ borderTopColor: 'var(--forge)', animation: 'spin 1s linear infinite' }}
      />
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Protected — no AppShell (custom nav) */}
        <Route element={<ProtectedRoute noShell />}>
          <Route path="/projects/:id/editor" element={<EditorPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/ideate" element={<IdeatePage />} />
          <Route path="/ideate/questionnaire/:id" element={<QuestionnairePage />} />
        </Route>

        {/* Protected — with AppShell */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsListPage />} />
          <Route path="/projects/new" element={<NewProjectPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/projects/:id/builds" element={<BuildsPage />} />
          <Route path="/projects/:id/deployments" element={<DeploymentsPage />} />
          <Route path="/projects/:id/settings" element={<ProjectSettingsPage />} />
          <Route path="/ideate/ideas/:id" element={<IdeaDetailPage />} />
          <Route path="/pipeline/:id" element={<PipelinePage />} />
          <Route path="/settings" element={<SettingsLayout />}>
            <Route path="profile" element={<ProfilePage />} />
            <Route path="ai-providers" element={<AIProvidersPage />} />
            <Route path="model-routing" element={<ModelRoutingPage />} />
            <Route path="integrations" element={<IntegrationsPage />} />
            <Route path="api-keys" element={<APIKeysPage />} />
            <Route path="security" element={<SecurityPage />} />
            <Route path="billing" element={<BillingPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}

