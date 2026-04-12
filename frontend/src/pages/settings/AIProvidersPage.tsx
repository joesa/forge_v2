import { useState } from 'react'

interface Provider {
  name: string
  logo: string
  connected: boolean
  isDefault?: boolean
  prefix?: string
  latency?: string
  models?: number
}

const providers: Provider[] = [
  { name: 'Anthropic', logo: '🤖', connected: true, isDefault: true, prefix: 'sk-ant-...c3x1', latency: '142ms', models: 8 },
  { name: 'OpenAI', logo: '🟢', connected: true, prefix: 'sk-...m9k2', latency: '98ms', models: 12 },
  { name: 'Google AI', logo: '🔷', connected: false },
  { name: 'Mistral', logo: '🌀', connected: false },
  { name: 'Cohere', logo: '🟣', connected: false },
  { name: 'Groq', logo: '⚡', connected: false },
  { name: 'Together AI', logo: '🔗', connected: false },
  { name: 'Fireworks', logo: '🎆', connected: false },
]

export default function AIProvidersPage() {
  const [modal, setModal] = useState<Provider | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [testResult, setTestResult] = useState<'idle' | 'success' | 'error'>('idle')

  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>
        AI Providers <span className="tag tag-forge" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Settings</span>
      </h1>
      <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 26 }}>Connect your API keys · All keys encrypted with AES-256-GCM</p>

      {/* Provider grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {providers.map(p => (
          <div key={p.name} className="card" style={{ padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>{p.logo}</div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>{p.name}</span>
                  {p.isDefault && <span className="tag tag-forge">Default</span>}
                  {p.connected && !p.isDefault && <span className="tag tag-jade">Connected</span>}
                </div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: p.connected ? 'rgba(232,232,240,0.35)' : 'rgba(232,232,240,0.30)' }}>
                  {p.connected ? `${p.prefix} · ${p.latency}` : 'Not connected'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {p.connected ? (
                <>
                  <button className="btn btn-ghost btn-sm">Edit</button>
                  <button className="btn btn-ghost btn-sm" style={{ color: 'var(--ember)', borderColor: 'rgba(255,107,53,0.22)' }}>Test</button>
                </>
              ) : (
                <button className="btn btn-ghost btn-sm" style={{ color: 'var(--forge)', borderColor: 'rgba(99,217,255,0.22)' }} onClick={() => { setModal(p); setApiKey(''); setTestResult('idle') }}>Connect →</button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Connect Modal */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div className="card" style={{ padding: 34, maxWidth: 460, border: '1px solid rgba(99,217,255,0.22)', borderRadius: 16 }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>{modal.logo}</div>
              <h2 style={{ fontSize: 18, fontWeight: 700 }}>Connect {modal.name}</h2>
            </div>

            {testResult === 'success' ? (
              <div style={{ background: 'rgba(61,255,160,0.08)', border: '1px solid rgba(61,255,160,0.18)', borderRadius: 8, padding: 14, textAlign: 'center' }}>
                <span style={{ color: '#3dffa0', fontSize: 13, fontWeight: 700 }}>✓ Connected — {modal.models ?? 8} models · {modal.latency ?? '120ms'}</span>
              </div>
            ) : testResult === 'error' ? (
              <div style={{ background: 'rgba(255,107,53,0.08)', border: '1px solid rgba(255,107,53,0.18)', borderRadius: 8, padding: 14, textAlign: 'center', marginBottom: 14 }}>
                <span style={{ color: '#ff6b35', fontSize: 13, fontWeight: 700 }}>✗ Invalid API key</span>
              </div>
            ) : null}

            {testResult !== 'success' && (
              <>
                <div style={{ marginBottom: 14 }}>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 5, display: 'block' }}>API Key</label>
                  <input className="input" type="password" placeholder="Enter your API key" value={apiKey} onChange={e => setApiKey(e.target.value)} />
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => setTestResult(apiKey.length > 5 ? 'success' : 'error')}>Test Connection</button>
                  <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => setTestResult(apiKey.length > 5 ? 'success' : 'error')}>Save</button>
                </div>
              </>
            )}

            {testResult === 'success' && (
              <button className="btn btn-primary" style={{ width: '100%', marginTop: 14 }} onClick={() => setModal(null)}>Done</button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
