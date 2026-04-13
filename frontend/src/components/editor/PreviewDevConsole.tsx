import { useState, useEffect, useRef, useCallback } from 'react'
import { useEditorStore } from '@/stores/editorStore'

const MONO = "'JetBrains Mono', monospace"
const MAX_LINES = 200

type Tab = 'console' | 'network' | 'errors'

interface ConsoleEntry {
  id: string
  type: 'log' | 'warn' | 'error'
  message: string
  timestamp: number
}

interface NetworkEntry {
  id: string
  method: string
  url: string
  status: number | null
  duration: number | null
  requestHeaders: Record<string, string> | null
  requestBody: string | null
  responseHeaders: Record<string, string> | null
  responseBody: string | null
  timestamp: number
}

interface ErrorEntry {
  id: string
  message: string
  stack: string | null
  timestamp: number
}

// WS message types from backend
interface WsConsoleMsg {
  type: 'log' | 'warn' | 'error'
  id: string
  message: string
  timestamp: number
}

interface WsNetworkRequestMsg {
  type: 'network_request'
  id: string
  method: string
  url: string
  headers: Record<string, string> | null
  body: string | null
  timestamp: number
}

interface WsNetworkResponseMsg {
  type: 'network_response'
  id: string
  status: number
  duration: number
  headers: Record<string, string> | null
  body: string | null
}

type WsMsg = WsConsoleMsg | WsNetworkRequestMsg | WsNetworkResponseMsg

