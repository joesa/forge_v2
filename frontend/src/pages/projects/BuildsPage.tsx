import { useNavigate, useParams } from 'react-router-dom'

const mockBuilds = [
  { id: 'b1', number: 12, status: 'success' as const, duration: '8m 42s', agent: 'Pipeline v3', created: '2 hours ago' },
  { id: 'b2', number: 11, status: 'success' as const, duration: '9m 15s', agent: 'Pipeline v3', created: '1 day ago' },
  { id: 'b3', number: 10, status: 'failed' as const, duration: '3m 22s', agent: 'Pipeline v3', created: '2 days ago' },
  { id: 'b4', number: 9, status: 'success' as const, duration: '7m 58s', agent: 'Pipeline v2', created: '5 days ago' },
]

const statusStyles: Record<string, { color: string; bg: string; border: string; label: string }> = {
  success: { color: '#3dffa0', bg: 'rgba(61,255,160,0.1)', border: 'rgba(61,255,160,0.2)', label: '✓ Success' },
  failed: { color: '#ff6b35', bg: 'rgba(255,107,53,0.1)', border: 'rgba(255,107,53,0.2)', label: '✕ Failed' },
  building: { color: '#63d9ff', bg: 'rgba(99,217,255,0.1)', border: 'rgba(99,217,255,0.2)', label: '◎ Building' },
}

export default function BuildsPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/projects/${id}`)}>← Project</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', margin: 0 }}>Builds</h1>
        <span className="tag tag-muted">/builds</span>
      </div>

      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              {['Build', 'Status', 'Duration', 'Agent', 'Created'].map((h) => (
                <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', fontWeight: 500 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mockBuilds.map((b) => {
              const st = statusStyles[b.status]
              return (
                <tr key={b.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '12px 16px', fontSize: 12, fontWeight: 700 }}>#{b.number}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: st.color, background: st.bg, border: `1px solid ${st.border}` }}>{st.label}</span>
                  </td>
                  <td style={{ padding: '12px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(232,232,240,0.50)' }}>{b.duration}</td>
                  <td style={{ padding: '12px 16px', fontSize: 11, color: 'rgba(232,232,240,0.50)' }}>{b.agent}</td>
                  <td style={{ padding: '12px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.35)' }}>{b.created}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
