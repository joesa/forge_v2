import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark-dimmed.css'
import './chat-markdown.css'
import { useEditorStore, type ChatMessage } from '@/stores/editorStore'
import { getValidToken } from '@/api/token'
import apiClient from '@/api/client'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1'

// ── Types ────────────────────────────────────────────────────────

interface ForgeEdit {
  path: string
  content: string
  description: string
}

// ── Parsing helpers ──────────────────────────────────────────────

function parseCompleteEdits(text: string): ForgeEdit[] {
  const edits: ForgeEdit[] = []
  const re = /```forge-edit\s*\n([\s\S]*?)```/g
  let match
  while ((match = re.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1]) as ForgeEdit
      if (parsed.path && parsed.content) edits.push(parsed)
    } catch { /* skip malformed */ }
  }
  return edits
}

function getStreamingEditPath(text: string): string | null {
  const idx = text.lastIndexOf('```forge-edit')
  if (idx === -1) return null
  const rest = text.slice(idx + 13)
  if (rest.includes('```')) return null
  const m = rest.match(/"path"\s*:\s*"([^"]+)"/)
  return m?.[1] ?? null
}

function getStreamingPartialContent(text: string): string | null {
  const idx = text.lastIndexOf('```forge-edit')
  if (idx === -1) return null
  const rest = text.slice(idx + 13)
  if (rest.includes('```')) return null
  const ci = rest.indexOf('"content": "')
  if (ci === -1) return null
  let raw = rest.slice(ci + 12)
  if (raw.endsWith('\\')) raw = raw.slice(0, -1)
  return raw
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\')
}

function stripForgeEdits(text: string): string {
  let cleaned = text.replace(/```forge-edit\s*\n[\s\S]*?```/g, '')
  const idx = cleaned.lastIndexOf('```forge-edit')
  if (idx !== -1 && !cleaned.slice(idx + 13).includes('```')) {
    cleaned = cleaned.slice(0, idx)
  }
  return cleaned.trim()
}

