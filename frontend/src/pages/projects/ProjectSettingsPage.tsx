import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

export default function ProjectSettingsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [name, setName] = useState('SaaS Dashboard')
  const [desc, setDesc] = useState('Analytics platform with real-time data visualization')

  return (
    <div style={{ padding: '34px 32px', maxWidth: 700 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/projects/${id}`)}>← Project</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', margin: 0 }}>Project Settings</h1>
        <span className="tag tag-muted">/settings</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Project Name</label>
          <input className="input" style={{ width: '100%', boxSizing: 'border-box' }} value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Description</label>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} style={{ width: '100%', boxSizing: 'border-box', resize: 'none', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '12px 14px', color: 'var(--text)', fontFamily: "'Syne', sans-serif", fontSize: 13, outline: 'none' }} />
        </div>
        <button className="btn btn-primary" style={{ width: 'fit-content' }}>Save Changes</button>
      </div>

      {/* Danger Zone */}
      <div style={{ marginTop: 36, background: 'rgba(255,107,53,0.08)', border: '1px solid rgba(255,107,53,0.20)', borderRadius: 10, padding: 18 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: '#ff6b35', marginBottom: 8 }}>Danger Zone</div>
        <p style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)', marginBottom: 12, lineHeight: 1.5 }}>Permanently delete this project and all associated builds, deployments, and data. This action cannot be undone.</p>
        <button className="btn btn-danger btn-sm">Delete Project</button>
      </div>
    </div>
  )
}
