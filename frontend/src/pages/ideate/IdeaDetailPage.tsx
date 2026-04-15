import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import apiClient from '@/api/client'

interface Idea {
  id: string
  title: string
  tagline: string
  uniqueness: number
  complexity: number
  problem: string
  solution: string
  market: string
  revenue: string
  stack: string[]
  description: string
  saved: boolean
}

interface SessionResponse {
  session_id: string
  status: string
  ideas: Idea[]
}

export default function IdeaDetailPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session')
  const [ideas, setIdeas] = useState<Idea[]>([])
  const [status, setStatus] = useState<string>(sessionId ? 'generating' : 'none')
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchSession = useCallback(async (sid: string) => {
    try {
      const { data } = await apiClient.get<SessionResponse>(`/ideas/session/${sid}`)
      setStatus(data.status)
      if (data.ideas.length > 0) {
        setIdeas(data.ideas)
      }
      if (data.status === 'completed' || data.status === 'failed') {
        if (pollRef.current) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
        if (data.status === 'failed') {
          setError('Idea generation failed. Please try again.')
        }
      }
    } catch {
      setError('Failed to load ideas.')
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [])

  // If no session param, try to load the latest session
  useEffect(() => {
    if (sessionId) return
    apiClient.get<SessionResponse>('/ideas/latest').then(({ data }) => {
      if (data.session_id && data.ideas.length > 0) {
        setIdeas(data.ideas)
        setStatus(data.status)
      } else if (data.session_id && data.status === 'generating') {
        setStatus('generating')
        pollRef.current = setInterval(() => void fetchSession(data.session_id), 2000)
      } else {
        setStatus('none')
      }
    }).catch(() => setStatus('none'))
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [sessionId, fetchSession])

  // Poll for session completion when we have a session ID  
  useEffect(() => {
    if (!sessionId) return
    void fetchSession(sessionId)
    pollRef.current = setInterval(() => void fetchSession(sessionId), 2000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [sessionId, fetchSession])

  const toggleSave = async (idea: Idea, index: number) => {
    try {
      const { data } = await apiClient.patch<{ saved: boolean }>(`/ideas/${idea.id}/save`)
      setIdeas(prev => prev.map((item, i) => i === index ? { ...item, saved: data.saved } : item))
    } catch { /* ignore */ }
  }

  const handleRegenerate = async () => {
    setStatus('generating')
    setIdeas([])
    setError(null)
    try {
      const { data } = await apiClient.post<{ session_id: string }>('/ideas/generate', { answers: {} })
      pollRef.current = setInterval(() => void fetchSession(data.session_id), 2000)
    } catch {
      setError('Failed to regenerate. Please try again.')
      setStatus('none')
    }
  }

  // Loading / generating state
  if (status === 'generating' && ideas.length === 0) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{
          width: 40, height: 40,
          border: '3px solid rgba(99,217,255,0.2)',
          borderTopColor: '#63d9ff',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }} />
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)' }}>Generating your ideas…</div>
        <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.45)' }}>AI is analyzing your answers and crafting unique app ideas</div>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    )
  }

  // No ideas state
  if (status === 'none' && ideas.length === 0) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{ fontSize: 44 }}>💡</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)' }}>No ideas yet</div>
        <div style={{ fontSize: 12, color: 'rgba(232,232,240,0.45)' }}>Take the questionnaire to generate personalized app ideas</div>
        <button className="btn btn-primary" onClick={() => navigate('/ideate/questionnaire/new')}>Start Questionnaire →</button>
      </div>
    )
  }

  return (
    <div style={{ padding: '36px 40px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 26 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/ideate')}>← Ideate</button>
            <h1 style={{ fontSize: 26, fontWeight: 800 }}>Your Ideas</h1>
            <span className="tag tag-forge">AI Generated</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>{ideas.length} AI-generated ideas · Private for 7 days · Based on your answers</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => void handleRegenerate()}>↻ Regenerate All</button>
      </div>

      {error && (
        <div style={{ background: 'rgba(255,107,53,0.08)', border: '1px solid rgba(255,107,53,0.22)', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 12, color: '#ff6b35' }}>
          {error}
        </div>
      )}

      {/* Top 3 */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(ideas.length, 3)}, 1fr)`, gap: 12, marginBottom: 12 }}>
        {ideas.slice(0, 3).map((idea, i) => (
          <IdeaCard key={idea.id} idea={idea} index={i} onSave={() => void toggleSave(idea, i)} onBuild={() => navigate('/projects/new', { state: { idea } })} />
        ))}
      </div>

      {/* Remaining */}
      {ideas.length > 3 && (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(ideas.length - 3, 2)}, 1fr)`, gap: 12 }}>
          {ideas.slice(3).map((idea, i) => (
            <IdeaCard key={idea.id} idea={idea} index={i + 3} onSave={() => void toggleSave(idea, i + 3)} onBuild={() => navigate('/projects/new', { state: { idea } })} />
          ))}
        </div>
      )}

      {/* Footer */}
      <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.20)', textAlign: 'center', marginTop: 22 }}>Ideas private for 7 days · Similar ideas may surface to other users after expiry</p>
    </div>
  )
}

function IdeaCard({ idea, index, onSave, onBuild }: { idea: Idea; index: number; onSave: () => void; onBuild: () => void }) {
  return (
    <div style={{ borderRadius: 13, border: '1px solid rgba(255,255,255,0.07)', overflow: 'hidden', animation: `fade-in 280ms ease ${index * 150}ms both` }}>
      {/* Header */}
      <div style={{ background: 'linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))', padding: '16px 16px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#f5c842' }}>★ {idea.uniqueness}/10 uniqueness</span>
          <span className="tag tag-violet" style={{ fontSize: 8 }}>◆ {idea.complexity}/10</span>
        </div>
        <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.5px', marginBottom: 3 }}>{idea.title}</div>
        <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.45)', fontStyle: 'italic' }}>{idea.tagline}</div>
      </div>

      {/* Content */}
      <div style={{ padding: '13px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 3 }}>PROBLEM</div>
        <p style={{ fontSize: 11, color: 'rgba(232,232,240,0.60)', lineHeight: 1.5, marginBottom: 10 }}>{idea.problem}</p>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 3 }}>SOLUTION</div>
        <p style={{ fontSize: 11, color: 'rgba(232,232,240,0.60)', lineHeight: 1.5, marginBottom: 10 }}>{idea.solution}</p>
        <div style={{ display: 'flex', gap: 14 }}>
          <div><span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Market</span><div style={{ fontSize: 12, fontWeight: 700, color: 'var(--forge)' }}>{idea.market}</div></div>
          <div><span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Revenue</span><div style={{ fontSize: 12, fontWeight: 700, color: 'var(--forge)' }}>{idea.revenue}</div></div>
        </div>
      </div>

      {/* Tech stack */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {idea.stack.map(t => <span key={t} className="tag tag-forge">{t}</span>)}
      </div>

      {/* Actions */}
      <div style={{ padding: '10px 16px', display: 'flex', gap: 7 }}>
        <button className="btn btn-ghost btn-sm" onClick={onSave} style={{ color: idea.saved ? '#3dffa0' : undefined }}>{idea.saved ? '💾 Saved' : '💾 Save'}</button>
        <button className="btn btn-ghost btn-sm">↻</button>
        <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={onBuild}>🚀 Build This</button>
      </div>
    </div>
  )
}
