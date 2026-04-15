import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import apiClient from '@/api/client'

interface PassedIdea {
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
}

const cloudServices = ['Supabase', 'Stripe', 'OpenAI', 'Resend', 'Twilio', 'AWS S3', 'Cloudflare', 'Auth0', 'Pinecone', 'SendGrid']

const frameworkMap: Record<string, string> = {
  'Next.js': 'nextjs',
  'React + Vite': 'vite_react',
  'FastAPI + React': 'fastapi',
  'Express': 'express',
}
const frameworks = Object.keys(frameworkMap)

export default function NewProjectPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const passedIdea = (location.state as { idea?: PassedIdea } | null)?.idea ?? null
  const [path, setPath] = useState<'prompt' | 'ideate' | null>(passedIdea ? 'prompt' : null)
  const [prompt, setPrompt] = useState('')
  const [aiEnhance, setAiEnhance] = useState(true)
  const [selectedServices, setSelectedServices] = useState<Set<string>>(new Set())
  const [selectedFramework, setSelectedFramework] = useState('Next.js')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  // Pre-fill form when navigating from "Build This" on a generated idea
  useEffect(() => {
    if (!passedIdea) return
    const parts = [
      passedIdea.description,
      passedIdea.problem ? `Problem: ${passedIdea.problem}` : '',
      passedIdea.solution ? `Solution: ${passedIdea.solution}` : '',
      passedIdea.market ? `Target Market: ${passedIdea.market}` : '',
      passedIdea.revenue ? `Revenue Model: ${passedIdea.revenue}` : '',
    ].filter(Boolean)
    setPrompt(parts.join('\n\n').slice(0, 2000))
    // Auto-select framework based on idea's recommended stack
    if (passedIdea.stack?.length) {
      const stackStr = passedIdea.stack.join(' ').toLowerCase()
      if (stackStr.includes('next')) setSelectedFramework('Next.js')
      else if (stackStr.includes('vue')) setSelectedFramework('Vue')
      else if (stackStr.includes('svelte')) setSelectedFramework('Svelte')
      else if (stackStr.includes('vite') || stackStr.includes('react')) setSelectedFramework('React + Vite')
    }
  }, [passedIdea])

  const handleStartBuild = async () => {
    if (!prompt.trim()) return
    setSubmitting(true)
    setSubmitError('')
    try {
      const projectName = passedIdea?.title ?? prompt.slice(0, 80)
      const framework = frameworkMap[selectedFramework] ?? 'nextjs'
      const description = prompt

      // Build enriched idea_spec when coming from a generated idea
      const ideaSpec: Record<string, unknown> = {
        name: projectName,
        framework,
        description,
      }
      if (passedIdea) {
        ideaSpec.problem = passedIdea.problem
        ideaSpec.solution = passedIdea.solution
        ideaSpec.market = passedIdea.market
        ideaSpec.revenue = passedIdea.revenue
        ideaSpec.tagline = passedIdea.tagline
        ideaSpec.uniqueness = passedIdea.uniqueness
        ideaSpec.complexity = passedIdea.complexity
        ideaSpec.target_stack = passedIdea.stack
        ideaSpec.source_idea_id = passedIdea.id
      }

      const { data } = await apiClient.post('/projects', {
        name: projectName,
        framework,
        description,
      })
      navigate(`/pipeline/${data.id}`, {
        state: passedIdea ? { ideaSpec: ideaSpec } : undefined,
      })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSubmitError(msg ?? 'Failed to create project')
    } finally {
      setSubmitting(false)
    }
  }

  const toggleService = (s: string) => {
    const next = new Set(selectedServices)
    if (next.has(s)) next.delete(s)
    else next.add(s)
    setSelectedServices(next)
  }

  return (
    <div style={{ padding: '34px 32px', maxWidth: 800 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/projects')}>← Projects</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', margin: 0 }}>New Project</h1>
        <span className="tag tag-muted">/projects/new</span>
      </div>

      {/* Two-path choice */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
        <div
          onClick={() => setPath('prompt')}
          style={{
            textAlign: 'center', padding: 26, borderRadius: 12, cursor: 'pointer', transition: 'all 200ms',
            border: path === 'prompt' ? '2px solid #63d9ff' : '2px solid rgba(255,255,255,0.06)',
            background: path === 'prompt' ? 'rgba(99,217,255,0.08)' : 'rgba(255,255,255,0.03)',
          }}
        >
          <div style={{ fontSize: 28, marginBottom: 9 }}>✍️</div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>I have an idea</div>
        </div>
        <div
          onClick={() => navigate('/ideate')}
          style={{
            textAlign: 'center', padding: 26, borderRadius: 12, cursor: 'pointer', transition: 'all 200ms',
            border: '2px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.03)',
          }}
        >
          <div style={{ fontSize: 28, marginBottom: 9 }}>💡</div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Generate an idea</div>
        </div>
      </div>

      {path === 'prompt' && (
        <div style={{ animation: 'fade-in 280ms ease' }}>
          {/* Prompt textarea */}
          <div style={{ marginBottom: 18 }}>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Describe Your Application</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value.slice(0, 2000))}
              rows={5}
              style={{
                width: '100%', boxSizing: 'border-box', resize: 'none',
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8, padding: '12px 14px', color: 'var(--text)',
                fontFamily: "'Syne', sans-serif", fontSize: 13, outline: 'none',
              }}
              placeholder="Describe the application you want to build…"
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>{prompt.length} / 2000</span>
            </div>
          </div>

          {/* AI Enhancement toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, padding: '11px 14px', marginBottom: 18 }}>
            <div onClick={() => setAiEnhance(!aiEnhance)} style={{ width: 38, height: 20, borderRadius: 10, background: aiEnhance ? '#63d9ff' : 'rgba(255,255,255,0.12)', position: 'relative', cursor: 'pointer', transition: 'background 200ms', flexShrink: 0 }}>
              <div style={{ width: 16, height: 16, borderRadius: '50%', background: '#fff', position: 'absolute', top: 2, left: aiEnhance ? 20 : 2, transition: 'left 200ms' }} />
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>AI Enhancement</div>
              <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.42)' }}>AI will enrich and expand your prompt before building</div>
            </div>
          </div>

          {/* Cloud Services */}
          <div style={{ marginBottom: 18 }}>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 8 }}>Cloud Services</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {cloudServices.map((s) => {
                const sel = selectedServices.has(s)
                return (
                  <button key={s} onClick={() => toggleService(s)} style={{
                    padding: '5px 13px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    border: sel ? '1px solid #63d9ff' : '1px solid rgba(255,255,255,0.08)',
                    color: sel ? '#63d9ff' : 'rgba(232,232,240,0.45)',
                    background: sel ? 'rgba(99,217,255,0.10)' : 'transparent',
                    transition: 'all 200ms',
                  }}>{s}</button>
                )
              })}
            </div>
          </div>

          {/* Framework selector */}
          <div style={{ marginBottom: 26 }}>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 8 }}>Framework</label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {frameworks.map((f) => {
                const sel = selectedFramework === f
                return (
                  <button key={f} onClick={() => setSelectedFramework(f)} style={{
                    padding: '9px 7px', borderRadius: 7, textAlign: 'center', fontSize: 10, fontWeight: 600, cursor: 'pointer',
                    border: sel ? '1px solid #63d9ff' : '1px solid rgba(255,255,255,0.07)',
                    color: sel ? '#63d9ff' : 'rgba(232,232,240,0.45)',
                    background: sel ? 'rgba(99,217,255,0.08)' : 'transparent',
                    transition: 'all 200ms',
                  }}>{f}</button>
                )
              })}
            </div>
          </div>

          {submitError && (
            <div style={{ background: 'var(--ember-dim)', border: '1px solid rgba(255,107,53,0.22)', borderRadius: 8, padding: '10px 14px', marginBottom: 13, fontSize: 12, color: 'var(--ember)' }}>{submitError}</div>
          )}

          <button className="btn btn-primary" style={{ width: '100%', height: 50, fontSize: 14 }} onClick={handleStartBuild} disabled={submitting || !prompt.trim()}>
            {submitting ? 'Creating project…' : 'Start Building →'}
          </button>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textAlign: 'center', color: 'rgba(232,232,240,0.30)', marginTop: 9 }}>
            Estimated build time: 8–15 minutes · Zero broken builds guaranteed
          </div>
        </div>
      )}
    </div>
  )
}
