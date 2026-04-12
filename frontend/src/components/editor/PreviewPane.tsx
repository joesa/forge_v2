import { useRef, useEffect } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { usePreview } from '@/hooks/usePreview'
import PreviewToolbar from './PreviewToolbar'

const MONO = "'JetBrains Mono', monospace"
const PREVIEW_DOMAIN = '.preview.forge.dev'

export default function PreviewPane() {
  const { sandboxId, previewDevice, previewRoute, selectedSnapshot } = useEditorStore()
  const { previewUrl, loading, healthy, error, snapshotImageUrl, refresh } =
    usePreview(sandboxId)

  const iframeRef = useRef<HTMLIFrameElement | null>(null)

  // Set auth cookie for *.preview.forge.dev before iframe loads
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      document.cookie = `forge_access_token=${token}; domain=${PREVIEW_DOMAIN}; path=/; SameSite=None; Secure`
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
        width: 310,
        flexShrink: 0,
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
        onRefresh={refresh}
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
      </div>

      {/* DevConsole placeholder */}
      <div
        style={{
          height: 0,
          flexShrink: 0,
          borderTop: '1px solid rgba(255,255,255,0.06)',
        }}
      />

      {/* SnapshotTimeline placeholder — 38px */}
      <div
        style={{
          height: 38,
          flexShrink: 0,
          background: 'rgba(4,4,10,0.95)',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 10px',
        }}
      >
        <span
          style={{
            fontFamily: MONO,
            fontSize: 9,
            color: 'rgba(232,232,240,0.20)',
            letterSpacing: 1,
            textTransform: 'uppercase',
          }}
        >
          Snapshots
        </span>
      </div>
    </div>
  )
}
