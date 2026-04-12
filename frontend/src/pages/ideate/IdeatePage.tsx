import { useNavigate } from 'react-router-dom'

const options = [
  { icon: '💡', title: 'Help me find an idea', desc: '8 adaptive questions · all skippable · 5 unique ideas generated', accent: 'va' as const, to: '/ideate/questionnaire/new' },
  { icon: '✍️', title: 'I already have an idea', desc: 'Describe it and AI will enhance it before building', accent: 'fa' as const, to: '/projects/new' },
  { icon: '🎲', title: 'Surprise me', desc: 'Zero input — AI generates from market signals instantly', accent: 'ea' as const, to: '' },
]

const accentStyles: Record<string, { bg: string; border: string }> = {
  va: { bg: 'linear-gradient(135deg, rgba(176,107,255,0.04), #0d0d1f)', border: 'rgba(176,107,255,0.16)' },
  fa: { bg: 'linear-gradient(135deg, rgba(99,217,255,0.04), #0d0d1f)', border: 'rgba(99,217,255,0.16)' },
  ea: { bg: 'linear-gradient(135deg, rgba(255,107,53,0.04), #0d0d1f)', border: 'rgba(255,107,53,0.16)' },
}

export default function IdeatePage() {
  const navigate = useNavigate()

  return (
    <div style={{ minHeight: '100vh', background: 'var(--void)' }}>
      {/* Simplified nav */}
      <nav style={{ height: 62, display: 'flex', alignItems: 'center', padding: '0 28px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 18, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dashboard')}>← Dashboard</button>
      </nav>

      {/* Content */}
      <div style={{ maxWidth: 580, margin: '0 auto', minHeight: 'calc(100vh - 112px)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 20px' }}>
        <div style={{ fontSize: 44, marginBottom: 14, textAlign: 'center' }}>💡</div>
        <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: '-1.2px', marginBottom: 10, color: 'var(--text)', textAlign: 'center' }}>What will you build?</h1>
        <p style={{ fontSize: 14, color: 'rgba(232,232,240,0.45)', textAlign: 'center', marginBottom: 44 }}>Let AI help you find your next million-dollar idea</p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: '100%' }}>
          {options.map((opt) => (
            <div
              key={opt.title}
              className="card"
              onClick={() => {
                if (opt.to) navigate(opt.to)
              }}
              style={{ background: accentStyles[opt.accent].bg, border: `1px solid ${accentStyles[opt.accent].border}`, display: 'flex', alignItems: 'center', gap: 14, padding: '18px 22px', cursor: 'pointer' }}
            >
              <span style={{ fontSize: 26, flexShrink: 0 }}>{opt.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 3 }}>{opt.title}</div>
                <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>{opt.desc}</div>
              </div>
              <span style={{ fontSize: 18, color: 'var(--forge)' }}>→</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
