import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import apiClient from '@/api/client'

interface Project {
  id: string
  name: string
  description: string | null
  status: string | null
  framework: string | null
  created_at: string | null
  updated_at: string | null
}

const statusStyles: Record<string, { color: string; bg: string; border: string; label: string }> = {
  live: { color: '#3dffa0', bg: 'rgba(61,255,160,0.1)', border: 'rgba(61,255,160,0.2)', label: '● Live' },
  building: { color: '#63d9ff', bg: 'rgba(99,217,255,0.1)', border: 'rgba(99,217,255,0.2)', label: '◎ Building' },
  draft: { color: 'rgba(232,232,240,0.5)', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', label: '✦ Draft' },
  error: { color: '#ff6b35', bg: 'rgba(255,107,53,0.1)', border: 'rgba(255,107,53,0.2)', label: '⚠ Error' },
  archived: { color: 'rgba(232,232,240,0.35)', bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.06)', label: '◆ Archived' },
}

const frameworkLabels: Record<string, string> = {
  nextjs: 'Next.js',
  vite_react: 'Vite + React',
  fastapi: 'FastAPI',
  django: 'Django',
  express: 'Express',
}

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`
  const days = Math.floor(hrs / 24)
  return `${days} day${days > 1 ? 's' : ''} ago`
}

export default function ProjectDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchProject = useCallback(async () => {
    if (!id) return
    try {
      const { data } = await apiClient.get<Project>(`/projects/${id}`)
      setProject(data)
    } catch {
      setError('Project not found')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchProject() }, [fetchProject])

  if (loading) {
    return (
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 14, color: 'rgba(232,232,240,0.40)' }}>Loading project…</div>
        </div>
      </div>
    )
  }

  if (error || !project) {
    return (
      <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>⬡</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>{error ?? 'Project not found'}</div>
          <button className="btn btn-ghost" onClick={() => navigate('/projects')}>← Back to Projects</button>
        </div>
      </div>
    )
  }

  const status = project.status ?? 'draft'
  const st = statusStyles[status] ?? statusStyles.draft
  const fw = project.framework ? (frameworkLabels[project.framework] ?? project.framework) : null

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 22 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => navigate('/projects')}>← Projects</button>
        <h1 style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)', margin: 0 }}>Project Overview</h1>
        <span className="tag tag-muted">/projects/{id}</span>
      </div>

      {/* Project header card */}
      <div className="card" style={{ marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: st.color, background: st.bg, border: `1px solid ${st.border}` }}>{st.label}</span>
              {fw && <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.42)' }}>{fw}</span>}
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', margin: '0 0 6px' }}>{project.name}</h2>
            {project.description && (
              <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.45)', lineHeight: 1.6, margin: 0 }}>{project.description}</p>
            )}
            {project.updated_at && (
              <p style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)', marginTop: 10 }}>Updated {timeAgo(project.updated_at)}</p>
            )}
          </div>
          <button className="btn btn-primary" onClick={() => navigate(`/projects/${id}/editor`)}>Open Editor →</button>
        </div>
      </div>

      {/* Quick links */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { icon: '⚡', label: 'Editor', path: `/projects/${id}/editor` },
          { icon: '🔨', label: 'Builds', path: `/projects/${id}/builds` },
          { icon: '▲', label: 'Deployments', path: `/projects/${id}/deployments` },
          { icon: '⚙️', label: 'Settings', path: `/projects/${id}/settings` },
        ].map((item) => (
          <div key={item.label} className="card" style={{ textAlign: 'center', cursor: 'pointer', padding: 22 }} onClick={() => navigate(item.path)}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>{item.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{item.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
