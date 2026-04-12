import { useNavigate } from 'react-router-dom'

const stats = [
  { value: '26+', label: 'AI Agents' },
  { value: '10', label: 'Reliability Layers' },
  { value: '12', label: 'Validation Gates' },
  { value: '0', label: 'Broken Builds' },
  { value: '1M+', label: 'Req/Day' },
  { value: '<700ms', label: 'Preview' },
]

const pricingPlans = [
  {
    name: 'Free',
    price: '$0',
    featured: false,
    features: ['3 projects', '500k tokens/month', 'Community support', 'Shared sandboxes', 'Basic analytics'],
    cta: 'Get Started',
  },
  {
    name: 'Pro',
    price: '$49',
    featured: true,
    features: ['Unlimited projects', '2M tokens/month', 'Priority support', 'Dedicated sandboxes', 'Advanced analytics', 'Custom domains', 'Team collaboration'],
    cta: 'Start Pro Trial',
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    featured: false,
    features: ['Everything in Pro', 'Unlimited tokens', 'SLA guarantee', 'SSO / SAML', 'Dedicated infrastructure', 'Custom integrations'],
    cta: 'Contact Sales',
  },
]

function LandingNav() {
  return (
    <nav
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        height: 62, padding: '0 28px',
        background: 'rgba(4,4,10,0.88)', backdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
        <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: 'flex', gap: 9 }}>
        <a href="/login" className="btn btn-ghost btn-sm">Log In</a>
        <a href="/register" className="btn btn-primary btn-sm">Start Building →</a>
      </div>
    </nav>
  )
}

function GlowOrbs() {
  return (
    <>
      <div style={{ position: 'absolute', top: '-10%', right: '-5%', width: 700, height: 700, borderRadius: '50%', background: 'rgba(176,107,255,0.04)', filter: 'blur(130px)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: '-10%', left: '-5%', width: 550, height: 550, borderRadius: '50%', background: 'rgba(99,217,255,0.04)', filter: 'blur(130px)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: '40%', left: '40%', width: 350, height: 350, borderRadius: '50%', background: 'rgba(255,107,53,0.03)', filter: 'blur(130px)', pointerEvents: 'none' }} />
    </>
  )
}

