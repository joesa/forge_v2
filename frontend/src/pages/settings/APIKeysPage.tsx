import { useState } from 'react'

interface ApiKey { name: string; prefix: string; lastUsed: string; expires: string }

const mockKeys: ApiKey[] = [
  { name: 'Production', prefix: 'fk_prod_...x8m2', lastUsed: '2 hours ago', expires: 'Never' },
  { name: 'Development', prefix: 'fk_dev_...k3n1', lastUsed: '5 days ago', expires: '2025-03-15' },
  { name: 'CI/CD Pipeline', prefix: 'fk_ci_...p7q4', lastUsed: '12 hours ago', expires: '2025-06-01' },
]

const thStyle = { fontFamily: "'JetBrains Mono', monospace" as const, fontSize: 9, textTransform: 'uppercase' as const, letterSpacing: 1, color: 'rgba(232,232,240,0.42)', padding: '10px 14px', textAlign: 'left' as const, borderBottom: '1px solid rgba(255,255,255,0.06)' }
const tdStyle = { padding: '10px 14px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)' }

export default function APIKeysPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [showReveal, setShowReveal] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [newKeyExpiry, setNewKeyExpiry] = useState('never')
  const [copied, setCopied] = useState(false)

  const generatedKey = 'fk_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0'

  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 4 }}>
            API Keys <span className="tag tag-forge" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Settings</span>
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>Manage API keys for programmatic access</p>
        </div>
        <button className="btn btn-primary" onClick={() => { setShowCreate(true); setNewKeyName(''); setNewKeyExpiry('never') }}>+ Create API Key</button>
      </div>

      {/* Keys table */}
      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>Prefix</th>
              <th style={thStyle}>Last Used</th>
              <th style={thStyle}>Expires</th>
              <th style={thStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {mockKeys.map(k => (
              <tr key={k.prefix}>
                <td style={{ ...tdStyle, fontWeight: 600 }}>{k.name}</td>
                <td style={{ ...tdStyle, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--muted)' }}>{k.prefix}</td>
                <td style={{ ...tdStyle, color: 'var(--muted)' }}>{k.lastUsed}</td>
                <td style={tdStyle}>{k.expires}</td>
                <td style={tdStyle}><button className="btn btn-ghost btn-sm" style={{ color: 'var(--ember)', borderColor: 'rgba(255,107,53,0.22)' }}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setShowCreate(false)}>
          <div className="card" style={{ padding: 34, maxWidth: 420, border: '1px solid rgba(99,217,255,0.22)', borderRadius: 16 }} onClick={e => e.stopPropagation()}>
            <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 18 }}>Create API Key</h2>
            <div style={{ marginBottom: 14 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 5, display: 'block' }}>Key Name</label>
              <input className="input" placeholder="e.g., Production" value={newKeyName} onChange={e => setNewKeyName(e.target.value)} />
            </div>
            <div style={{ marginBottom: 18 }}>
              <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 5, display: 'block' }}>Expires</label>
              <select className="input" value={newKeyExpiry} onChange={e => setNewKeyExpiry(e.target.value)} style={{ cursor: 'pointer' }}>
                <option value="never">Never</option>
                <option value="30d">30 days</option>
                <option value="90d">90 days</option>
              </select>
            </div>
            <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => { setShowCreate(false); setShowReveal(true); setCopied(false) }}>Create</button>
          </div>
        </div>
      )}

      {/* Reveal modal */}
      {showReveal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ padding: 34, maxWidth: 480, border: '1px solid rgba(99,217,255,0.22)', borderRadius: 16 }}>
            <p style={{ fontSize: 11, color: '#f5c842', fontWeight: 700, marginBottom: 14 }}>⚠️ This key will only be shown once</p>
            <div style={{ background: '#04040a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '12px 14px', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#63d9ff', wordBreak: 'break-all', marginBottom: 14 }}>{generatedKey}</div>
            <button className="btn btn-primary" style={{ width: '100%', marginBottom: 8 }} onClick={() => { void navigator.clipboard.writeText(generatedKey); setCopied(true) }}>
              {copied ? '✓ Copied!' : '⎘ Copy to Clipboard'}
            </button>
            <button className="btn btn-ghost" style={{ width: '100%' }} onClick={() => setShowReveal(false)}>I&apos;ve saved this key safely</button>
          </div>
        </div>
      )}
    </div>
  )
}
