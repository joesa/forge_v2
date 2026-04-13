import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

type FilterTab = 'all' | 'live' | 'building' | 'draft' | 'error'

const tabs: FilterTab[] = ['all', 'live', 'building', 'draft', 'error']

const statusStyles: Record<string, { color: string; bg: string; border: string; label: string }> = {
  live: { color: '#3dffa0', bg: 'rgba(61,255,160,0.1)', border: 'rgba(61,255,160,0.2)', label: '● Live' },
  building: { color: '#63d9ff', bg: 'rgba(99,217,255,0.1)', border: 'rgba(99,217,255,0.2)', label: '◎ Building' },
  draft: { color: 'rgba(232,232,240,0.5)', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)', label: '✦ Draft' },
  error: { color: '#ff6b35', bg: 'rgba(255,107,53,0.1)', border: 'rgba(255,107,53,0.2)', label: '⚠ Error' },
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

export default function ProjectsListPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<FilterTab>('all')
  const [search, setSearch] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Project | null>(null)

  const fetchProjects = useCallback(async () => {
    try {
      const { data } = await apiClient.get<Project[]>('/projects')
      setProjects(data)
    } catch {
      /* auth interceptor handles 401 */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchProjects() }, [fetchProjects])

  const handleDelete = async () => {
    if (!confirmDelete) return
    setDeleting(confirmDelete.id)
    try {
      await apiClient.delete(`/projects/${confirmDelete.id}`)
      setProjects((prev) => prev.filter((p) => p.id !== confirmDelete.id))
    } catch {
      /* swallow — project may already be gone */
    } finally {
      setDeleting(null)
      setConfirmDelete(null)
    }
  }

  const filtered = projects.filter((p) => {
    const status = p.status ?? 'draft'
    if (filter !== 'all' && status !== filter) return false
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div style={{ padding: '34px 32px', maxWidth: 1160 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, color: 'var(--text)', margin: 0 }}>Projects</h1>
          <span className="tag tag-muted">/projects</span>
        </div>
        <div style={{ display: 'flex', gap: 9, alignItems: 'center' }}>
          <input className="input" style={{ width: 200, height: 36, fontSize: 12 }} placeholder="Search projects…" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn btn-primary" onClick={() => navigate('/projects/new')}>+ New Project</button>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 5, marginBottom: 22 }}>
        {tabs.map((t) => (
          <button key={t} className={`btn btn-sm ${filter === t ? 'btn-secondary' : 'btn-ghost'}`} onClick={() => setFilter(t)} style={{ textTransform: 'capitalize' }}>
            {t}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 14, color: 'rgba(232,232,240,0.40)' }}>Loading projects…</div>
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>⬡</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>No projects yet</div>
          <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.40)', marginBottom: 20 }}>Start building your first application</p>
          <div style={{ display: 'flex', gap: 9, justifyContent: 'center' }}>
            <button className="btn btn-primary" onClick={() => navigate('/ideate')}>Start with an idea →</button>
            <button className="btn btn-ghost" onClick={() => navigate('/projects/new')}>Build from prompt →</button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {filtered.map((p) => {
            const status = p.status ?? 'draft'
            const st = statusStyles[status] ?? statusStyles.draft
            return (
              <div key={p.id} className="card" style={{ padding: 0, overflow: 'hidden', position: 'relative' }}>
                <div style={{ height: 90, background: 'linear-gradient(135deg, rgba(99,217,255,0.08), rgba(176,107,255,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 28, opacity: 0.5 }}>⬡</span>
                </div>
                {/* Delete button */}
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmDelete(p) }}
                  title="Delete project"
                  style={{
                    position: 'absolute', top: 8, right: 8,
                    width: 26, height: 26, borderRadius: 6,
                    background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.08)',
                    color: 'rgba(232,232,240,0.45)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 13, lineHeight: 1, transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = '#ff6b35'; e.currentTarget.style.borderColor = 'rgba(255,107,53,0.4)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(232,232,240,0.45)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
                >
                  ×
                </button>
                <div style={{ padding: '14px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", padding: '2px 7px', borderRadius: 4, color: st.color, background: st.bg, border: `1px solid ${st.border}` }}>{st.label}</span>
                    <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace", color: 'rgba(232,232,240,0.42)' }}>{p.framework}</span>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'rgba(232,232,240,0.40)', lineHeight: 1.5, marginBottom: 14 }}>{p.description}</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)' }}>{timeAgo(p.updated_at)}</span>
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/projects/${p.id}/editor`)}>Open Editor →</button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setConfirmDelete(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#0d0d14', border: '1px solid rgba(255,107,53,0.25)',
              borderRadius: 12, padding: '24px 28px', maxWidth: 380, width: '100%',
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>Delete project?</div>
            <p style={{ fontSize: 13, color: 'rgba(232,232,240,0.50)', lineHeight: 1.6, marginBottom: 6 }}>
              This will permanently delete <strong style={{ color: 'var(--text)' }}>{confirmDelete.name}</strong> and all its builds, deployments, and files.
            </p>
            <p style={{ fontSize: 11, color: '#ff6b35', marginBottom: 20 }}>This action cannot be undone.</p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setConfirmDelete(null)}>Cancel</button>
              <button
                className="btn btn-danger btn-sm"
                onClick={handleDelete}
                disabled={deleting !== null}
                style={{ minWidth: 80 }}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
