import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

interface Idea {
  title: string
  tagline: string
  uniqueness: number
  complexity: number
  problem: string
  solution: string
  market: string
  revenue: string
  stack: string[]
}

const mockIdeas: Idea[] = [
  { title: 'DevFlow', tagline: 'GitHub-native project management for small teams', uniqueness: 8.2, complexity: 6, problem: 'Small dev teams juggle multiple tools for project tracking, losing context between code and tasks.', solution: 'A GitHub-integrated project board with AI-powered sprint planning and automatic issue linking.', market: '$4.2B', revenue: '$120k ARR Y1', stack: ['Next.js', 'Supabase', 'GitHub API', 'OpenAI'] },
  { title: 'PriceRadar', tagline: 'AI-powered competitive pricing intelligence', uniqueness: 7.5, complexity: 7, problem: 'E-commerce brands manually track competitor prices across dozens of sites.', solution: 'Automated price monitoring with AI recommendations for optimal pricing strategies.', market: '$2.8B', revenue: '$85k ARR Y1', stack: ['React', 'Python', 'Puppeteer', 'GPT-4'] },
  { title: 'MeetSync', tagline: 'Async meeting summaries that actually work', uniqueness: 6.8, complexity: 5, problem: 'Remote teams waste hours in meetings that could be emails.', solution: 'AI meeting recorder that creates structured summaries, action items, and follow-ups.', market: '$6.1B', revenue: '$200k ARR Y1', stack: ['Next.js', 'Whisper', 'Claude', 'Stripe'] },
  { title: 'StackBuddy', tagline: 'AI code review for junior developers', uniqueness: 7.1, complexity: 8, problem: 'Junior devs wait hours for code reviews, slowing their learning cycle.', solution: 'Instant AI code reviews with explanations, best practices, and mentor-style feedback.', market: '$1.9B', revenue: '$60k ARR Y1', stack: ['VS Code Extension', 'Claude', 'TypeScript'] },
  { title: 'FormForge', tagline: 'AI-generated forms from natural language', uniqueness: 8.8, complexity: 4, problem: 'Building forms is tedious. Most form builders require manual field-by-field setup.', solution: 'Describe your form in plain English, get a production-ready form with validation and submission logic.', market: '$3.5B', revenue: '$95k ARR Y1', stack: ['React', 'Zod', 'Supabase', 'OpenAI'] },
]

export default function IdeaDetailPage() {
  const navigate = useNavigate()
  const [saved, setSaved] = useState<Set<number>>(new Set())

  const toggleSave = (i: number) => setSaved(s => { const n = new Set(s); n.has(i) ? n.delete(i) : n.add(i); return n })

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
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>5 AI-generated ideas · Private for 7 days · Based on your answers</p>
        </div>
        <button className="btn btn-ghost btn-sm">↻ Regenerate All</button>
      </div>

      {/* Top 3 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
        {mockIdeas.slice(0, 3).map((idea, i) => (
          <IdeaCard key={i} idea={idea} index={i} saved={saved.has(i)} onSave={() => toggleSave(i)} onBuild={() => navigate('/projects/new')} />
        ))}
      </div>

      {/* Bottom 2 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
        {mockIdeas.slice(3).map((idea, i) => (
          <IdeaCard key={i + 3} idea={idea} index={i + 3} saved={saved.has(i + 3)} onSave={() => toggleSave(i + 3)} onBuild={() => navigate('/projects/new')} />
        ))}
      </div>

      {/* Footer */}
      <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.20)', textAlign: 'center', marginTop: 22 }}>Ideas private for 7 days · Similar ideas may surface to other users after expiry</p>
    </div>
  )
}

function IdeaCard({ idea, index, saved, onSave, onBuild }: { idea: Idea; index: number; saved: boolean; onSave: () => void; onBuild: () => void }) {
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
        <button className="btn btn-ghost btn-sm" onClick={onSave} style={{ color: saved ? '#3dffa0' : undefined }}>{saved ? '💾 Saved' : '💾 Save'}</button>
        <button className="btn btn-ghost btn-sm">↻</button>
        <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={onBuild}>🚀 Build This</button>
      </div>
    </div>
  )
}
