import { useNavigate, useParams } from 'react-router-dom'

export default function ProjectDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/projects')}>← Projects</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', margin: 0 }}>Project Overview</h1>
        <span className="tag tag-muted">/projects/{id}</span>
      </div>

      {/* Project header card */}
      <div className="card" style={{ marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: '#3dffa0', background: 'rgba(61,255,160,0.1)', border: '1px solid rgba(61,255,160,0.2)' }}>● Live</span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.42)' }}>Next.js</span>
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', margin: '0 0 6px' }}>SaaS Dashboard</h2>
            <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.45)', lineHeight: 1.6, margin: 0 }}>Analytics platform with real-time data visualization and team collaboration features.</p>
          </div>
          <button className="btn btn-primary" onClick={() => navigate(`/projects/${id}/editor`)}>Open Editor →</button>
        </div>
      </div>

      {/* Quick links */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { icon: '⚡', label: 'Editor', path: `/projects/${id}/editor` },
          { icon: '🔨', label: 'Builds', path: `/projects/${id}/builds` },
          { icon: '▲', label: 'Deployments', path: `/projects/${id}/deployments` },
          { icon: '⚙️', label: 'Settings', path: `/projects/${id}/settings` },
        ].map((item) => (
          <div key={item.label} className="card" style={{ textAlign: 'center', cursor: 'pointer', padding: 22 }} onClick={() => navigate(item.path)}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>{item.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
