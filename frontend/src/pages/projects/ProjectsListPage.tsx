import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

type FilterTab = 'all' | 'live' | 'building' | 'draft' | 'error'

const tabs: FilterTab[] = ['all', 'live', 'building', 'draft', 'error']

const mockProjects = [
  { id: '1', name: 'SaaS Dashboard', desc: 'Analytics platform with real-time data visualization', status: 'live' as const, framework: 'Next.js', updated: '2 hours ago' },
  { id: '2', name: 'E-commerce App', desc: 'Full-stack store with Stripe integration', status: 'building' as const, framework: 'React + Vite', updated: '15 min ago' },
  { id: '3', name: 'AI Chat Bot', desc: 'Customer support bot with RAG pipeline', status: 'draft' as const, framework: 'FastAPI + React', updated: '1 day ago' },
  { id: '4', name: 'Portfolio Site', desc: 'Personal portfolio with blog and projects', status: 'live' as const, framework: 'Next.js', updated: '3 days ago' },
  { id: '5', name: 'Task Manager', desc: 'Collaborative task management application', status: 'error' as const, framework: 'Remix', updated: '5 hours ago' },
]

const statusStyles: Record<string, { color: string; bg: string; border: string; label: string }> = {
  live: { color: '#3dffa0', bg: 'rgba(61,255,160,0.1)', border: 'rgba(61,255,160,0.2)', label: '● Live' },
  building: { color: '#63d9ff', bg: 'rgba(99,217,255,0.1)', border: 'rgba(99,217,255,0.2)', label: '◎ Building' },
  draft: { color: 'rgba(232,232,240,0.5)', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', label: '✦ Draft' },
  error: { color: '#ff6b35', bg: 'rgba(255,107,53,0.1)', border: 'rgba(255,107,53,0.2)', label: '⚠ Error' },
}

export default function ProjectsListPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<FilterTab>('all')
  const [search, setSearch] = useState('')

  const filtered = mockProjects.filter((p) => {
    if (filter !== 'all' && p.status !== filter) return false
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, color: 'var(--text)', margin: 0 }}>Projects</h1>
          <span className="tag tag-muted">/projects</span>
        </div>
        <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
          <input className="input" style={{ width: 200, height: 36, fontSize: 12 }} placeholder="Search projects…" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn btn-primary" onClick={() => navigate('/projects/new')}>+ New Project</button>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 5, marginBottom: 22 }}>
        {tabs.map((t) => (
          <button key={t} className={`btn btn-sm ${filter === t ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setFilter(t)} style={{ textTransform: 'capitalize' }}>
            {t}
          </button>
        ))}
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>⬡</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>No projects yet</div>
          <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.40)', marginBottom: 20 }}>Start building your first application</p>
          <div style={{ display: 'flex', gap: 9, justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={() => navigate('/ideate')}>Start with an idea →</button>
            <button className="btn btn-ghost" onClick={() => navigate('/projects/new')}>Build from prompt →</button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {filtered.map((p) => {
            const st = statusStyles[p.status]
            return (
              <div key={p.id} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ height: 90, background: 'linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 28, opacity: 0.5 }}>⬡</span>
                </div>
                <div style={{ padding: '14px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: st.color, background: st.bg, border: `1px solid ${st.border}` }}>{st.label}</span>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: 'rgba(232,232,240,0.42)' }}>{p.framework}</span>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', lineHeight: 1.5, marginBottom: 14 }}>{p.desc}</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>{p.updated}</span>
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/projects/${p.id}/editor`)}>Open Editor →</button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