export default function LandingPage() {
  const navigate = useNavigate()

  return (
    <div style={{ background: '#04040a', minHeight: '100vh', position: 'relative', overflow: 'hidden' }}>
      <LandingNav />

      {/* ── Hero Section (100vh) ─────────────────────────────── */}
      <section className="grid-bg" style={{ minHeight: '100vh', position: 'relative', display: 'flex', alignItems: 'center' }}>
        <GlowOrbs />
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '100px 32px 72px', position: 'relative', zIndex: 1, width: '100%' }}>
          {/* Eyebrow */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
            <div style={{ width: 28, height: 1, background: '#63d9ff' }} />
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: 3, textTransform: 'uppercase', color: '#63d9ff' }}>
              AI-Native Development Platform
            </span>
          </div>

          {/* h1 */}
          <h1 style={{ fontSize: 'clamp(48px,6.5vw,86px)', fontWeight: 800, letterSpacing: -3, lineHeight: 0.92, color: 'var(--text)', margin: 0 }}>
            Build anything.<br />
            <span style={{ fontFamily: "'Instrument Serif', serif", fontStyle: 'italic', color: '#63d9ff' }}>Ship</span>{' '}
            <span style={{ color: '#ff6b35' }}>everything.</span>
          </h1>

          {/* Subtitle */}
          <p style={{ fontSize: 16, color: 'rgba(232,232,240,0.45)', maxWidth: 580, lineHeight: 1.7, marginTop: 20, marginBottom: 34 }}>
            FORGE takes your idea through a C-Suite of AI agents, a 10-layer
            reliability system, and delivers a live production application —
            zero broken builds, guaranteed.
          </p>

          {/* CTA row */}
          <div style={{ display: 'flex', gap: 11, flexWrap: 'wrap' }}>
            <button className="btn btn-primary btn-lg" onClick={() => navigate('/register')}>Start Building →</button>
            <button className="btn btn-ghost btn-lg" onClick={() => navigate('/ideate')}>💡 Generate an Idea</button>
          </div>

          {/* Stats row */}
          <div style={{ display: 'flex', gap: 36, paddingTop: 40, borderTop: '1px solid rgba(255,255,255,0.06)', marginTop: 52, flexWrap: 'wrap' }}>
            {stats.map((s) => (
              <div key={s.label}>
                <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, background: 'linear-gradient(135deg, #63d9ff, #3dffa0)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  {s.value}
                </div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.42)', marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Three Paths Section ──────────────────────────────── */}
      <section style={{ background: '#0d0d1f', borderTop: '1px solid rgba(255,255,255,0.06)', padding: '72px 0' }}>
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px' }}>
          <div className="section-label" style={{ color: 'var(--ember)' }}>Core Flow</div>
          <h2 style={{ fontSize: 'clamp(24px,3.2vw,34px)', fontWeight: 800, letterSpacing: '-1.2px', color: 'var(--text)', margin: '0 0 28px' }}>
            Every path leads to production
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <div className="card fa" style={{ cursor: 'pointer' }} onClick={() => navigate('/projects/new')}>
              <div style={{ fontSize: 22, marginBottom: 9 }}>✍️</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Direct Prompt</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', lineHeight: 1.5, marginBottom: 12 }}>
                Describe your app. AI optionally enriches it before the pipeline.
              </div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                <span className="tag tag-forge">Instant</span>
                <span className="tag tag-jade">AI Enhancement</span>
              </div>
            </div>

            <div className="card va" style={{ cursor: 'pointer' }} onClick={() => navigate('/ideate')}>
              <div style={{ fontSize: 22, marginBottom: 9 }}>💡</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>AI Ideation Engine</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', lineHeight: 1.5, marginBottom: 12 }}>
                8 adaptive questions, all skippable → 5 unique high-value ideas.
              </div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                <span className="tag tag-violet">5 Ideas</span>
                <span className="tag tag-gold">Skippable Q&A</span>
                <span className="tag tag-ember">Private 7d</span>
              </div>
            </div>

            <div className="card ea" style={{ cursor: 'pointer' }} onClick={() => navigate('/ideate')}>
              <div style={{ fontSize: 22, marginBottom: 9 }}>🎲</div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Full AI Generation</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', lineHeight: 1.5, marginBottom: 12 }}>
                Zero input. AI generates ideas from live market signals.
              </div>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                <span className="tag tag-ember">Zero Input</span>
                <span className="tag tag-forge">Market-Aware</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Preview System Highlight ─────────────────────────── */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px 72px' }}>
        <div style={{
          background: 'linear-gradient(135deg, rgba(99,217,255,0.04), rgba(4,4,10,0.9))',
          border: '1px solid rgba(99,217,255,0.12)',
          borderRadius: 16, padding: 36, marginTop: 72,
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, alignItems: 'center',
        }}>
          <div>
            <div className="section-label" style={{ color: 'var(--jade)' }}>Live Preview System</div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: 'var(--text)', margin: '0 0 18px' }}>
              Watch your app take shape in real time
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {[
                'HMR live reload <700ms after file save',
                'Build snapshot timeline — 10 screenshots per build',
                'Click-to-annotate overlay with AI context',
                'Dev console (logs, network, errors, source maps)',
                'Shareable preview links (24h, no auth required)',
              ].map((text) => (
                <div key={text} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'rgba(232,232,240,0.55)' }}>
                  <span style={{ color: 'var(--jade)', fontSize: 14 }}>✓</span>
                  {text}
                </div>
              ))}
            </div>
            <button className="btn btn-secondary" style={{ marginTop: 20 }} onClick={() => navigate('/register')}>
              See Editor Preview →
            </button>
          </div>
          {/* Right: Mini mockup placeholder */}
          <div style={{
            background: '#080812', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)',
            height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.20)' }}>
              ⬡ Preview Mockup
            </span>
          </div>
        </div>
      </section>

      {/* ── Pricing Section ──────────────────────────────────── */}
      <section style={{ padding: '72px 0', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '0 32px' }}>
          <div className="section-label" style={{ color: 'var(--ember)' }}>Pricing</div>
          <h2 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-1.2px', color: 'var(--text)', margin: '0 0 28px' }}>
            Simple, transparent pricing
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {pricingPlans.map((plan) => (
              <div
                key={plan.name}
                className="card"
                style={{
                  ...(plan.featured ? {
                    border: '2px solid #63d9ff',
                    transform: 'scale(1.02)',
                    background: 'linear-gradient(135deg, rgba(99,217,255,0.06), #0d0d1f)',
                  } : {}),
                  padding: 26,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)' }}>{plan.name}</span>
                  {plan.featured && <span className="tag tag-forge">MOST POPULAR</span>}
                </div>
                <div style={{ marginBottom: 14 }}>
                  <span style={{ fontSize: 30, fontWeight: 800, color: '#63d9ff', letterSpacing: -1 }}>{plan.price}</span>
                  {plan.price !== 'Custom' && <span style={{ fontSize: 14, fontWeight: 400, color: 'rgba(232,232,240,0.40)' }}>/month</span>}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 18 }}>
                  {plan.features.map((f) => (
                    <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'rgba(232,232,240,0.50)' }}>
                      <span style={{ color: 'var(--jade)' }}>✓</span> {f}
                    </div>
                  ))}
                </div>
                <button className={`btn ${plan.featured ? 'btn-primary' : 'btn-secondary'}`} style={{ width: '100%' }}>
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
