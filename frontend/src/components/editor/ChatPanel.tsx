import { useState, useRef, useEffect, useCallback } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { getValidToken } from '@/api/token'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '') + '/api/v1'

export default function ChatPanel() {
  const projectId = useEditorStore((s) => s.projectId)
  const activeFile = useEditorStore((s) => s.activeFile)
  const fileContents = useEditorStore((s) => s.fileContents)
  const messages = useEditorStore((s) => s.chatMessages)
  const streaming = useEditorStore((s) => s.chatStreaming)
  const addChatMessage = useEditorStore((s) => s.addChatMessage)
  const updateLastAssistantMessage = useEditorStore((s) => s.updateLastAssistantMessage)
  const setChatStreaming = useEditorStore((s) => s.setChatStreaming)
  const setFileContent = useEditorStore((s) => s.setFileContent)
  const openFile = useEditorStore((s) => s.openFile)

  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || streaming || !projectId) return

    setInput('')
    const userMsg = { id: crypto.randomUUID(), role: 'user' as const, content: text }
    addChatMessage(userMsg)

    const assistantMsg = { id: crypto.randomUUID(), role: 'assistant' as const, content: '', pending: true }
    addChatMessage(assistantMsg)
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
      const allMessages = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }))

      const resp = await fetch(`${API_BASE}/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
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

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6)
          try {
            const event = JSON.parse(jsonStr) as { type: string; content?: string }
            if (event.type === 'text' && event.content) {
              accumulated += event.content
              updateLastAssistantMessage(accumulated)
            } else if (event.type === 'error' && event.content) {
              accumulated += `\n\n${event.content}`
              updateLastAssistantMessage(accumulated)
            }
          } catch {
            // skip malformed events
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        updateLastAssistantMessage('Connection error. Please try again.')
      }
    } finally {
      setChatStreaming(false)
      abortRef.current = null
    }
  }, [input, streaming, projectId, messages, activeFile, fileContents, addChatMessage, updateLastAssistantMessage, setChatStreaming])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage()
    }
  }

  const applyEdit = (path: string, content: string) => {
    openFile(path, content)
    setFileContent(path, content)
  }

  const parseForgeEdits = (text: string): { path: string; content: string; description: string }[] => {
    const edits: { path: string; content: string; description: string }[] = []
    const regex = /```forge-edit\s*\n([\s\S]*?)```/g
    let match
    while ((match = regex.exec(text)) !== null) {
      try {
        const parsed = JSON.parse(match[1]) as { path: string; content: string; description: string }
        if (parsed.path && parsed.content) {
          edits.push(parsed)
        }
      } catch {
        // skip malformed edit blocks
      }
    }
    return edits
  }

  const renderMessage = (msg: typeof messages[0]) => {
    const isUser = msg.role === 'user'

    if (isUser) {
      return (
        <div key={msg.id}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, fontWeight: 700, letterSpacing: 0.5, color: 'rgba(232,232,240,0.35)', marginBottom: 3 }}>YOU</div>
          <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, padding: '9px 11px', fontSize: 11, lineHeight: 1.6, color: 'rgba(232,232,240,0.65)' }}>
            {msg.content}
          </div>
        </div>
      )
    }

    const edits = parseForgeEdits(msg.content)
    // Strip forge-edit blocks for display
    const displayContent = msg.content.replace(/```forge-edit\s*\n[\s\S]*?```/g, '').trim()

    return (
      <div key={msg.id}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, fontWeight: 700, letterSpacing: 0.5, color: '#63d9ff', marginBottom: 3 }}>FORGE AI</div>
        <div style={{ background: 'rgba(99,217,255,0.08)', border: '1px solid rgba(99,217,255,0.14)', borderRadius: 8, padding: '9px 11px', fontSize: 11, lineHeight: 1.6 }}>
          {displayContent && <div style={{ whiteSpace: 'pre-wrap', marginBottom: edits.length ? 8 : 0 }}>{displayContent}</div>}
          {msg.pending && !msg.content && (
            <span style={{ color: 'rgba(232,232,240,0.35)' }}>Thinking...</span>
          )}
          {edits.map((edit, i) => (
            <div key={i} style={{ background: '#04040a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 7, overflow: 'hidden', marginTop: 6 }}>
              <div style={{ padding: '6px 10px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#63d9ff' }}>{edit.path}</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  <button className="btn btn-ghost" style={{ height: 22, padding: '0 6px', fontSize: 9 }} onClick={() => { void navigator.clipboard.writeText(edit.content) }}>Copy</button>
                  <button className="btn btn-primary" style={{ height: 22, padding: '0 6px', fontSize: 9 }} onClick={() => applyEdit(edit.path, edit.content)}>Apply</button>
                </div>
              </div>
              <div style={{ padding: '6px 10px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.45)', maxHeight: 120, overflow: 'auto' }}>
                {edit.description}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div style={{ borderLeft: '1px solid rgba(255,255,255,0.06)', background: '#080812', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Chat header */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
        <div style={{ width: 26, height: 26, borderRadius: '50%', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>⚡</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 700 }}>Forge AI</div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: streaming ? '#f5c842' : '#3dffa0' }}>
            {streaming ? '● streaming...' : '● active · claude-sonnet-4'}
          </div>
        </div>
        <span style={{ fontSize: 12, color: 'rgba(232,232,240,0.30)', cursor: 'pointer' }}>⚙</span>
      </div>

      {/* Chat messages */}
      <div ref={scrollRef} style={{ flex: 1, padding: 12, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 9 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 16px' }}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>⚡</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>Forge AI</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', lineHeight: 1.6 }}>
              Ask me to modify code, add features, fix bugs, or explain how something works.
            </div>
          </div>
        )}
        {messages.map(renderMessage)}
      </div>

      {/* Chat input */}
      <div style={{ padding: '9px 10px', borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
          {['/build', '/deploy', '/test', '/lint'].map((cmd) => (
            <span
              key={cmd}
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, padding: '2px 6px', background: 'rgba(99,217,255,0.08)', color: '#63d9ff', border: '1px solid rgba(99,217,255,0.18)', borderRadius: 3, cursor: 'pointer' }}
              onClick={() => setInput(cmd + ' ')}
            >{cmd}</span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 5 }}>
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, resize: 'none', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 5, padding: '6px 9px', color: 'var(--text)', outline: 'none', opacity: streaming ? 0.5 : 1 }}
            placeholder="Ask Forge AI..."
          />
          <button
            onClick={() => void sendMessage()}
            disabled={streaming || !input.trim()}
            style={{ width: 28, height: 28, background: streaming || !input.trim() ? 'rgba(99,217,255,0.3)' : '#63d9ff', border: 'none', borderRadius: 5, color: '#04040a', fontSize: 13, fontWeight: 700, cursor: streaming ? 'not-allowed' : 'pointer', flexShrink: 0, alignSelf: 'flex-end' }}
          >→</button>
        </div>
      </div>
    </div>
  )
}
