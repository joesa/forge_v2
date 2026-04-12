import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

type StageStatus = 'done' | 'running' | 'pending' | 'failed'

interface Stage { name: string; status: StageStatus; duration: string }

const stages: Stage[] = [
  { name: 'Input Layer', status: 'done', duration: '0:12' },
  { name: 'C-Suite Analysis', status: 'done', duration: '1:45' },
  { name: 'Synthesis', status: 'running', duration: '0:38' },
  { name: 'Spec Layer', status: 'pending', duration: '—' },
  { name: 'Bootstrap', status: 'pending', duration: '—' },
  { name: 'Build', status: 'pending', duration: '—' },
]

const agents = [
  { emoji: '🏗️', role: 'Architect', status: 'done' as const, output: 'Next.js 14 + Supabase stack recommended' },
  { emoji: '🎨', role: 'UX Director', status: 'done' as const, output: 'Dashboard-first layout with sidebar nav' },
  { emoji: '🔒', role: 'Security Lead', status: 'done' as const, output: 'JWT auth + RLS policies defined' },
  { emoji: '⚡', role: 'Performance', status: 'running' as const, output: '' },
  { emoji: '💰', role: 'Business Analyst', status: 'running' as const, output: '' },
  { emoji: '🧪', role: 'QA Engineer', status: 'pending' as const, output: '' },
  { emoji: '📊', role: 'Data Architect', status: 'pending' as const, output: '' },
  { emoji: '🚀', role: 'DevOps Lead', status: 'pending' as const, output: '' },
]

const logLines = [
  { time: '4:31', level: 'info', msg: 'Synthesis: Merging C-Suite outputs...' },
  { time: '4:28', level: 'success', msg: 'Security Lead: Completed analysis — 3 recommendations' },
  { time: '4:25', level: 'info', msg: 'Performance: Analyzing bundle size targets...' },
  { time: '4:20', level: 'success', msg: 'UX Director: Layout blueprint generated' },
  { time: '4:18', level: 'info', msg: 'Business Analyst: Evaluating monetization models...' },
  { time: '4:12', level: 'success', msg: 'Architect: Stack recommendation complete' },
  { time: '4:05', level: 'info', msg: 'C-Suite Analysis: 8 agents spawned in parallel' },
  { time: '4:00', level: 'success', msg: 'Input Layer: Requirements parsed — 12 features identified' },
]

const levelColor: Record<string, string> = { info: '#63d9ff', success: '#3dffa0', error: '#ff6b35', warn: '#f5c842' }

const statusCircle = (status: StageStatus) => {
  const base = { width: 26, height: 26, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 as const, flexShrink: 0 }
  if (status === 'done') return { ...base, background: '#3dffa0', color: '#04040a' }
  if (status === 'running') return { ...base, background: '#63d9ff', color: '#04040a', boxShadow: '0 0 0 3px rgba(99,217,255,0.25)' }
  if (status === 'failed') return { ...base, background: '#ff6b35', color: '#04040a' }
  return { ...base, background: 'rgba(255,255,255,0.07)', color: 'rgba(232,232,240,0.35)' }
}

const statusIcon = (status: StageStatus, index: number) => {
  if (status === 'done') return '✓'
  if (status === 'running') return '◎'
  if (status === 'failed') return '✕'
  return String(index + 1)
}

