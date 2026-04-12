import { useState, useRef, useEffect, useCallback } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import apiClient from '@/api/client'

const MONO = "'JetBrains Mono', monospace"

interface PreviewToolbarProps {
  sandboxId: string | null
  previewUrl: string | null
  onRefresh: () => void
  iframeRef: React.RefObject<HTMLIFrameElement | null>
}

export default function PreviewToolbar({
  sandboxId,
  previewUrl,
  onRefresh,
  iframeRef,
}: PreviewToolbarProps) {
  const {
    previewRoute,
    previewDevice,
    annotationMode,
    devConsoleErrors,
    setPreviewRoute,
    setPreviewDevice,
    toggleAnnotationMode,
  } = useEditorStore()

  const [sharePopover, setSharePopover] = useState(false)
  const [shareUrl, setShareUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const shareRef = useRef<HTMLDivElement>(null)
  const dismissTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // History stubs (iframe navigation tracking is limited cross-origin)
  const [canGoBack] = useState(false)
  const [canGoForward] = useState(false)

  // Close share popover on outside click
  useEffect(() => {
    if (!sharePopover) return
    function handleClick(e: MouseEvent) {
      if (shareRef.current && !shareRef.current.contains(e.target as Node)) {
        setSharePopover(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [sharePopover])

  // Auto-dismiss share popover after 5s
  useEffect(() => {
    if (!sharePopover) return
    dismissTimerRef.current = setTimeout(() => setSharePopover(false), 5000)
    return () => {
      if (dismissTimerRef.current !== null) clearTimeout(dismissTimerRef.current)
    }
  }, [sharePopover])

  const handleBack = useCallback(() => {
    try { iframeRef.current?.contentWindow?.history.back() } catch { /* cross-origin */ }
  }, [iframeRef])

  const handleForward = useCallback(() => {
    try { iframeRef.current?.contentWindow?.history.forward() } catch { /* cross-origin */ }
  }, [iframeRef])

  const handleScreenshot = useCallback(async () => {
    if (!sandboxId) return
    try {
      const { data } = await apiClient.post<{ url: string }>(
        `/sandbox/${sandboxId}/preview/screenshot`,
        { route: previewRoute },
      )
      const link = document.createElement('a')
      link.href = data.url
      link.download = `preview-${Date.now()}.webp`
      link.click()
    } catch {
      // Screenshot may fail if sandbox is not running
    }
  }, [sandboxId, previewRoute])

  const handleShare = useCallback(async () => {
    if (!sandboxId) return
    try {
      const { data } = await apiClient.post<{ share_url: string }>(
        `/sandbox/${sandboxId}/preview/share`,
        { expires_hours: 24 },
      )
      setShareUrl(data.share_url)
      setSharePopover(true)
      await navigator.clipboard.writeText(data.share_url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Share may fail
    }
  }, [sandboxId])

  const btnBase: React.CSSProperties = {
    background: 'none',
    border: 'none',
    color: 'rgba(232,232,240,0.50)',
    cursor: 'pointer',
    padding: '0 6px',
    fontSize: 14,
    lineHeight: '38px',
    flexShrink: 0,
  }

  const btnActive: React.CSSProperties = {
    ...btnBase,
    color: '#63d9ff',
  }

  const btnEmber: React.CSSProperties = {
    ...btnBase,
    color: '#ff6b35',
  }

  return (
    <div
      style={{
        height: 38,
        flexShrink: 0,
        background: 'rgba(4,4,10,0.95)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 8px',
        gap: 2,
      }}
    >
      {/* Navigation */}
      <button
        style={{ ...btnBase, opacity: canGoBack ? 1 : 0.3 }}
        onClick={handleBack}
        title="Back"
      >
        ←
      </button>
      <button
        style={{ ...btnBase, opacity: canGoForward ? 1 : 0.3 }}
        onClick={handleForward}
        title="Forward"
      >
        →
      </button>

      {/* URL bar */}
      <input
        value={previewRoute}
        onChange={(e) => setPreviewRoute(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onRefresh()
        }}
        style={{
          flex: 1,
          height: 24,
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 4,
          color: '#e8e8f0',
          fontFamily: MONO,
          fontSize: 9,
          padding: '0 8px',
          outline: 'none',
          minWidth: 0,
        }}
        placeholder={previewUrl ?? '/'}
      />

      {/* Device toggles */}
      <button
        style={previewDevice === 'mobile' ? btnActive : btnBase}
        onClick={() => setPreviewDevice('mobile')}
        title="Mobile (375px)"
      >
        📱
      </button>
      <button
        style={previewDevice === 'desktop' ? btnActive : btnBase}
        onClick={() => setPreviewDevice('desktop')}
        title="Desktop"
      >
        💻
      </button>

      {/* Separator */}
      <div style={{ width: 1, height: 18, background: 'rgba(255,255,255,0.08)', margin: '0 4px', flexShrink: 0 }} />

      {/* Refresh */}
      <button style={btnBase} onClick={onRefresh} title="Refresh">
        ↺
      </button>

      {/* Screenshot */}
      <button style={btnBase} onClick={() => void handleScreenshot()} title="Screenshot (WebP)">
        📷
      </button>

      {/* Annotate */}
      <button
        style={annotationMode ? btnEmber : btnBase}
        onClick={toggleAnnotationMode}
        title="Annotate"
      >
        ✏️
      </button>

      {/* Share */}
      <div ref={shareRef} style={{ position: 'relative', flexShrink: 0 }}>
        <button style={btnBase} onClick={() => void handleShare()} title="Share">
          🔗
        </button>
        {sharePopover && (
          <div
            style={{
              position: 'absolute',
              top: 36,
              right: 0,
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              padding: '10px 12px',
              zIndex: 50,
              minWidth: 220,
              whiteSpace: 'nowrap',
            }}
          >
            <div style={{ fontFamily: MONO, fontSize: 9, color: 'rgba(232,232,240,0.5)', marginBottom: 4 }}>
              Share URL
            </div>
            <div style={{ fontFamily: MONO, fontSize: 10, color: '#e8e8f0', wordBreak: 'break-all', whiteSpace: 'normal' }}>
              {shareUrl}
            </div>
            {copied && (
              <div style={{ color: '#3dffa0', fontSize: 10, fontFamily: MONO, marginTop: 4 }}>
                Copied!
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error badge */}
      {devConsoleErrors > 0 && (
        <div
          style={{
            fontFamily: MONO,
            fontSize: 9,
            color: '#ff6b35',
            background: 'rgba(255,107,53,0.10)',
            border: '1px solid rgba(255,107,53,0.18)',
            borderRadius: 4,
            padding: '2px 7px',
            letterSpacing: 0.5,
            marginLeft: 4,
            flexShrink: 0,
            cursor: 'pointer',
          }}
          title="Console errors"
        >
          ● {devConsoleErrors}
        </div>
      )}
    </div>
  )
}
