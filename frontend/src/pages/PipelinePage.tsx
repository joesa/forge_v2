import type { ReactNode } from 'react'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import apiClient from '@/api/client'

type StageStatus = 'done' | 'running' | 'pending' | 'failed'

interface Stage { name: string; status: StageStatus; duration: string; detail: Record<string, unknown> }

interface AgentCard {
  emoji: string
  role: string
  agentName: string
  status: StageStatus
  output: string
  detail: Record<string, unknown>
}

const STAGE_NAMES = [
  'Input Layer',
  'C-Suite Analysis',
  'Synthesis',
  'Spec Layer',
  'Bootstrap',
  'Build',
]

const AGENT_ROLES: { emoji: string; role: string; agentName: string }[] = [
  { emoji: '🏗️', role: 'Architect', agentName: 'cto' },
  { emoji: '🎨', role: 'UX Director', agentName: 'cdo' },
  { emoji: '🔒', role: 'Security Lead', agentName: 'cso' },
  { emoji: '⚡', role: 'Performance', agentName: 'cfo' },
  { emoji: '💰', role: 'Business Analyst', agentName: 'ceo' },
  { emoji: '🧪', role: 'QA Engineer', agentName: 'cco' },
  { emoji: '📊', role: 'Data Architect', agentName: 'cpo' },
  { emoji: '🚀', role: 'DevOps Lead', agentName: 'cmo' },
]

interface LogLine { time: string; level: string; msg: string }

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

