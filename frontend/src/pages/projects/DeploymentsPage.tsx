import { useNavigate, useParams } from 'react-router-dom'

const mockDeploys = [
  { id: 'd1', url: 'saas-dashboard.forge.dev', status: 'live' as const, build: '#12', created: '2 hours ago' },
  { id: 'd2', url: 'saas-dashboard-staging.forge.dev', status: 'live' as const, build: '#11', created: '1 day ago' },
  { id: 'd3', url: 'saas-dashboard-preview.forge.dev', status: 'expired' as const, build: '#10', created: '5 days ago' },
]

const statusStyles: Record<string, { color: string; bg: string; border: string; label: string }> = {
  live: { color: '#3dffa0', bg: 'rgba(61,255,160,0.1)', border: 'rgba(61,255,160,0.2)', label: '● Live' },
  expired: { color: 'rgba(232,232,240,0.5)', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', label: '○ Expired' },
}

export default function DeploymentsPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/projects/${id}`)}>← Project</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', margin: 0 }}>Deployments</h1>
        <span className="tag tag-muted">/deployments</span>
      </div>

      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              {['URL', 'Status', 'Build', 'Created'].map((h) => (
                <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', fontWeight: 500 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mockDeploys.map((d) => {
              const st = statusStyles[d.status]
              return (
                <tr key={d.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '12px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#63d9ff' }}>{d.url}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: st.color, background: st.bg, border: `1px solid ${st.border}` }}>{st.label}</span>
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 11, color: 'rgba(232,232,240,0.50)' }}>{d.build}</td>
                  <td style={{ padding: '12px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.35)' }}>{d.created}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
