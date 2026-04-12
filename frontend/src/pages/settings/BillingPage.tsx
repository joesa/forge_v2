const usage = [
  { label: 'Tokens Used', value: '847k', max: '2M', pct: 42 },
  { label: 'Builds', value: '38', max: '∞', pct: 0 },
  { label: 'Deployments', value: '14', max: '∞', pct: 0 },
  { label: 'Storage', value: '2.1 GB', max: '10 GB', pct: 21 },
]

const invoices = [
  { date: 'Jan 1, 2025', amount: '$49.00', status: 'Paid' },
  { date: 'Dec 1, 2024', amount: '$49.00', status: 'Paid' },
  { date: 'Nov 1, 2024', amount: '$49.00', status: 'Paid' },
]

const thStyle = { fontFamily: "'JetBrains Mono', monospace" as const, fontSize: 9, textTransform: 'uppercase' as const, letterSpacing: 1, color: 'rgba(232,232,240,0.42)', padding: '10px 14px', textAlign: 'left' as const, borderBottom: '1px solid rgba(255,255,255,0.06)' }
const tdStyle = { padding: '10px 14px', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)' }

export default function BillingPage() {
  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 22 }}>
        Billing <span className="tag tag-forge" style={{ marginLeft: 8, verticalAlign: 'middle' }}>Settings</span>
      </h1>

      {/* Plan card */}
      <div style={{ background: 'linear-gradient(135deg, rgba(99,217,255,0.06), rgba(176,107,255,0.06))', border: '1px solid rgba(99,217,255,0.20)', borderRadius: 14, padding: 26, marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 4 }}>CURRENT PLAN</div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.5px' }}>Pro Plan</div>
          <div style={{ fontSize: 14, color: 'var(--muted)', marginTop: 2 }}>$49/month</div>
        </div>
        <button className="btn btn-primary">Manage Subscription →</button>
      </div>

      {/* Usage grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 18 }}>
        {usage.map(u => (
          <div key={u.label} className="card" style={{ padding: 16 }}>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 6 }}>{u.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.5px' }}>{u.value}<span style={{ fontSize: 11, fontWeight: 400, color: 'var(--muted)' }}> / {u.max}</span></div>
            {u.pct > 0 && (
              <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.08)', marginTop: 8 }}>
                <div style={{ height: '100%', borderRadius: 2, background: '#63d9ff', width: `${u.pct}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Invoice table */}
      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>Date</th>
              <th style={thStyle}>Amount</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Download</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map(inv => (
              <tr key={inv.date}>
                <td style={tdStyle}>{inv.date}</td>
                <td style={{ ...tdStyle, fontWeight: 600 }}>{inv.amount}</td>
                <td style={tdStyle}><span className="tag tag-jade">{inv.status}</span></td>
                <td style={tdStyle}><span style={{ color: '#63d9ff', cursor: 'pointer', fontSize: 11 }}>Download PDF</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