function elapsed(startMs: number): string {
  const s = Math.floor((Date.now() - startMs) / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export default function PipelinePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [projectName, setProjectName] = useState('')
  const [, setPipelineId] = useState<string | null>(null)
  const [stages, setStages] = useState<Stage[]>(
    STAGE_NAMES.map(n => ({ name: n, status: 'pending', duration: '—', detail: {} }))
  )
  const [agents, setAgents] = useState<AgentCard[]>(
    AGENT_ROLES.map(a => ({ ...a, status: 'pending', output: '', detail: {} }))
  )
  const [logs, setLogs] = useState<LogLine[]>([])
  const [elapsedStr, setElapsedStr] = useState('0:00')
  const [completed, setCompleted] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState<AgentCard | null>(null)
  const [selectedStage, setSelectedStage] = useState<Stage | null>(null)

  const startRef = useRef(Date.now())
  const timerRef = useRef<ReturnType<typeof setInterval>>(undefined)
  const wsRef = useRef<WebSocket | null>(null)

  // Add a log line
  const addLog = useCallback((level: string, msg: string) => {
    const now = elapsed(startRef.current)
    setLogs(prev => [{ time: now, level, msg }, ...prev].slice(0, 50))
  }, [])

  // Handle a WebSocket message
  const handleWsMessage = useCallback((data: Record<string, unknown>) => {
    const type = data.type as string | undefined

    if (type === 'stage_update') {
      const idx = (data.stage as number) - 1
      const status = data.status as StageStatus
      const detail = (data.detail as Record<string, unknown>) ?? undefined
      setStages(prev => {
        const next: Stage[] = prev.map((s, i) => {
          if (i === idx) return { ...s, status, duration: status === 'done' ? elapsed(startRef.current) : s.duration, ...(detail ? { detail } : {}) }
          if (i === idx + 1 && status === 'done' && prev[i].status === 'pending') return { ...s, status: 'running' }
          return s
        })
        if (next.every(s => s.status === 'done')) setCompleted(true)
        return next
      })
      addLog(status === 'failed' ? 'error' : 'info', `${STAGE_NAMES[idx]}: ${data.message ?? status}`)
    }

    if (type === 'agent_update') {
      const agent = data.agent as string
      const status = data.status as StageStatus
      const output = (data.output as string) ?? ''
      const detail = (data.detail as Record<string, unknown>) ?? {}
      setAgents(prev => prev.map(a => (a.agentName === agent) ? { ...a, status, output, detail } : a))
      const matched = AGENT_ROLES.find(r => r.agentName === agent)
      addLog(status === 'done' ? 'success' : 'info', `${matched?.role ?? agent}: ${output || status}`)
    }

    if (type === 'log') {
      addLog((data.level as string) ?? 'info', (data.message as string) ?? '')
    }

    if (type === 'pipeline_complete') {
      const finalStatus = data.status as string
      setStages(prev => prev.map(s => s.status === 'running' ? { ...s, status: finalStatus === 'completed' ? 'done' : 'failed' } : s))
      if (finalStatus === 'completed') setCompleted(true)
    }
  }, [addLog])

  // 1. Fetch project → 2. Start pipeline → 3. Connect WebSocket
  useEffect(() => {
    if (!id) return
    let cancelled = false

    const boot = async () => {
      try {
        // Fetch project details
        const { data: proj } = await apiClient.get(`/projects/${id}`)
        if (cancelled) return
        setProjectName(proj.name)

        // Start the pipeline
        const { data: pipe } = await apiClient.post('/pipeline/run', {
          project_id: id,
          idea_spec: {
            description: proj.description ?? '',
            framework: proj.framework ?? '',
            name: proj.name ?? '',
          },
        })
        if (cancelled) return
        setPipelineId(pipe.pipeline_id)
        addLog('success', `Pipeline started — ${pipe.pipeline_id.slice(0, 8)}`)

        // Mark stage 1 as running
        setStages(prev => prev.map((s, i) => i === 0 ? { ...s, status: 'running' } : s))

        // Connect WebSocket for live events
        const token = localStorage.getItem('access_token')
        if (token) {
          const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
          const host = import.meta.env.VITE_API_BASE_URL
            ? new URL(import.meta.env.VITE_API_BASE_URL as string).host
            : window.location.host
          const wsUrl = `${protocol}://${host}/api/v1/pipeline/${pipe.pipeline_id}/stream`
          const ws = new WebSocket(wsUrl)
          wsRef.current = ws

          ws.onopen = () => {
            ws.send(token) // first message = JWT
          }

          ws.onmessage = (event) => {
            try {
              const msg = JSON.parse(event.data as string) as Record<string, unknown>
              handleWsMessage(msg)
            } catch { /* ignore non-JSON */ }
          }

          ws.onerror = () => addLog('warn', 'WebSocket error — retrying...')
          ws.onclose = () => addLog('info', 'Pipeline stream closed')
        }
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        addLog('error', msg ?? 'Failed to start pipeline')
      }
    }

    boot()

    // Elapsed timer
    startRef.current = Date.now()
    timerRef.current = setInterval(() => setElapsedStr(elapsed(startRef.current)), 1000)

    return () => {
      cancelled = true
      if (timerRef.current) clearInterval(timerRef.current)
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    }
  }, [id, addLog, handleWsMessage])

  // Derive progress
  const doneCount = stages.filter(s => s.status === 'done').length
  const currentStage = stages.findIndex(s => s.status === 'running') + 1
  const agentsDone = agents.filter(a => a.status === 'done').length
  const allDone = doneCount === stages.length
  const overallStatus = (completed || allDone) ? 'completed' : stages.some(s => s.status === 'failed') ? 'failed' : 'running'

  const renderDetailValue = (value: unknown): ReactNode => {
    if (value === null || value === undefined || value === '') return <span style={{ color: 'var(--muted)' }}>—</span>
    if (typeof value === 'string') return <span style={{ whiteSpace: 'pre-wrap' }}>{value}</span>
    if (typeof value === 'number' || typeof value === 'boolean') return <span>{String(value)}</span>
    if (Array.isArray(value)) {
      if (value.length === 0) return <span style={{ color: 'var(--muted)' }}>—</span>
      return (
        <ul style={{ margin: 0, paddingLeft: 16 }}>
          {value.map((item, i) => (
            <li key={i} style={{ marginBottom: 3 }}>
              {typeof item === 'object' && item !== null
                ? Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                    <span key={k}><strong style={{ color: 'rgba(232,232,240,0.55)' }}>{k}:</strong> {String(v)}  </span>
                  ))
                : String(item)}
            </li>
          ))}
        </ul>
      )
    }
    if (typeof value === 'object') {
      const entries = Object.entries(value as Record<string, unknown>).filter(([, v]) => v !== '' && v !== null)
      if (entries.length === 0) return <span style={{ color: 'var(--muted)' }}>—</span>
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {entries.map(([k, v]) => (
            <div key={k}>
              <strong style={{ color: 'rgba(232,232,240,0.55)' }}>{k.replace(/_/g, ' ')}:</strong>{' '}
              {typeof v === 'string' ? v : JSON.stringify(v)}
            </div>
          ))}
        </div>
      )
    }
    return <span>{JSON.stringify(value)}</span>
  }

  return (
    <div style={{ padding: '36px 40px', maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate('/projects')}>← Projects</button>
          <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.8px' }}>
            Building: {projectName || '...'}
          </h1>
          <span className="tag tag-forge">Pipeline</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span className="tag tag-forge" style={overallStatus === 'running' ? { animation: 'pulse-f 1.8s ease-in-out infinite' } : undefined}>
            {overallStatus === 'completed' ? '✓ Complete' : overallStatus === 'failed' ? '✕ Failed' : `◎ Running — Stage ${currentStage || 1} of ${stages.length}`}
          </span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'var(--muted)' }}>Elapsed: {elapsedStr}</span>
        </div>
      </div>

      {/* 2-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '350px 1fr', gap: 18, marginBottom: 18 }}>
        {/* Stage list */}
        <div className="card" style={{ padding: 18 }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 13 }}>PIPELINE STAGES</div>
          {stages.map((s, i) => (
            <div key={s.name}
              onClick={() => s.status === 'done' ? setSelectedStage(s) : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '10px 7px',
                borderBottom: i < stages.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                cursor: s.status === 'done' ? 'pointer' : 'default',
                borderRadius: 6,
                transition: 'background 150ms',
              }}
              onMouseEnter={e => { if (s.status === 'done') (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.03)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
            >
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
              {s.status === 'done' && <span style={{ color: 'var(--muted)', fontSize: 12, marginLeft: 2 }}>›</span>}
            </div>
          ))}
        </div>

        {/* Active stage detail — C-Suite cards */}
        <div className="card" style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>C-Suite Analysis</h2>
            <span className="tag tag-jade">{agentsDone}/{agents.length} Complete</span>
          </div>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 14 }}>{agents.length} executive agents analyzing in parallel</p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {agents.map(a => (
              <div key={a.role} onClick={() => a.status === 'done' ? setSelectedAgent(a) : undefined} style={{
                background: '#111125', borderRadius: 8, padding: '12px 13px',
                border: a.status === 'done' ? '1px solid rgba(61,255,160,0.2)' : a.status === 'running' ? '1px solid rgba(99,217,255,0.22)' : '1px solid rgba(255,255,255,0.06)',
                cursor: a.status === 'done' ? 'pointer' : 'default',
                transition: 'border-color 200ms, transform 120ms',
              }}
              onMouseEnter={e => { if (a.status === 'done') (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(61,255,160,0.45)' }}
              onMouseLeave={e => { if (a.status === 'done') (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(61,255,160,0.2)' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: a.output ? 6 : 0 }}>
                  <span style={{ fontSize: 18 }}>{a.emoji}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, flex: 1 }}>{a.role}</span>
                  {a.status === 'done' && <span style={{ color: '#3dffa0', fontSize: 12 }}>✓</span>}
                  {a.status === 'running' && <span style={{ color: '#63d9ff', fontSize: 10, animation: 'spin 1s linear infinite', display: 'inline-block' }}>◎</span>}
                  {a.status === 'pending' && <span style={{ color: 'var(--muted)', fontSize: 10 }}>○</span>}
                </div>
                {a.output && <p style={{ fontSize: 10, color: 'var(--muted)', lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{a.output}</p>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live event log */}
      <div className="card" style={{ padding: 18, maxHeight: 180, overflow: 'hidden', marginBottom: 18 }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 10 }}>LIVE EVENT LOG</div>
        {logs.length === 0 && (
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--muted)', padding: '4px 0' }}>Waiting for pipeline events...</div>
        )}
        {logs.map((l, i) => (
          <div key={i} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, display: 'flex', gap: 8, padding: '2px 0' }}>
            <span style={{ color: 'rgba(232,232,240,0.18)', minWidth: 36 }}>{l.time}</span>
            <span style={{ color: levelColor[l.level] ?? '#63d9ff', minWidth: 50 }}>{l.level.toUpperCase()}</span>
            <span style={{ color: 'var(--muted)' }}>{l.msg}</span>
          </div>
        ))}
      </div>

      {/* Token usage bar */}
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--muted)', marginBottom: 8 }}>
        TOKEN USAGE
        <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginTop: 4, maxWidth: 120 }}>
          <div style={{ height: '100%', background: '#63d9ff', borderRadius: 2, width: `${Math.min(100, doneCount / stages.length * 100)}%`, transition: 'width 400ms' }} />
        </div>
      </div>

      {/* Skip button */}
      <div style={{ textAlign: 'center', marginTop: 18 }}>
        <button className="btn btn-primary" style={{ height: 48, fontSize: 15, padding: '0 32px' }} onClick={() => navigate(`/projects/${id}/editor`)}>
          {completed ? 'Open in Editor →' : 'Skip to Editor Preview →'}
        </button>
        <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--muted)', marginTop: 7 }}>
          {completed ? 'Your app is ready!' : 'In production this auto-redirects when build completes'}
        </p>
      </div>

      {/* Agent detail modal */}
      {selectedAgent && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', zIndex: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setSelectedAgent(null)}>
          <div className="card" style={{ padding: 28, maxWidth: 600, width: '90%', maxHeight: '80vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <span style={{ fontSize: 28 }}>{selectedAgent.emoji}</span>
              <div style={{ flex: 1 }}>
                <h2 style={{ fontSize: 18, fontWeight: 700 }}>{selectedAgent.role}</h2>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#3dffa0', textTransform: 'uppercase' }}>Analysis Complete</span>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelectedAgent(null)} style={{ fontSize: 16, padding: '4px 8px' }}>✕</button>
            </div>
            {selectedAgent.output && (
              <div style={{ background: 'rgba(99,217,255,0.06)', borderRadius: 8, padding: '10px 14px', marginBottom: 14, border: '1px solid rgba(99,217,255,0.12)' }}>
                <p style={{ fontSize: 12, color: '#63d9ff', lineHeight: 1.6, margin: 0 }}>{selectedAgent.output}</p>
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(selectedAgent.detail).length > 0 ? (
                Object.entries(selectedAgent.detail).map(([key, value]) => (
                  <div key={key} style={{ background: '#0a0a1a', borderRadius: 8, padding: '12px 14px', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 700, letterSpacing: 0.5, color: 'rgba(232,232,240,0.40)', textTransform: 'uppercase', marginBottom: 6 }}>
                      {key.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.7 }}>
                      {renderDetailValue(value)}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ background: '#0a0a1a', borderRadius: 8, padding: 16, border: '1px solid rgba(255,255,255,0.06)' }}>
                  <p style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>No detailed output available for this agent.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Stage detail modal */}
      {selectedStage && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(6px)', zIndex: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setSelectedStage(null)}>
          <div className="card" style={{ padding: 28, maxWidth: 640, width: '90%', maxHeight: '80vh', overflow: 'auto' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={statusCircle(selectedStage.status)}>{statusIcon(selectedStage.status, stages.indexOf(selectedStage))}</div>
              <div style={{ flex: 1 }}>
                <h2 style={{ fontSize: 18, fontWeight: 700 }}>{selectedStage.name}</h2>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: selectedStage.status === 'done' ? '#3dffa0' : '#63d9ff', textTransform: 'uppercase' }}>
                  {selectedStage.status === 'done' ? `Completed in ${selectedStage.duration}` : selectedStage.status}
                </span>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelectedStage(null)} style={{ fontSize: 16, padding: '4px 8px' }}>✕</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(selectedStage.detail).length > 0 ? (
                Object.entries(selectedStage.detail).map(([key, value]) => (
                  <div key={key} style={{ background: '#0a0a1a', borderRadius: 8, padding: '12px 14px', border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 700, letterSpacing: 0.5, color: 'rgba(232,232,240,0.40)', textTransform: 'uppercase', marginBottom: 6 }}>
                      {key.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.7 }}>
                      {renderDetailValue(value)}
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ background: '#0a0a1a', borderRadius: 8, padding: 16, border: '1px solid rgba(255,255,255,0.06)' }}>
                  <p style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>No detailed output available yet for this stage.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Completion overlay */}
      {completed && !selectedStage && !selectedAgent && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ padding: 36, maxWidth: 420, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 14 }}>🎉</div>
            <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Your app is ready!</h2>
            <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18 }}>{doneCount} stages completed · {stages.filter(s => s.status === 'failed').length} errors</p>
            <button className="btn btn-primary" style={{ height: 48, fontSize: 15, width: '100%', marginBottom: 10 }} onClick={() => navigate(`/projects/${id}/editor`)}>Open in Editor →</button>
          </div>
        </div>
      )}
    </div>
  )
}
