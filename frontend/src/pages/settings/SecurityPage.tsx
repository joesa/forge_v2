import { useState } from 'react'

const sessions = [
  { device: 'Chrome on macOS', location: 'New York, US', current: true },
  { device: 'Firefox on Windows', location: 'London, UK', current: false },
  { device: 'Safari on iPhone', location: 'New York, US', current: false },
]

export default function SecurityPage() {
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')

  const strength = newPw.length >= 16 ? 4 : newPw.length >= 12 ? 3 : newPw.length >= 8 ? 2 : newPw.length > 0 ? 1 : 0

  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>
        Security <span className="tag tag-forge" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Settings</span>
      </h1>
      <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 26 }}>Manage your security settings and active sessions</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
        {/* Change Password */}
        <div className="card" style={{ padding: 22 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>Change Password</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 400 }}>
            <input className="input" type="password" placeholder="Current password" value={currentPw} onChange={e => setCurrentPw(e.target.value)} />
            <div>
              <input className="input" type="password" placeholder="New password" value={newPw} onChange={e => setNewPw(e.target.value)} />
              {newPw && (
                <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
                  {[1, 2, 3, 4].map(i => (
                    <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i <= strength ? '#63d9ff' : 'rgba(255,255,255,0.08)' }} />
                  ))}
                </div>
              )}
            </div>
            <input className="input" type="password" placeholder="Confirm new password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)} />
            <button className="btn btn-primary" style={{ width: 'fit-content' }}>Update Password</button>
          </div>
        </div>

        {/* 2FA */}
        <div className="card" style={{ padding: 22 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Two-Factor Authentication</h3>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>Authenticator App</div>
              <div style={{ fontSize: 11, color: 'var(--muted)' }}>Add an extra layer of security to your account</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="tag" style={{ background: 'rgba(255,255,255,0.05)', color: 'rgba(232,232,240,0.5)', border: '1px solid rgba(255,255,255,0.08)' }}>Disabled</span>
              <button className="btn btn-ghost btn-sm" style={{ color: 'var(--forge)', borderColor: 'rgba(99,217,255,0.22)' }}>Enable 2FA</button>
            </div>
          </div>
        </div>

        {/* Active Sessions */}
        <div className="card" style={{ padding: 22 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Active Sessions</h3>
          {sessions.map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: i < sessions.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {s.device}
                  {s.current && <span className="tag tag-jade">Current</span>}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)' }}>{s.location}</div>
              </div>
              {!s.current && <button className="btn btn-ghost btn-sm" style={{ color: 'var(--ember)', borderColor: 'rgba(255,107,53,0.22)' }}>Sign Out</button>}
            </div>
          ))}
          <button className="btn btn-ghost" style={{ color: 'var(--ember)', borderColor: 'rgba(255,107,53,0.22)', marginTop: 13 }}>Sign Out All Other Sessions</button>
        </div>
      </div>
    </div>
  )
}
