import { useRef, useEffect } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { usePreview } from '@/hooks/usePreview'
import PreviewToolbar from './PreviewToolbar'
import AnnotationLayer from './AnnotationLayer'
import SnapshotTimeline from './SnapshotTimeline'
import PreviewDevConsole from './PreviewDevConsole'

const MONO = "'JetBrains Mono', monospace"

export default function PreviewPane() {
  const { sandboxId, previewDevice, previewRoute, selectedSnapshot, previewExpanded } = useEditorStore()
  const syncLive = useEditorStore((s) => s.syncSteps.live)
  const chatStreaming = useEditorStore((s) => s.chatStreaming)
  const { previewUrl, loading, healthy, booting, error, snapshotImageUrl, refresh } =
    usePreview(sandboxId)

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const lastReloadRef = useRef(0)
  const wasStreamingRef = useRef(false)
  const wasBootingRef = useRef(false)

  /** Force-reload the preview iframe (handles cross-origin) */
  const reloadIframe = () => {
    const now = Date.now()
    // Debounce: at most one reload per 2 seconds
    if (now - lastReloadRef.current < 2000) return
    lastReloadRef.current = now
    const iframe = iframeRef.current
    if (!iframe) return
    try {
      iframe.contentWindow?.location.reload()
    } catch {
      // Cross-origin — reassign src to force reload
      if (iframe.src) {
        const src = iframe.src
        iframe.src = 'about:blank'
        setTimeout(() => { iframe.src = src }, 50)
      }
    }
  }

  // Auto-reload iframe when sandbox transitions from booting → healthy
  useEffect(() => {
    if (booting) {
      wasBootingRef.current = true
      return
    }
    if (wasBootingRef.current && healthy) {
      wasBootingRef.current = false
      // Small delay to let the dev server fully initialize
      const timer = setTimeout(() => reloadIframe(), 500)
      return () => clearTimeout(timer)
    }
  }, [booting, healthy])

  // Reload iframe when a chat edit sync reaches "live" status
  useEffect(() => {
    if (syncLive !== 'done') return
    reloadIframe()
  }, [syncLive])

  // Reload iframe when chat streaming ends (edits were applied)
  useEffect(() => {
    if (chatStreaming) {
      wasStreamingRef.current = true
      return
    }
    // Streaming just stopped
    if (wasStreamingRef.current) {
      wasStreamingRef.current = false
      // Delay to let sandbox agent write file + Vite recompile
      const timer = setTimeout(() => reloadIframe(), 1500)
      return () => clearTimeout(timer)
    }
  }, [chatStreaming])

  // Set auth cookie scoped to the preview URL domain
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token || !previewUrl) return
    try {
      const host = new URL(previewUrl).hostname
      // Use parent domain (e.g. .code.run or .preview.forge.dev)
      const parts = host.split('.')
      const cookieDomain = parts.length > 2 ? `.${parts.slice(-2).join('.')}` : host
      document.cookie = `forge_access_token=${token}; domain=${cookieDomain}; path=/; SameSite=None; Secure`
    } catch {
      // Fallback: set cookie without domain restriction
      document.cookie = `forge_access_token=${token}; path=/; SameSite=None; Secure`
    }
  }, [previewUrl])

  const iframeSrc = previewUrl
    ? previewRoute === '/'
      ? previewUrl
      : `${previewUrl}${previewRoute}`
    : undefined

  return (
    <div
      style={{
        width: previewExpanded ? undefined : 310,
        flex: previewExpanded ? 1 : undefined,
        minWidth: previewExpanded ? 0 : undefined,
        flexShrink: previewExpanded ? undefined : 0,
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid rgba(255,255,255,0.06)',
        background: '#04040a',
      }}
    >
      {/* Toolbar — 38px */}
      <PreviewToolbar
        sandboxId={sandboxId}
        previewUrl={previewUrl}
        onRefresh={() => { refresh(); reloadIframe(); }}
        iframeRef={iframeRef}
      />

      {/* Preview body — flex:1 */}
      <div
        style={{
          flex: 1,
          overflow: 'hidden',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'stretch',
          background: '#080812',
          position: 'relative',
        }}
      >
        {selectedSnapshot && snapshotImageUrl ? (
          // Snapshot image view
          <img
            src={snapshotImageUrl}
            alt="Snapshot preview"
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
            }}
          />
        ) : loading ? (
          // Loading state
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              color: 'rgba(232,232,240,0.42)',
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: 1,
            }}
          >
            Loading preview…
          </div>
        ) : booting ? (
          // Sandbox is booting — show progress instead of 503 iframe
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              gap: 12,
              padding: 20,
            }}
          >
            <div style={{
              width: 24,
              height: 24,
              border: '2px solid rgba(99,217,255,0.2)',
              borderTopColor: '#63d9ff',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
            <div style={{ color: 'rgba(232,232,240,0.55)', fontFamily: MONO, fontSize: 10, textAlign: 'center' }}>
              Sandbox starting…
            </div>
            <div style={{ color: 'rgba(232,232,240,0.25)', fontFamily: MONO, fontSize: 9, textAlign: 'center' }}>
              Installing dependencies &amp; starting dev server
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
          </div>
        ) : error ? (
          // Error state
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              gap: 8,
              padding: 20,
            }}
          >
            <div style={{ color: '#ff6b35', fontFamily: MONO, fontSize: 10 }}>
              {error}
            </div>
            <button
              onClick={refresh}
              style={{
                background: 'rgba(99,217,255,0.10)',
                border: '1px solid rgba(99,217,255,0.22)',
                color: '#63d9ff',
                borderRadius: 6,
                padding: '4px 12px',
                fontFamily: MONO,
                fontSize: 9,
                cursor: 'pointer',
              }}
            >
              Retry
            </button>
          </div>
        ) : iframeSrc ? (
          // Live preview iframe
          <iframe
            ref={iframeRef}
            src={iframeSrc}
            title="Preview"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
            style={{
              width: previewDevice === 'mobile' ? 375 : '100%',
              maxWidth: '100%',
              height: '100%',
              border: 'none',
              background: '#fff',
            }}
          />
        ) : (
          // No preview available
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              color: 'rgba(232,232,240,0.20)',
              fontFamily: MONO,
              fontSize: 10,
              letterSpacing: 1,
              textTransform: 'uppercase',
            }}
          >
            No preview
          </div>
        )}

        {/* Health indicator */}
        {!loading && previewUrl && (
          <div
            style={{
              position: 'absolute',
              top: 6,
              right: 6,
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: healthy ? '#3dffa0' : 'rgba(232,232,240,0.20)',
            }}
            title={healthy ? 'Sandbox healthy' : 'Sandbox unreachable'}
          />
        )}

        {/* Annotation overlay */}
        <AnnotationLayer sandboxId={sandboxId} iframeRef={iframeRef} />
      </div>

      {/* Dev Console */}
      <PreviewDevConsole sandboxId={sandboxId} />

      {/* Snapshot Timeline — 38px */}
      <SnapshotTimeline />
    </div>
  )
}
