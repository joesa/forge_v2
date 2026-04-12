import { useNavigate } from 'react-router-dom'

const stats = [
  { icon: '📁', value: '7', label: 'Total Projects' },
  { icon: '⚙️', value: '2', label: 'Active Builds' },
  { icon: '▲', value: '14', label: 'Deployments' },
  { icon: '⚡', value: '847k / 2M', label: 'Tokens', hasProgress: true },
]

const recentProjects = [
  { id: '1', name: 'SaaS Dashboard', desc: 'Analytics platform with real-time data', status: 'live' as const, framework: 'Next.js' },
  { id: '2', name: 'E-commerce App', desc: 'Full-stack store with Stripe integration', status: 'building' as const, framework: 'React + Vite' },
  { id: '3', name: 'AI Chat Bot', desc: 'Customer support bot with RAG pipeline', status: 'draft' as const, framework: 'FastAPI + React' },
]

const activities = [
  { color: '#3dffa0', text: 'Deployed SaaS Dashboard to production', project: 'SaaS Dashboard', time: '2m ago' },
  { color: '#63d9ff', text: 'Build completed for E-commerce App', project: 'E-commerce', time: '15m ago' },
  { color: '#b06bff', text: 'AI analysis finished for AI Chat Bot', project: 'AI Chat Bot', time: '1h ago' },
  { color: '#ff6b35', text: 'Build failed — auto-fix applied', project: 'Portfolio', time: '3h ago' },
]

const statusStyles: Record<string, { color: string; bg: string; border: string; label: string }> = {
  live: { color: '#3dffa0', bg: 'rgba(61,255,160,0.1)', border: 'rgba(61,255,160,0.2)', label: '● Live' },
  building: { color: '#63d9ff', bg: 'rgba(99,217,255,0.1)', border: 'rgba(99,217,255,0.2)', label: '◎ Building' },
  draft: { color: 'rgba(232,232,240,0.5)', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', label: '✦ Draft' },
}

export default function DashboardPage() {
  const navigate = useNavigate()

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      {/* Header */}
      <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, color: 'var(--text)', marginBottom: 4 }}>Good morning 👋</h1>
      <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.40)', marginBottom: 28 }}>Here&apos;s what&apos;s happening in your workspace</p>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 36 }}>
        {stats.map((s) => (
          <div key={s.label} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 18 }}>
            <div style={{ fontSize: 18, marginBottom: 7 }}>{s.icon}</div>
            <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, background: 'linear-gradient(135deg, #63d9ff, #3dffa0)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{s.value}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.40)', marginTop: 4 }}>{s.label}</div>
            {s.hasProgress && (
              <div style={{ height: 3, background: 'rgba(255,255,255,0.07)', borderRadius: 2, marginTop: 8 }}>
                <div style={{ width: '42%', height: '100%', background: '#63d9ff', borderRadius: 2 }} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Continue Building */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 13 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)', margin: 0 }}>Continue Building</h2>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/projects')}>View all</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {recentProjects.map((p) => {
            const st = statusStyles[p.status]
            return (
              <div key={p.id} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ height: 80, borderRadius: '12px 12px 0 0', background: 'linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 28, opacity: 0.5 }}>⬡</span>
                </div>
                <div style={{ padding: '14px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: st.color, background: st.bg, border: `1px solid ${st.border}` }}>{st.label}</span>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: 'rgba(232,232,240,0.42)' }}>{p.framework}</span>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 3 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', lineHeight: 1.5, marginBottom: 13 }}>{p.desc}</div>
                  <button className="btn btn-secondary btn-sm" style={{ width: '100%' }} onClick={() => navigate(`/projects/${p.id}/editor`)}>Open Editor →</button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)', marginBottom: 13 }}>Quick Actions</h2>
        <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => navigate('/projects/new')}>+ New Project</button>
          <button className="btn btn-secondary" onClick={() => navigate('/ideate')}>💡 Generate Idea</button>
          <button className="btn btn-ghost" onClick={() => navigate('/projects')}>📁 All Projects</button>
          <button className="btn btn-ghost" onClick={() => navigate('/settings/profile')}>⚙ Settings</button>
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <h2 style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)', marginBottom: 13 }}>Recent Activity</h2>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {activities.map((a, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: a.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}>{a.text}</span>
              <span className="tag tag-forge">{a.project}</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.35)' }}>{a.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
