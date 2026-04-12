const integrations = [
  { name: 'GitHub', icon: '🐙', desc: 'Push generated code to repositories', connected: true, status: 'Connected as @joesmith' },
  { name: 'Vercel', icon: '▲', desc: 'Deploy frontend applications', connected: true, status: 'Team: joe-dev' },
  { name: 'Netlify', icon: '🟢', desc: 'Alternative frontend deployments', connected: false, status: '' },
  { name: 'Supabase', icon: '⚡', desc: 'Database and auth for generated apps', connected: true, status: 'Project: forge-prod' },
  { name: 'Stripe', icon: '💳', desc: 'Billing integration for generated apps', connected: false, status: '' },
  { name: 'Slack', icon: '💬', desc: 'Build notifications and alerts', connected: false, status: '' },
]

export default function IntegrationsPage() {
  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>
        Integrations <span className="tag tag-forge" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Settings</span>
      </h1>
      <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 22 }}>Connect third-party services to enhance your workflow</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {integrations.map(i => (
          <div key={i.name} className="card" style={{ padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>{i.icon}</div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>{i.name}</span>
                  {i.connected && <span className="tag tag-jade">Connected</span>}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{i.connected ? i.status : i.desc}</div>
              </div>
            </div>
            {i.connected ? (
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn btn-ghost btn-sm">Configure</button>
                <button className="btn btn-ghost btn-sm" style={{ color: 'var(--ember)', borderColor: 'rgba(255,107,53,0.22)' }}>Disconnect</button>
              </div>
            ) : (
              <button className="btn btn-ghost btn-sm" style={{ color: 'var(--forge)', borderColor: 'rgba(99,217,255,0.22)' }}>Connect →</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
