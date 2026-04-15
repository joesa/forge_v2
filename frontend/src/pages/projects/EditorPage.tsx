import { useState, useCallback, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useEditorStore } from '@/stores/editorStore'
import { useEditor } from '@/hooks/useEditor'
import apiClient from '@/api/client'
import ForgeMonacoEditor, { langFromPath } from '@/components/editor/MonacoEditor'
import FileTree from '@/components/editor/FileTree'
import EditorTabs from '@/components/editor/EditorTabs'
import PreviewPane from '@/components/editor/PreviewPane'
import ChatPanel from '@/components/editor/ChatPanel'

const activityIcons = ['📁', '🔍', '⚡', '🔀', '🐛', '🧪']

export default function EditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const projectId = id ?? ''
  const { saveNow, handleContentChange, handleFileOpen } = useEditor(projectId)
  const {
    activeFile,
    fileContents,
    previewVisible,
    previewExpanded,
    chatVisible,
    devConsoleErrors,
    togglePreview,
    togglePreviewExpanded,
    setChatVisible,
  } = useEditorStore()
  const [activeActivity, setActiveActivity] = useState(0)
  const [projectName, setProjectName] = useState('')

  useEffect(() => {
    if (!projectId) return
    apiClient.get<{ name: string }>(`/projects/${projectId}`).then(({ data }) => {
      setProjectName(data.name)
    }).catch(() => { /* ignore */ })
  }, [projectId])

  const currentContent = activeFile ? (fileContents[activeFile] ?? '') : ''
  const currentLang = activeFile ? langFromPath(activeFile) : 'typescript'
  const breadcrumb = activeFile ? activeFile.split('/') : []

  const handleEditorChange = useCallback(
    (value: string) => {
      if (activeFile) handleContentChange(activeFile, value)
    },
    [activeFile, handleContentChange],
  )

  const handleSave = useCallback(() => {
    void saveNow()
  }, [saveNow])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#04040a' }}>
      {/* Top bar */}
      <div style={{ height: 46, background: '#080812', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0, zIndex: 50, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 11 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 22, height: 22, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 16, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
          <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px' }} />
          <span style={{ fontSize: 12, color: 'rgba(232,232,240,0.55)', cursor: 'pointer' }} onClick={() => navigate(`/projects/${id}`)}>{projectName || 'Loading…'} ▼</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.30)', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: 10 }}>○ main</span>
          <button className="btn btn-ghost btn-sm" style={{ height: 24, fontSize: 10, padding: '0 8px', color: '#63d9ff' }} onClick={() => navigate(`/pipeline/${id}`)}>◎ Pipeline</button>
          <button className="btn btn-ghost btn-sm" style={{ height: 24, fontSize: 10, padding: '0 8px' }} onClick={() => navigate(`/projects/${id}`)}>← Project</button>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--ember)' }}>● {devConsoleErrors} error{devConsoleErrors !== 1 ? 's' : ''}</span>
          <button className="btn btn-ghost btn-sm" style={{ height: 28, fontSize: 11 }} onClick={togglePreview}>
            {previewVisible ? '⊟' : '⊞'} Preview
          </button>
          {previewVisible && (
            <button className="btn btn-ghost btn-sm" style={{ height: 28, fontSize: 11 }} onClick={togglePreviewExpanded}>
              {previewExpanded ? '⊟' : '⊞'} {previewExpanded ? 'Collapse' : 'Expand'}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" style={{ height: 28, fontSize: 11 }} onClick={() => setChatVisible(!chatVisible)}>
            {chatVisible ? '⊟' : '⊞'} Chat
          </button>
          <button className="btn btn-primary btn-sm" style={{ height: 28, fontSize: 11 }}>▲ Deploy</button>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: 'var(--void)' }}>JS</div>
        </div>
      </div>

      {/* Body */}
      {previewExpanded ? (
        /* Expanded preview: simple flex layout — preview fills space, optional chat */
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
            <PreviewPane />
          </div>
          {chatVisible && <ChatPanel />}
        </div>
      ) : (
        /* Normal editor layout: 5-column grid */
        <div style={{ flex: 1, display: 'grid', gridTemplateColumns: `46px 210px 1fr ${previewVisible ? '310px' : ''} ${chatVisible ? '295px' : ''}`.trim(), overflow: 'hidden', minHeight: 0 }}>
          {/* Activity bar — 46px */}
          <div style={{ background: 'rgba(4,4,10,0.90)', borderRight: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '10px 0', gap: 5 }}>
            {activityIcons.map((icon, i) => (
              <div
                key={i}
                onClick={() => setActiveActivity(i)}
                style={{
                  width: 34, height: 34, borderRadius: activeActivity === i ? '0 6px 6px 0' : 6,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, cursor: 'pointer',
                  color: activeActivity === i ? '#63d9ff' : 'rgba(232,232,240,0.40)',
                  background: activeActivity === i ? 'rgba(99,217,255,0.08)' : 'transparent',
                  borderLeft: activeActivity === i ? '2px solid #63d9ff' : '2px solid transparent',
                  marginLeft: activeActivity === i ? -1 : 0,
                }}
              >{icon}</div>
            ))}
            <div style={{ flex: 1 }} />
            <div style={{ width: 34, height: 34, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, cursor: 'pointer', color: 'rgba(232,232,240,0.40)' }} onClick={() => navigate(`/projects/${id}/settings`)}>⚙️</div>
          </div>

          {/* File tree */}
          <FileTree onFileOpen={handleFileOpen} />

          {/* Main editor area */}
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Tab bar */}
            <EditorTabs />

            {/* Breadcrumb */}
            <div style={{ padding: '5px 14px', background: 'rgba(255,255,255,0.015)', borderBottom: '1px solid rgba(255,255,255,0.06)', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.30)' }}>
              {breadcrumb.map((seg, i) => (
                <span key={i}>
                  {i > 0 && ' › '}
                  <span style={i === breadcrumb.length - 1 ? { color: '#63d9ff' } : undefined}>{seg}</span>
                </span>
              ))}
              {breadcrumb.length === 0 && <span>No file open</span>}
            </div>

            {/* Monaco */}
            <div style={{ flex: 1, overflow: 'hidden' }}>
              {activeFile ? (
                <ForgeMonacoEditor
                  value={currentContent}
                  language={currentLang}
                  onChange={handleEditorChange}
                  onSave={handleSave}
                />
              ) : (
                <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#04040a' }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: 'rgba(232,232,240,0.20)' }}>Open a file to start editing</span>
                </div>
              )}
            </div>
          </div>

          {/* Preview pane (conditional) */}
          {previewVisible && <PreviewPane />}

          {/* Chat panel */}
          {chatVisible && <ChatPanel />}
        </div>
      )}

      {/* Status bar */}
      <div style={{ height: 22, background: '#63d9ff', flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 16, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#04040a', fontWeight: 700 }}>
        <span>⚡ Forge</span>
        <span>TypeScript</span>
        <span>Ln 24, Col 8</span>
        <span>No errors</span>
        <div style={{ flex: 1 }} />
        <span>Sandbox: ● Running</span>
        <span>main</span>
      </div>
    </div>
  )
}
