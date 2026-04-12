import { useState } from 'react'

interface Route {
  stage: string
  provider: string
  model: string
  fallback: string
  cost: string
}

const initialRoutes: Route[] = [
  { stage: 'Input Layer', provider: 'Anthropic', model: 'claude-sonnet-4-20250514', fallback: 'gpt-4o', cost: '$0.04' },
  { stage: 'C-Suite Analysis', provider: 'Anthropic', model: 'claude-sonnet-4-20250514', fallback: 'claude-3-haiku', cost: '$0.32' },
  { stage: 'Synthesis', provider: 'Anthropic', model: 'claude-sonnet-4-20250514', fallback: 'gpt-4o', cost: '$0.12' },
  { stage: 'Spec Layer', provider: 'OpenAI', model: 'gpt-4o', fallback: 'claude-sonnet-4-20250514', cost: '$0.08' },
  { stage: 'Bootstrap', provider: 'Anthropic', model: 'claude-sonnet-4-20250514', fallback: 'gpt-4o', cost: '$0.15' },
  { stage: 'Build', provider: 'Anthropic', model: 'claude-sonnet-4-20250514', fallback: 'gpt-4o', cost: '$0.12' },
]

const thStyle = { fontFamily: "'JetBrains Mono', monospace" as const, fontSize: 9, textTransform: 'uppercase' as const, letterSpacing: 1, color: 'rgba(232,232,240,0.42)', padding: '10px 14px', textAlign: 'left' as const, borderBottom: '1px solid rgba(255,255,255,0.06)' }
const tdStyle = { padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.04)' }
const selectStyle = { background: '#080812', border: '1px solid rgba(255,255,255,0.08)', color: '#e8e8f0', padding: '4px 9px', borderRadius: 5, fontSize: 11, outline: 'none' }

export default function ModelRoutingPage() {
  const [routes] = useState(initialRoutes)

  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>
        Model Routing <span className="tag tag-forge" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Settings</span>
      </h1>
      <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 22 }}>Configure which AI models handle each pipeline stage</p>

      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>Stage</th>
              <th style={thStyle}>Provider</th>
              <th style={thStyle}>Model</th>
              <th style={thStyle}>Fallback</th>
              <th style={thStyle}>Est. Cost</th>
            </tr>
          </thead>
          <tbody>
            {routes.map(r => (
              <tr key={r.stage}>
                <td style={{ ...tdStyle, fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>{r.stage}</td>
                <td style={tdStyle}><select style={selectStyle} defaultValue={r.provider}><option>Anthropic</option><option>OpenAI</option><option>Google AI</option></select></td>
                <td style={tdStyle}><select style={selectStyle} defaultValue={r.model}><option>claude-sonnet-4-20250514</option><option>gpt-4o</option><option>claude-3-haiku</option></select></td>
                <td style={tdStyle}><select style={selectStyle} defaultValue={r.fallback}><option>gpt-4o</option><option>claude-sonnet-4-20250514</option><option>claude-3-haiku</option></select></td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#63d9ff', fontWeight: 700 }}>{r.cost}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Cost estimator */}
      <div style={{ marginTop: 18, background: 'rgba(99,217,255,0.06)', border: '1px solid rgba(99,217,255,0.18)', borderRadius: 10, padding: 18 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#63d9ff', marginBottom: 4 }}>Estimated cost per full pipeline run</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: '#63d9ff', letterSpacing: '-1px' }}>~$0.83</div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>vs. $2.40 with all-Opus · 60% saved via semantic cache</div>
      </div>

      <button className="btn btn-primary" style={{ marginTop: 18 }}>Save Routing</button>
    </div>
  )
}
