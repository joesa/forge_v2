import { useState } from 'react'

export default function ProfilePage() {
  const [name, setName] = useState('Joe Smith')
  const [tz, setTz] = useState('America/New_York')

  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Profile</h1>
      <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 26 }}>Manage your account settings</p>

      {/* Avatar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 26 }}>
        <div style={{ width: 68, height: 68, borderRadius: '50%', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 700, color: 'var(--void)' }}>JS</div>
        <div>
          <button className="btn btn-ghost btn-sm">Upload Photo</button>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 5 }}>JPG, PNG or GIF · Max 2MB</p>
        </div>
      </div>

      {/* Form */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 480 }}>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 5, display: 'block' }}>Display Name</label>
          <input className="input" value={name} onChange={e => setName(e.target.value)} />
        </div>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 5, display: 'block' }}>Email</label>
          <input className="input" value="joe@example.com" disabled style={{ opacity: 0.6 }} />
        </div>
        <div>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 5, display: 'block' }}>Timezone</label>
          <select className="input" value={tz} onChange={e => setTz(e.target.value)} style={{ cursor: 'pointer' }}>
            <option value="America/New_York">America/New_York</option>
            <option value="America/Chicago">America/Chicago</option>
            <option value="America/Los_Angeles">America/Los_Angeles</option>
            <option value="Europe/London">Europe/London</option>
            <option value="Asia/Tokyo">Asia/Tokyo</option>
          </select>
        </div>
        <button className="btn btn-primary" style={{ width: 'fit-content' }}>Save Changes</button>
      </div>

      {/* Danger Zone */}
      <div style={{ marginTop: 28, background: 'rgba(255,107,53,0.08)', border: '1px solid rgba(255,107,53,0.20)', borderRadius: 10, padding: 18 }}>
        <h3 style={{ fontSize: 12, fontWeight: 700, color: '#ff6b35', marginBottom: 6 }}>Danger Zone</h3>
        <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>Permanently delete your account and all associated data. This action cannot be undone.</p>
        <button className="btn btn-ghost btn-sm" style={{ color: '#ff6b35', borderColor: 'rgba(255,107,53,0.22)' }}>Delete Account</button>
      </div>
    </div>
  )
}