function getWsBase(): string {
  const api = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (!api) {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}`
  }
  return api.replace(/^http/, 'ws')
}

function statusColor(status: number | null): string {
  if (status === null) return 'rgba(232,232,240,0.42)'
  if (status >= 200 && status < 300) return '#3dffa0'
  if (status >= 300 && status < 400) return '#f5c842'
  return '#ff6b35'
}

interface PreviewDevConsoleProps {
  sandboxId: string | null
}

export default function PreviewDevConsole({ sandboxId }: PreviewDevConsoleProps) {
  const { setDevConsoleErrors, setChatVisible } = useEditorStore()

  const [collapsed, setCollapsed] = useState(true)
  const [tab, setTab] = useState<Tab>('console')
  const [consoleLines, setConsoleLines] = useState<ConsoleEntry[]>([])
  const [networkEntries, setNetworkEntries] = useState<NetworkEntry[]>([])
  const [errors, setErrors] = useState<ErrorEntry[]>([])
  const [expanded, setExpanded] = useState(false)
  const [expandedNetId, setExpandedNetId] = useState<string | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)
  const userScrolledUp = useRef(false)

  // Track error count in editorStore
  useEffect(() => {
    setDevConsoleErrors(errors.length)
  }, [errors.length, setDevConsoleErrors])

  // Auto-scroll unless user scrolled up
  useEffect(() => {
    if (userScrolledUp.current) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [consoleLines, networkEntries, errors, tab])

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20
    userScrolledUp.current = !atBottom
  }, [])

  // WebSocket connection with reconnect backoff
  useEffect(() => {
    if (!sandboxId) return

    let ws: WebSocket | null = null
    let attempt = 0
    let timer: ReturnType<typeof setTimeout> | null = null
    let unmounted = false

    function connect() {
      if (unmounted) return
      const token = localStorage.getItem('access_token')
      const url = `${getWsBase()}/api/v1/sandbox/${sandboxId}/console${token ? `?token=${encodeURIComponent(token)}` : ''}`
      ws = new WebSocket(url)

      ws.onopen = () => { attempt = 0 }

      ws.onmessage = (ev) => {
        let msg: WsMsg
        try { msg = JSON.parse(ev.data as string) as WsMsg } catch { return }

        if (msg.type === 'log' || msg.type === 'warn' || msg.type === 'error') {
          const entry: ConsoleEntry = {
            id: msg.id,
            type: msg.type,
            message: msg.message,
            timestamp: msg.timestamp,
          }
          setConsoleLines((prev) => {
            const next = [...prev, entry]
            return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
          })
          if (msg.type === 'error') {
            setErrors((prev) => [
              ...prev,
              { id: msg.id, message: msg.message, stack: null, timestamp: msg.timestamp },
            ])
          }
        } else if (msg.type === 'network_request') {
          setNetworkEntries((prev) => [
            ...prev,
            {
              id: msg.id,
              method: msg.method,
              url: msg.url,
              status: null,
              duration: null,
              requestHeaders: msg.headers,
              requestBody: msg.body?.slice(0, 1000) ?? null,
              responseHeaders: null,
              responseBody: null,
              timestamp: msg.timestamp,
            },
          ])
        } else if (msg.type === 'network_response') {
          setNetworkEntries((prev) =>
            prev.map((e) =>
              e.id === msg.id
                ? {
                    ...e,
                    status: msg.status,
                    duration: msg.duration,
                    responseHeaders: msg.headers,
                    responseBody: msg.body?.slice(0, 1000) ?? null,
                  }
                : e,
            ),
          )
        }
      }

      ws.onclose = (ev) => {
        if (unmounted) return
        // Don't reconnect if sandbox not found or auth failed
        if (ev.code === 4001 || ev.code === 4003) return
        attempt++
        if (attempt > 8) return // stop after ~4 min of retries
        const delay = Math.min(1000 * 2 ** attempt, 30000)
        timer = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      unmounted = true
      if (timer) clearTimeout(timer)
      if (ws) {
        // Guard: only close if the connection is open or connecting
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close()
        }
      }
    }
  }, [sandboxId])

  // Clear all
  const handleClear = useCallback(() => {
    setConsoleLines([])
    setNetworkEntries([])
    setErrors([])
    setExpandedNetId(null)
  }, [])

  // Send error to AI chat
  const handleSendToAI = useCallback(
    (err: ErrorEntry) => {
      // Append error context to chat (dispatch via custom event for ChatPanel to pick up)
      const detail = `[Console Error] ${err.message}${err.stack ? `\n${err.stack}` : ''}`
      window.dispatchEvent(new CustomEvent('forge:chat-inject', { detail }))
      setChatVisible(true)
    },
    [setChatVisible],
  )

  const headerHeight = 28
  const bodyMaxHeight = expanded ? 320 : 132

  return (
    <div
      style={{
        flexShrink: 0,
        background: 'rgba(4,4,10,0.97)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        maxHeight: collapsed ? headerHeight : headerHeight + bodyMaxHeight,
        overflow: 'hidden',
        transition: 'max-height 150ms ease',
      }}
    >
      {/* Header */}
      <div
        style={{
          height: headerHeight,
          display: 'flex',
          alignItems: 'center',
          padding: '0 8px',
          gap: 2,
          borderBottom: collapsed ? 'none' : '1px solid rgba(255,255,255,0.04)',
        }}
      >
        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed((c) => !c)}
          style={{
            background: 'none',
            border: 'none',
            color: 'rgba(232,232,240,0.42)',
            cursor: 'pointer',
            padding: '0 4px',
            fontFamily: MONO,
            fontSize: 9,
          }}
          title={collapsed ? 'Expand console' : 'Collapse console'}
        >
          {collapsed ? '▶' : '▼'}
        </button>

        {/* Tabs */}
        {(['console', 'network', 'errors'] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); if (collapsed) setCollapsed(false) }}
            style={{
              background: 'none',
              border: 'none',
              fontFamily: MONO,
              fontSize: 9,
              letterSpacing: 1,
              textTransform: 'uppercase',
              color: tab === t ? '#e8e8f0' : 'rgba(232,232,240,0.42)',
              cursor: 'pointer',
              padding: '0 6px',
              position: 'relative',
            }}
          >
            {t === 'errors' && errors.length > 0
              ? <>ERRORS<span style={{ color: '#ff6b35', marginLeft: 3 }}>●{errors.length}</span></>
              : t.toUpperCase()}
          </button>
        ))}

        <div style={{ flex: 1 }} />

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded((e) => !e)}
          style={{
            background: 'none',
            border: 'none',
            color: 'rgba(232,232,240,0.42)',
            cursor: 'pointer',
            padding: '0 4px',
            fontFamily: MONO,
            fontSize: 10,
          }}
          title={expanded ? 'Shrink' : 'Expand'}
        >
          ⊡
        </button>

        {/* Clear */}
        <button
          onClick={handleClear}
          style={{
            background: 'none',
            border: 'none',
            color: 'rgba(232,232,240,0.42)',
            cursor: 'pointer',
            padding: '0 4px',
            fontFamily: MONO,
            fontSize: 10,
          }}
          title="Clear"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      {!collapsed && (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          style={{
            maxHeight: bodyMaxHeight,
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: '4px 8px',
          }}
        >
          {/* CONSOLE tab */}
          {tab === 'console' && (
            consoleLines.length === 0 ? (
              <div style={{ fontFamily: MONO, fontSize: 9, color: 'rgba(232,232,240,0.20)', padding: '8px 0' }}>
                No console output
              </div>
            ) : (
              consoleLines.map((line) => (
                <div
                  key={line.id}
                  style={{
                    fontFamily: MONO,
                    fontSize: 10,
                    lineHeight: '16px',
                    color: line.type === 'error'
                      ? '#ff6b35'
                      : line.type === 'warn'
                        ? '#f5c842'
                        : 'rgba(232,232,240,0.45)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                  }}
                >
                  {line.message}
                </div>
              ))
            )
          )}

          {/* NETWORK tab */}
          {tab === 'network' && (
            networkEntries.length === 0 ? (
              <div style={{ fontFamily: MONO, fontSize: 9, color: 'rgba(232,232,240,0.20)', padding: '8px 0' }}>
                No network activity
              </div>
            ) : (
              networkEntries.map((entry) => (
                <div key={entry.id}>
                  <div
                    onClick={() => setExpandedNetId(expandedNetId === entry.id ? null : entry.id)}
                    style={{
                      fontFamily: MONO,
                      fontSize: 10,
                      lineHeight: '18px',
                      cursor: 'pointer',
                      display: 'flex',
                      gap: 6,
                      alignItems: 'baseline',
                    }}
                  >
                    <span style={{ color: statusColor(entry.status), minWidth: 28 }}>
                      {entry.status ?? '…'}
                    </span>
                    <span style={{ color: 'rgba(232,232,240,0.42)' }}>
                      {entry.method}
                    </span>
                    <span
                      style={{
                        color: 'rgba(232,232,240,0.60)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      {entry.url}
                    </span>
                    {entry.duration !== null && (
                      <span style={{ color: 'rgba(232,232,240,0.30)', flexShrink: 0 }}>
                        {entry.duration}ms
                      </span>
                    )}
                  </div>
                  {expandedNetId === entry.id && (
                    <div
                      style={{
                        fontFamily: MONO,
                        fontSize: 9,
                        color: 'rgba(232,232,240,0.35)',
                        padding: '4px 0 4px 34px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                        borderLeft: '2px solid rgba(255,255,255,0.04)',
                        marginLeft: 4,
                      }}
                    >
                      {entry.requestHeaders && (
                        <div>
                          <span style={{ color: 'rgba(232,232,240,0.50)' }}>Request Headers:</span>
                          {'\n'}{Object.entries(entry.requestHeaders).map(([k, v]) => `${k}: ${v}`).join('\n')}
                        </div>
                      )}
                      {entry.requestBody && (
                        <div style={{ marginTop: 4 }}>
                          <span style={{ color: 'rgba(232,232,240,0.50)' }}>Request Body:</span>
                          {'\n'}{entry.requestBody}
                        </div>
                      )}
                      {entry.responseHeaders && (
                        <div style={{ marginTop: 4 }}>
                          <span style={{ color: 'rgba(232,232,240,0.50)' }}>Response Headers:</span>
                          {'\n'}{Object.entries(entry.responseHeaders).map(([k, v]) => `${k}: ${v}`).join('\n')}
                        </div>
                      )}
                      {entry.responseBody && (
                        <div style={{ marginTop: 4 }}>
                          <span style={{ color: 'rgba(232,232,240,0.50)' }}>Response Body:</span>
                          {'\n'}{entry.responseBody}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )
          )}

          {/* ERRORS tab */}
          {tab === 'errors' && (
            errors.length === 0 ? (
              <div style={{ fontFamily: MONO, fontSize: 9, color: 'rgba(232,232,240,0.20)', padding: '8px 0' }}>
                No errors
              </div>
            ) : (
              errors.map((err) => (
                <div
                  key={err.id}
                  style={{
                    padding: '4px 0',
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                  }}
                >
                  <div style={{ fontFamily: MONO, fontSize: 10, color: '#ff6b35', lineHeight: '16px' }}>
                    {err.message}
                  </div>
                  {err.stack && (
                    <div
                      style={{
                        fontFamily: MONO,
                        fontSize: 9,
                        color: 'rgba(232,232,240,0.30)',
                        whiteSpace: 'pre-wrap',
                        lineHeight: '14px',
                        marginTop: 2,
                      }}
                    >
                      {err.stack}
                    </div>
                  )}
                  <button
                    onClick={() => handleSendToAI(err)}
                    style={{
                      background: 'rgba(176,107,255,0.08)',
                      border: '1px solid rgba(176,107,255,0.18)',
                      color: '#b06bff',
                      borderRadius: 4,
                      padding: '2px 8px',
                      fontFamily: MONO,
                      fontSize: 8,
                      cursor: 'pointer',
                      marginTop: 4,
                    }}
                  >
                    Send to AI ↑
                  </button>
                </div>
              ))
            )
          )}
        </div>
      )}
    </div>
  )
}
