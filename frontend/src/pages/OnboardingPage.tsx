import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'

const startOptions = [
  { icon: '✍️', title: 'I have an idea', desc: 'Describe my app and FORGE builds it' },
  { icon: '💡', title: 'Help me find an idea', desc: 'Answer questions, get 5 AI-generated ideas' },
  { icon: '🎲', title: 'Surprise me', desc: 'AI generates ideas with zero input from me' },
]

const providers = [
  { name: 'Anthropic', note: 'FORGE Default — no key needed', connected: true },
  { name: 'OpenAI', note: 'Add your API key', connected: false },
  { name: 'Gemini', note: 'Add your API key', connected: false },
]

function ProgressPills({ step }: { step: number }) {
  return (
    <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: 28 }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: i < step ? 8 : i === step ? 28 : 8,
            height: 8,
            borderRadius: i === step ? 4 : '50%',
            background: i < step ? '#3dffa0' : i === step ? '#63d9ff' : 'rgba(255,255,255,0.12)',
            transition: 'all 0.25s ease',
          }}
        />
      ))}
    </div>
  )
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [selectedStart, setSelectedStart] = useState(0)

  return (
    <div className="grid-bg" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#04040a' }}>
      {/* Simplified nav */}
      <nav style={{ height: 62, padding: '0 28px', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
        </Link>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>Step {step + 1} of 3</span>
      </nav>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 20px' }}>
        <div style={{ width: '100%', maxWidth: 580 }}>
          <ProgressPills step={step} />

          <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 36, animation: 'fade-in 280ms ease' }} key={step}>
            {step === 0 && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 44, marginBottom: 14 }}>⬡</div>
                <h2 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.8px', marginBottom: 9, color: 'var(--text)' }}>Welcome to FORGE</h2>
                <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.45)', lineHeight: 1.7, marginBottom: 24 }}>
                  The AI-native platform that builds production apps for you.
                  Let&apos;s get you set up in 2 minutes.
                </p>
                <button className="btn btn-primary" style={{ width: '100%', height: 48 }} onClick={() => setStep(1)}>Let&apos;s go →</button>
              </div>
            )}

            {step === 1 && (
              <>
                <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 5, color: 'var(--text)' }}>How do you want to start?</h2>
                <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 20 }}>You can always change this later</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 9, marginBottom: 22 }}>
                  {startOptions.map((opt, i) => (
                    <div
                      key={opt.title}
                      onClick={() => setSelectedStart(i)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 13, textAlign: 'left',
                        background: selectedStart === i ? 'rgba(99,217,255,0.08)' : 'rgba(255,255,255,0.03)',
                        border: `2px solid ${selectedStart === i ? '#63d9ff' : 'rgba(255,255,255,0.06)'}`,
                        borderRadius: 10, padding: '13px 16px', cursor: 'pointer', transition: 'all 200ms',
                      }}
                    >
                      <span style={{ fontSize: 22, flexShrink: 0 }}>{opt.icon}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 700 }}>{opt.title}</div>
                        <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>{opt.desc}</div>
                      </div>
                      {selectedStart === i && <span style={{ color: '#63d9ff', fontSize: 16 }}>✓</span>}
                    </div>
                  ))}
                </div>
                <button className="btn btn-primary" style={{ width: '100%', height: 48 }} onClick={() => setStep(2)}>Continue →</button>
              </>
            )}

            {step === 2 && (
              <>
                <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 5, color: 'var(--text)' }}>Connect an AI provider</h2>
                <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', marginBottom: 20 }}>
                  FORGE includes Anthropic Claude on Free tier. Add your keys for unlimited usage.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 22 }}>
                  {providers.map((p) => (
                    <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 11, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, padding: '11px 13px' }}>
                      <div style={{ width: 18, height: 18, borderRadius: 4, background: 'rgba(255,255,255,0.08)', flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>{p.name}</div>
                        <div style={{ fontSize: 10, color: 'rgba(232,232,240,0.42)' }}>{p.note}</div>
                      </div>
                      {p.connected ? (
                        <span className="tag tag-jade">Active</span>
                      ) : (
                        <button className="btn btn-ghost btn-sm">Add Key</button>
                      )}
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 9 }}>
                  <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => navigate('/dashboard')}>Skip for now</button>
                  <button className="btn btn-primary" style={{ flex: 1, height: 48 }} onClick={() => navigate('/dashboard')}>Get Started →</button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