export default function PipelinePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [completed, setCompleted] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  // WebSocket placeholder — connects to pipeline event stream
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${window.location.host}/api/v1/pipeline/${id}/ws`

    // Phase 2: uncomment to enable live pipeline events
    // const ws = new WebSocket(url)
    // wsRef.current = ws
    // ws.onmessage = (event) => { /* handle stage updates, log lines */ }
    // ws.onerror = () => { /* retry logic */ }

    // Suppress unused warning for url in Phase 1
    void url

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [id])

  return (
    <div style={{ padding: '36px 40px', maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/projects')}>← Projects</button>
          <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.8px' }}>Building: SaaS Dashboard</h1>
          <span className="tag tag-forge">Pipeline</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span className="tag tag-forge" style={{ animation: 'pulse-f 1.8s ease-in-out infinite' }}>◎ Running — Stage 3 of 6</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--muted)' }}>Elapsed: 4:32</span>
        </div>
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: 18, marginBottom: 18 }}>
        {/* Stage list */}
        <div className="card" style={{ padding: 18 }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 13 }}>PIPELINE STAGES</div>
          {stages.map((s, i) => (
            <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 7px', borderBottom: i < stages.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none', cursor: 'pointer' }}>
              <div style={statusCircle(s.status)}>{statusIcon(s.status, i)}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{s.name}</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: s.status === 'running' ? '#63d9ff' : 'var(--muted)' }}>
                  {s.status === 'done' && 'Completed'}
                  {s.status === 'running' && 'In progress...'}
                  {s.status === 'pending' && 'Waiting'}
                  {s.status === 'failed' && 'Failed'}
                </div>
              </div>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--muted)' }}>{s.duration}</span>
            </div>
          ))}
        </div>

        {/* Active stage detail */}
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>C-Suite Analysis</h2>
            <span className="tag tag-jade">6/8 Complete</span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 14 }}>8 executive agents analyzing in parallel</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {agents.map(a => (
              <div key={a.role} style={{
                background: '#111125', borderRadius: 8, padding: '12px 13px',
                border: a.status === 'done' ? '1px solid rgba(61,255,160,0.2)' : a.status === 'running' ? '1px solid rgba(99,217,255,0.22)' : '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: a.output ? 6 : 0 }}>
                  <span style={{ fontSize: 18 }}>{a.emoji}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, flex: 1 }}>{a.role}</span>
                  {a.status === 'done' && <span style={{ color: '#3dffa0', fontSize: 12 }}>✓</span>}
                  {a.status === 'running' && <span style={{ color: '#63d9ff', fontSize: 10, animation: 'spin 1s linear infinite', display: 'inline-block' }}>◎</span>}
                  {a.status === 'pending' && <span style={{ color: 'var(--muted)', fontSize: 10 }}>○</span>}
                </div>
                {a.output && <p style={{ fontSize: 10, color: 'var(--muted)', lineHeight: 1.4 }}>{a.output}</p>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live event log */}
      <div className="card" style={{ padding: 18, maxHeight: 180, overflow: 'hidden', marginBottom: 18 }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 10 }}>LIVE EVENT LOG</div>
        {logLines.map((l, i) => (
          <div key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, display: 'flex', gap: 8, padding: '2px 0' }}>
            <span style={{ color: 'rgba(232,232,240,0.18)', minWidth: 36 }}>{l.time}</span>
            <span style={{ color: levelColor[l.level], minWidth: 50 }}>{l.level.toUpperCase()}</span>
            <span style={{ color: 'var(--muted)' }}>{l.msg}</span>
          </div>
        ))}
      </div>

      {/* Skip button */}
      <div style={{ textAlign: 'center', marginTop: 18 }}>
        <button className="btn btn-primary" style={{ height: 48, fontSize: 15, padding: '0 32px' }} onClick={() => setCompleted(true)}>Skip to Editor Preview →</button>
        <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--muted)', marginTop: 7 }}>In production this auto-redirects when build completes</p>
      </div>

      {/* Completion overlay */}
      {completed && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ padding: 36, maxWidth: 420, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 14 }}>🎉</div>
            <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Your app is ready!</h2>
            <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18 }}>6 stages completed · 47 files generated · 0 errors</p>
            <button className="btn btn-primary" style={{ height: 48, fontSize: 15, width: '100%', marginBottom: 10 }} onClick={() => navigate('/projects/proj-1/editor')}>Open in Editor →</button>
            <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--muted)' }}>Opening automatically in 3...</p>
          </div>
        </div>
      )}
    </div>
  )
}