// ── Sub-components ───────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: 4, padding: '4px 0' }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#63d9ff',
            animation: `chatPulse 1.4s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  )
}

function FileCard({ edit, onClick }: { edit: ForgeEdit; onClick: () => void }) {
  return (
    <div style={{
      background: 'rgba(99,217,255,0.04)', border: '1px solid rgba(99,217,255,0.15)',
      borderRadius: 8, overflow: 'hidden', marginTop: 8,
    }}>
      <div
        style={{
          padding: '8px 12px', display: 'flex', alignItems: 'center',
          gap: 8, cursor: 'pointer', borderBottom: '1px solid rgba(99,217,255,0.08)',
        }}
        onClick={onClick}
      >
        <span style={{ fontSize: 14 }}>📄</span>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
          color: '#63d9ff', flex: 1,
        }}>{edit.path}</span>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
          color: '#3dffa0', background: 'rgba(61,255,160,0.08)',
          padding: '2px 8px', borderRadius: 10, fontWeight: 600,
        }}>✓ Applied</span>
      </div>
      <div style={{
        padding: '6px 12px', fontSize: 11, color: 'rgba(232,232,240,0.5)',
        lineHeight: 1.5,
      }}>{edit.description}</div>
    </div>
  )
}

function StreamingFileCard({ path }: { path: string }) {
  return (
    <div style={{
      background: 'rgba(245,200,66,0.04)', border: '1px solid rgba(245,200,66,0.15)',
      borderRadius: 8, padding: '8px 12px', marginTop: 8,
      display: 'flex', alignItems: 'center', gap: 8,
    }}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%', background: '#f5c842',
        animation: 'chatPulse 1s ease-in-out infinite',
      }} />
      <span style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
        color: '#f5c842',
      }}>Writing {path}...</span>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────

export default function ChatPanel() {
  const projectId = useEditorStore((s) => s.projectId)
  const activeFile = useEditorStore((s) => s.activeFile)
  const fileContents = useEditorStore((s) => s.fileContents)
  const messages = useEditorStore((s) => s.chatMessages)
  const streaming = useEditorStore((s) => s.chatStreaming)
  const addChatMessage = useEditorStore((s) => s.addChatMessage)
  const updateLastAssistantMessage = useEditorStore((s) => s.updateLastAssistantMessage)
  const setChatStreaming = useEditorStore((s) => s.setChatStreaming)
  const openFile = useEditorStore((s) => s.openFile)
  const setFileContent = useEditorStore((s) => s.setFileContent)
  const markSaved = useEditorStore((s) => s.markSaved)
  const setSyncStep = useEditorStore((s) => s.setSyncStep)
  const setSyncFile = useEditorStore((s) => s.setSyncFile)
  const resetSyncSteps = useEditorStore((s) => s.resetSyncSteps)

  const [input, setInput] = useState('')
  const [streamingPath, setStreamingPath] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const appliedCountRef = useRef(0)
  const lastLiveUpdateRef = useRef(0)

  // Auto-scroll to bottom
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
    }
  }, [messages, streamingPath])

  const saveAndSync = useCallback(async (path: string, content: string) => {
    if (!projectId) return
    setSyncStep('saving', 'done')
    setSyncStep('syncing', 'active')
    setSyncFile(path)
    // Mark as modified so auto-save acts as fallback if this call fails
    setFileContent(path, content)
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const { data } = await apiClient.put<{ synced: boolean; sync_method: string | null }>(
          `/projects/${projectId}/files/content`, { path, content }
        )
        markSaved(path)
        if (!data.synced) {
          console.warn(`[ForgeAI] File saved but sandbox sync missed for ${path} — will retry`)
          if (attempt < 2) {
            await new Promise((r) => setTimeout(r, 1000))
            continue
          }
        }
        setSyncStep('syncing', 'done')
        setSyncStep('applied', 'done')
        setTimeout(() => setSyncStep('live', 'done'), 400)
        return
      } catch {
        if (attempt < 2) await new Promise((r) => setTimeout(r, 500 * (attempt + 1)))
      }
    }
    setSyncStep('syncing', 'error')
    console.warn(`[ForgeAI] Failed to sync ${path} to sandbox after 3 attempts`)
  }, [projectId, setFileContent, markSaved, setSyncStep, setSyncFile])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setChatStreaming(false)
    setStreamingPath(null)
  }, [setChatStreaming])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || streaming || !projectId) return

    setInput('')
    appliedCountRef.current = 0
    setStreamingPath(null)
    resetSyncSteps()

    const userMsg = { id: crypto.randomUUID(), role: 'user' as const, content: text }
    addChatMessage(userMsg)
    addChatMessage({ id: crypto.randomUUID(), role: 'assistant' as const, content: '', pending: true })
    setChatStreaming(true)

    const token = await getValidToken()
    if (!token) {
      updateLastAssistantMessage('Session expired. Please log in again.')
      setChatStreaming(false)
      return
    }

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const allMessages = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }))

      const resp = await fetch(`${API_BASE}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          project_id: projectId,
          messages: allMessages,
          active_file: activeFile,
          active_file_content: activeFile ? (fileContents[activeFile] ?? null) : null,
        }),
        signal: ctrl.signal,
      })

      if (!resp.ok) {
        updateLastAssistantMessage('Sorry, something went wrong. Please try again.')
        setChatStreaming(false)
        return
      }

      const reader = resp.body?.getReader()
      if (!reader) {
        updateLastAssistantMessage('No response received.')
        setChatStreaming(false)
        return
      }

      const decoder = new TextDecoder()
      let accumulated = ''
      let buffer = ''
      let prevStreamingPath: string | null = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6)) as { type: string; content?: string }
            if (event.type === 'text' && event.content) {
              accumulated += event.content
              updateLastAssistantMessage(accumulated)

              // Apply newly completed forge-edit blocks
              const edits = parseCompleteEdits(accumulated)
              while (appliedCountRef.current < edits.length) {
                const edit = edits[appliedCountRef.current]
                setSyncStep('parsing', 'done')
                setSyncStep('saving', 'active')
                setSyncFile(edit.path)
                openFile(edit.path, edit.content)
                void saveAndSync(edit.path, edit.content)
                appliedCountRef.current++
                setStreamingPath(null)
              }

              // Detect in-progress forge-edit block
              const currentPath = getStreamingEditPath(accumulated)
              if (currentPath && !prevStreamingPath) {
                resetSyncSteps()
                setSyncStep('parsing', 'active')
                setSyncFile(currentPath)
              }
              prevStreamingPath = currentPath
              setStreamingPath(currentPath)

              // Live-update editor with partial content (throttled)
              if (currentPath) {
                const now = Date.now()
                if (now - lastLiveUpdateRef.current > 80) {
                  lastLiveUpdateRef.current = now
                  const partial = getStreamingPartialContent(accumulated)
                  if (partial) openFile(currentPath, partial)
                }
              }
            } else if (event.type === 'error' && event.content) {
              accumulated += `\n\n⚠️ ${event.content}`
              updateLastAssistantMessage(accumulated)
            }
          } catch { /* skip malformed */ }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        updateLastAssistantMessage('Connection error. Please try again.')
      }
    } finally {
      setChatStreaming(false)
      setStreamingPath(null)
      abortRef.current = null
      // Clear sync dots after a short delay so user sees final state
      setTimeout(() => resetSyncSteps(), 3000)
    }
  }, [input, streaming, projectId, messages, activeFile, fileContents, addChatMessage, updateLastAssistantMessage, setChatStreaming, openFile, saveAndSync, setSyncStep, setSyncFile, resetSyncSteps])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage()
    }
  }

  const renderMessage = (msg: ChatMessage, idx: number) => {
    const isUser = msg.role === 'user'
    const isCurrentStreaming = streaming && msg.role === 'assistant' && idx === messages.length - 1

    if (isUser) {
      return (
        <div key={msg.id} style={{ marginBottom: 16 }}>
          <div style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 600,
            letterSpacing: 0.5, color: 'rgba(232,232,240,0.3)', marginBottom: 4,
          }}>YOU</div>
          <div style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 10, padding: '10px 14px', fontSize: 13, lineHeight: 1.6,
            color: 'rgba(232,232,240,0.75)',
          }}>{msg.content}</div>
        </div>
      )
    }

    const edits = parseCompleteEdits(msg.content)
    const displayText = stripForgeEdits(msg.content)

    return (
      <div key={msg.id} style={{ marginBottom: 16 }}>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 600,
          letterSpacing: 0.5, color: 'rgba(99,217,255,0.5)', marginBottom: 4,
        }}>FORGE AI</div>
        <div style={{ fontSize: 13, lineHeight: 1.7, color: 'rgba(232,232,240,0.8)' }}>
          {displayText ? (
            <div className="forge-md">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {displayText}
              </ReactMarkdown>
              {isCurrentStreaming && !streamingPath && (
                <span className="forge-cursor" />
              )}
            </div>
          ) : msg.pending && !msg.content ? (
            <TypingIndicator />
          ) : null}
          {edits.map((edit, i) => (
            <FileCard
              key={`${edit.path}-${i}`}
              edit={edit}
              onClick={() => openFile(edit.path, edit.content)}
            />
          ))}
          {isCurrentStreaming && streamingPath && (
            <StreamingFileCard path={streamingPath} />
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{
      borderLeft: '1px solid rgba(255,255,255,0.06)', background: '#080812',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
        }}>⚡</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700 }}>Forge AI</div>
          <div style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
            color: streaming ? '#f5c842' : '#3dffa0',
          }}>
            {streaming ? '● streaming...' : '● online'}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{
        flex: 1, padding: '16px 14px', overflowY: 'auto',
      }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 16px' }}>
            <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.8 }}>⚡</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text)', marginBottom: 6 }}>Forge AI</div>
            <div style={{
              fontSize: 12, color: 'rgba(232,232,240,0.4)', lineHeight: 1.7,
              maxWidth: 220, margin: '0 auto',
            }}>
              Ask me to modify code, add features, fix bugs, or explain how things work.
            </div>
          </div>
        )}
        {messages.map((msg, i) => renderMessage(msg, i))}
      </div>

      {/* Input */}
      <div style={{
        padding: '10px 12px', borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0,
      }}>
        {!streaming && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
            {['/build', '/deploy', '/test', '/lint'].map((cmd) => (
              <span
                key={cmd}
                style={{
                  fontFamily: "'JetBrains Mono', monospace", fontSize: 9,
                  padding: '2px 8px', background: 'rgba(99,217,255,0.06)',
                  color: 'rgba(99,217,255,0.7)', border: '1px solid rgba(99,217,255,0.12)',
                  borderRadius: 4, cursor: 'pointer',
                }}
                onClick={() => setInput(cmd + ' ')}
              >{cmd}</span>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end' }}>
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            style={{
              flex: 1, fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
              resize: 'none', background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
              padding: '8px 12px', color: 'var(--text)', outline: 'none',
              opacity: streaming ? 0.4 : 1, lineHeight: 1.5,
            }}
            placeholder="Ask Forge AI..."
          />
          {streaming ? (
            <button
              onClick={stopStreaming}
              style={{
                width: 32, height: 32, background: 'rgba(255,80,80,0.15)',
                border: '1px solid rgba(255,80,80,0.3)', borderRadius: 8,
                color: '#ff5050', fontSize: 12, cursor: 'pointer', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
              title="Stop"
            >■</button>
          ) : (
            <button
              onClick={() => void sendMessage()}
              disabled={!input.trim()}
              style={{
                width: 32, height: 32,
                background: input.trim() ? 'linear-gradient(135deg, #63d9ff, #b06bff)' : 'rgba(255,255,255,0.06)',
                border: 'none', borderRadius: 8,
                color: input.trim() ? '#04040a' : 'rgba(232,232,240,0.3)',
                fontSize: 15, fontWeight: 700,
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >↑</button>
          )}
        </div>
      </div>
    </div>
  )
}
