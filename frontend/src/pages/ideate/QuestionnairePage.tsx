import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '@/api/client'

type AnswerType = 'chips' | 'grid' | 'slider' | 'text'

interface Question {
  step: string
  text: string
  type: AnswerType
  options?: string[]
  range?: { min: string; max: string }
  placeholder?: string
}

const questions: Question[] = [
  { step: '01', text: 'What kind of product excites you most?', type: 'chips', options: ['SaaS', 'Marketplace', 'Social', 'Developer Tool', 'E-commerce', 'AI/ML', 'Fintech', 'Health'] },
  { step: '02', text: 'Who is your ideal customer?', type: 'grid', options: ['Developers', 'Small Business', 'Enterprise', 'Consumers'] },
  { step: '03', text: 'What\'s your technical comfort level?', type: 'slider', range: { min: 'Beginner', max: 'Expert' } },
  { step: '04', text: 'Describe a problem you\'d love to solve', type: 'text', placeholder: 'A frustration you encounter daily...' },
  { step: '05', text: 'Which industries interest you?', type: 'chips', options: ['Healthcare', 'Education', 'Finance', 'Real Estate', 'Travel', 'Food', 'Entertainment', 'Sustainability'] },
  { step: '06', text: 'What\'s your preferred business model?', type: 'grid', options: ['Subscription', 'Freemium', 'Marketplace Fee', 'One-time Purchase'] },
  { step: '07', text: 'How much time can you invest weekly?', type: 'slider', range: { min: '2 hours', max: '40+ hours' } },
  { step: '08', text: 'Any specific features or integrations in mind?', type: 'text', placeholder: 'e.g., Stripe payments, AI chat, real-time collaboration...' },
]

export default function QuestionnairePage() {
  const navigate = useNavigate()
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string[] | string>>({})
  const [sliderVal, setSliderVal] = useState(50)

  const q = questions[current]
  const selected = (answers[current] as string[] | undefined) ?? []

  const toggleChip = useCallback((chip: string) => {
    const prev = (answers[current] as string[] | undefined) ?? []
    setAnswers(a => ({ ...a, [current]: prev.includes(chip) ? prev.filter(c => c !== chip) : [...prev, chip] }))
  }, [answers, current])

  const selectGrid = useCallback((opt: string) => {
    setAnswers(a => ({ ...a, [current]: [opt] }))
  }, [current])

  const [submitting, setSubmitting] = useState(false)

  const submitAnswers = useCallback(async (finalAnswers: Record<number, string[] | string>) => {
    setSubmitting(true)
    try {
      // Map numeric indices to question labels
      const labeled: Record<string, string[] | string> = {}
      questions.forEach((q, i) => {
        if (finalAnswers[i] !== undefined) {
          labeled[q.text] = finalAnswers[i]
        }
      })
      const { data } = await apiClient.post<{ session_id: string }>('/ideas/generate', { answers: labeled })
      navigate(`/ideate/ideas/generated?session=${data.session_id}`)
    } catch {
      // Fallback: navigate without session (will show error state)
      navigate('/ideate/ideas/generated')
    } finally {
      setSubmitting(false)
    }
  }, [navigate])

  const next = () => {
    const updated = { ...answers }
    if (q.type === 'slider') updated[current] = [String(sliderVal)]
    setAnswers(updated)
    if (current < questions.length - 1) {
      setCurrent(c => c + 1)
    } else {
      void submitAnswers(updated)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--void)', display: 'flex', flexDirection: 'column' }}>
      {/* Nav */}
      <nav style={{ height: 62, display: 'flex', alignItems: 'center', padding: '0 28px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 18, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
        </div>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.35)' }}>Question {current + 1} of {questions.length}</span>
        </div>
        <button className="btn btn-ghost btn-sm" style={{ color: 'var(--ember)', borderColor: 'rgba(255,107,53,0.22)' }} onClick={() => void submitAnswers(answers)}>Skip All →</button>
      </nav>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 20px' }}>
        {/* Progress pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center', marginBottom: 28 }}>
          {questions.map((_, i) => (
            <div key={i} style={{
              width: i === current ? 28 : 8, height: 8,
              borderRadius: i === current ? 4 : '50%',
              background: i < current ? '#3dffa0' : i === current ? '#63d9ff' : 'rgba(255,255,255,0.12)',
              transition: 'all 0.25s',
            }} />
          ))}
        </div>

        {/* Question card */}
        <div className="card" key={current} style={{ maxWidth: 620, width: '100%', padding: 36, animation: 'fade-in 280ms ease' }}>
          <div style={{ fontSize: 52, fontWeight: 800, letterSpacing: '-2px', color: 'rgba(232,232,240,0.10)', lineHeight: 1, marginBottom: 7 }}>{q.step}</div>
          <div style={{ fontSize: 21, fontWeight: 700, letterSpacing: '-0.5px', marginBottom: 22, color: 'var(--text)' }}>{q.text}</div>

          {/* Answer type A — chips */}
          {q.type === 'chips' && q.options && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 26 }}>
              {q.options.map(chip => (
                <span
                  key={chip}
                  onClick={() => toggleChip(chip)}
                  style={{
                    padding: '7px 15px', borderRadius: 20, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    border: selected.includes(chip) ? '1px solid #63d9ff' : '1px solid rgba(255,255,255,0.08)',
                    color: selected.includes(chip) ? '#63d9ff' : 'rgba(232,232,240,0.50)',
                    background: selected.includes(chip) ? 'rgba(99,217,255,0.10)' : 'transparent',
                  }}
                >{chip}</span>
              ))}
            </div>
          )}

          {/* Answer type B — grid */}
          {q.type === 'grid' && q.options && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9, marginBottom: 26 }}>
              {q.options.map(opt => (
                <div
                  key={opt}
                  onClick={() => selectGrid(opt)}
                  style={{
                    textAlign: 'center', padding: '13px 16px', borderRadius: 10, cursor: 'pointer',
                    border: selected.includes(opt) ? '2px solid #63d9ff' : '2px solid rgba(255,255,255,0.06)',
                    background: selected.includes(opt) ? 'rgba(99,217,255,0.08)' : 'transparent',
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)' }}>{opt}</div>
                </div>
              ))}
            </div>
          )}

          {/* Answer type C — slider */}
          {q.type === 'slider' && q.range && (
            <div style={{ marginBottom: 26 }}>
              <input type="range" min={0} max={100} value={sliderVal} onChange={e => setSliderVal(Number(e.target.value))} style={{ width: '100%', accentColor: '#63d9ff' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'rgba(232,232,240,0.40)' }}>
                <span>{q.range.min}</span><span>{q.range.max}</span>
              </div>
            </div>
          )}

          {/* Answer type D — text */}
          {q.type === 'text' && (
            <textarea
              className="input"
              rows={3}
              placeholder={q.placeholder}
              value={(answers[current] as string) ?? ''}
              onChange={e => setAnswers(a => ({ ...a, [current]: e.target.value }))}
              style={{ width: '100%', resize: 'none', height: 'auto', marginBottom: 26 }}
            />
          )}

          {/* Bottom row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button className="btn btn-ghost" onClick={() => setCurrent(c => Math.max(0, c - 1))} style={{ opacity: current === 0 ? 0.3 : 1 }}>← Back</button>
            <button className="btn btn-ghost btn-sm" style={{ color: 'rgba(232,232,240,0.40)' }} onClick={next}>Skip this →</button>
            <button className="btn btn-primary" onClick={next} disabled={submitting}>
              {submitting ? 'Generating…' : current === questions.length - 1 ? 'Generate Ideas →' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
