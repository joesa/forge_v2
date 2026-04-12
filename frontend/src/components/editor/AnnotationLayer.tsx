import { useState, useEffect, useCallback, useRef } from 'react'
import { useEditorStore, type Annotation } from '@/stores/editorStore'
import apiClient from '@/api/client'

const MONO = "'JetBrains Mono', monospace"
const PREVIEW_ORIGIN_SUFFIX = '.preview.forge.dev'

/**
 * PostMessage injection script for the preview iframe.
 * elementFromPoint → buildSelectorPath (max 4 levels deep)
 * → reply {type:'selector_result', selector, route}
 */
const SELECTOR_SCRIPT = `
(function() {
  window.addEventListener('message', function(e) {
    if (!e.data || e.data.type !== 'get_selector') return;
    var x = e.data.x, y = e.data.y;
    var el = document.elementFromPoint(x, y);
    if (!el) { e.source.postMessage({type:'selector_result', selector:'body', route:location.pathname}, '*'); return; }
    var parts = [];
    var cur = el;
    for (var i = 0; i < 4 && cur && cur !== document.body && cur !== document.documentElement; i++) {
      var tag = cur.tagName.toLowerCase();
      if (cur.id) { parts.unshift(tag + '#' + cur.id); break; }
      var cls = Array.from(cur.classList).slice(0,2).join('.');
      parts.unshift(cls ? tag + '.' + cls : tag);
      cur = cur.parentElement;
    }
    e.source.postMessage({type:'selector_result', selector: parts.join(' > ') || 'body', route:location.pathname}, '*');
  });
})();
`

interface AnnotationLayerProps {
  sandboxId: string | null
  iframeRef: React.RefObject<HTMLIFrameElement | null>
}

interface PendingAnnotation {
  x_pct: number
  y_pct: number
  screenX: number
  screenY: number
  selector: string | null
  route: string
}

interface SelectorResult {
  type: 'selector_result'
  selector: string
  route: string
}

export default function AnnotationLayer({ sandboxId, iframeRef }: AnnotationLayerProps) {
  const {
    annotationMode,
    annotations,
    previewRoute,
    setAnnotations,
  } = useEditorStore()

  const [pending, setPending] = useState<PendingAnnotation | null>(null)
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)
  const [popoverId, setPopoverId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  const layerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Inject selector script into iframe on load
  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    function injectScript() {
      try {
        const doc = iframe?.contentDocument
        if (doc) {
          const script = doc.createElement('script')
          script.textContent = SELECTOR_SCRIPT
          doc.body.appendChild(script)
        }
      } catch {
        // Cross-origin — script injection not possible; fallback to 'body' selector
      }
    }

    iframe.addEventListener('load', injectScript)
    return () => { iframe.removeEventListener('load', injectScript) }
  }, [iframeRef])

  // Listen for selector_result postMessage — ONLY accept from preview.forge.dev
  useEffect(() => {
    function handleMessage(e: MessageEvent<unknown>) {
      // Origin check: only accept from *.preview.forge.dev
      if (!e.origin.endsWith(PREVIEW_ORIGIN_SUFFIX)) return

      const data = e.data as SelectorResult | null
      if (!data || data.type !== 'selector_result') return

      setPending((prev) => {
        if (!prev) return null
        return { ...prev, selector: data.selector, route: data.route }
      })
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  // Focus textarea when pending annotation appears
  useEffect(() => {
    if (pending?.selector !== null) {
      textareaRef.current?.focus()
    }
  }, [pending?.selector])

  // Handle click on the annotation layer (crosshair mode)
  const handleLayerClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!annotationMode || !layerRef.current) return

      const rect = layerRef.current.getBoundingClientRect()
      const x_pct = (e.clientX - rect.left) / rect.width
      const y_pct = (e.clientY - rect.top) / rect.height

      // Validate 0-1
      if (x_pct < 0 || x_pct > 1 || y_pct < 0 || y_pct > 1) return

      // Send postMessage to iframe to get CSS selector
      const iframe = iframeRef.current
      if (iframe?.contentWindow) {
        const iframeRect = iframe.getBoundingClientRect()
        const iframeX = e.clientX - iframeRect.left
        const iframeY = e.clientY - iframeRect.top

        iframe.contentWindow.postMessage(
          { type: 'get_selector', x: iframeX, y: iframeY },
          '*',
        )
      }

      setPending({
        x_pct,
        y_pct,
        screenX: e.clientX - rect.left,
        screenY: e.clientY - rect.top,
        selector: null, // Will be filled by postMessage reply
        route: previewRoute,
      })
      setComment('')
      setPopoverId(null)
    },
    [annotationMode, iframeRef, previewRoute],
  )

  // Save annotation
  const handleSave = useCallback(async () => {
    if (!sandboxId || !pending || !comment.trim()) return
    setSaving(true)
    try {
      const { data } = await apiClient.post<Annotation>(
        `/sandbox/${sandboxId}/annotations`,
        {
          css_selector: pending.selector ?? 'body',
          route: pending.route || previewRoute,
          comment: comment.trim(),
          x_pct: pending.x_pct,
          y_pct: pending.y_pct,
        },
      )
      setAnnotations([...annotations, data])
      setPending(null)
      setComment('')
    } catch {
      // Save may fail
    } finally {
      setSaving(false)
    }
  }, [sandboxId, pending, comment, previewRoute, annotations, setAnnotations])

  // Cancel pending annotation
  const handleCancel = useCallback(() => {
    setPending(null)
    setComment('')
  }, [])

  // Resolve annotation
  const handleResolve = useCallback(
    async (id: string) => {
      // Toggle resolved on the annotation — for now just update local state
      setAnnotations(
        annotations.map((a) =>
          a.id === id ? { ...a, resolved: true } : a,
        ),
      )
      setPopoverId(null)
    },
    [annotations, setAnnotations],
  )

  // Delete annotation
  const handleDelete = useCallback(
    async (id: string) => {
      if (!sandboxId) return
      try {
        await apiClient.delete(`/sandbox/${sandboxId}/annotation/${id}`)
        setAnnotations(annotations.filter((a) => a.id !== id))
      } catch {
        // Deletion may fail
      }
      setPopoverId(null)
    },
    [sandboxId, annotations, setAnnotations],
  )

  return (
    <div
      ref={layerRef}
      onClick={handleLayerClick}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: annotationMode ? 'all' : 'none',
        cursor: annotationMode ? 'crosshair' : 'default',
        zIndex: 10,
      }}
    >
      {/* Annotation dots */}
      {annotations.map((ann) => (
        <div
          key={ann.id}
          style={{
            position: 'absolute',
            left: `${ann.x_pct * 100}%`,
            top: `${ann.y_pct * 100}%`,
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'all',
            zIndex: 11,
          }}
          onMouseEnter={() => setHoveredId(ann.id)}
          onMouseLeave={() => setHoveredId(null)}
          onClick={(e) => {
            e.stopPropagation()
            if (!ann.resolved) {
              setPopoverId(popoverId === ann.id ? null : ann.id)
            }
          }}
        >
          {/* Dot */}
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: ann.resolved ? '#3dffa0' : '#ff6b35',
              opacity: ann.resolved ? 0.5 : 1,
              animation: ann.resolved ? 'none' : 'ember-pulse 1.8s ease-in-out infinite',
              cursor: 'pointer',
            }}
          />

          {/* Hover tooltip */}
          {hoveredId === ann.id && popoverId !== ann.id && (
            <div
              style={{
                position: 'absolute',
                top: -30,
                left: '50%',
                transform: 'translateX(-50%)',
                background: '#0d0d1f',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 4,
                padding: '3px 8px',
                fontFamily: MONO,
                fontSize: 9,
                color: '#e8e8f0',
                whiteSpace: 'nowrap',
                maxWidth: 200,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                pointerEvents: 'none',
                zIndex: 20,
              }}
            >
              {ann.comment.slice(0, 60)}
            </div>
          )}

          {/* Click popover (unresolved only) */}
          {popoverId === ann.id && !ann.resolved && (
            <div
              style={{
                position: 'absolute',
                top: 16,
                left: '50%',
                transform: 'translateX(-50%)',
                background: '#0d0d1f',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 8,
                padding: '8px 10px',
                zIndex: 20,
                minWidth: 130,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 9,
                  color: 'rgba(232,232,240,0.5)',
                  marginBottom: 2,
                  maxWidth: 180,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {ann.comment.slice(0, 60)}
              </div>
              <button
                onClick={() => void handleResolve(ann.id)}
                style={{
                  background: 'rgba(61,255,160,0.08)',
                  border: '1px solid rgba(61,255,160,0.18)',
                  color: '#3dffa0',
                  borderRadius: 4,
                  padding: '3px 8px',
                  fontFamily: MONO,
                  fontSize: 9,
                  cursor: 'pointer',
                }}
              >
                Mark Resolved
              </button>
              <button
                onClick={() => void handleDelete(ann.id)}
                style={{
                  background: 'rgba(255,107,53,0.10)',
                  border: '1px solid rgba(255,107,53,0.18)',
                  color: '#ff6b35',
                  borderRadius: 4,
                  padding: '3px 8px',
                  fontFamily: MONO,
                  fontSize: 9,
                  cursor: 'pointer',
                }}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      ))}

      {/* Pending annotation textarea */}
      {pending && (
        <div
          style={{
            position: 'absolute',
            left: pending.screenX + 8,
            top: pending.screenY + 8,
            background: '#0d0d1f',
            border: '1px solid rgba(99,217,255,0.22)',
            borderRadius: 8,
            padding: 10,
            zIndex: 30,
            width: 200,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <textarea
            ref={textareaRef}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSave()
              }
              if (e.key === 'Escape') handleCancel()
            }}
            placeholder="Add annotation…"
            style={{
              width: '100%',
              height: 60,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 4,
              color: '#e8e8f0',
              fontFamily: MONO,
              fontSize: 10,
              padding: '6px 8px',
              resize: 'none',
              outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            <button
              onClick={() => void handleSave()}
              disabled={saving || !comment.trim()}
              style={{
                flex: 1,
                background: '#63d9ff',
                color: '#04040a',
                border: 'none',
                borderRadius: 4,
                padding: '4px 0',
                fontFamily: MONO,
                fontSize: 9,
                fontWeight: 700,
                cursor: saving ? 'wait' : 'pointer',
                opacity: !comment.trim() ? 0.4 : 1,
              }}
            >
              {saving ? '…' : 'Save'}
            </button>
            <button
              onClick={handleCancel}
              style={{
                flex: 1,
                background: 'transparent',
                color: 'rgba(232,232,240,0.5)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 4,
                padding: '4px 0',
                fontFamily: MONO,
                fontSize: 9,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
          {pending.selector && (
            <div
              style={{
                marginTop: 4,
                fontFamily: MONO,
                fontSize: 8,
                color: 'rgba(232,232,240,0.25)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {pending.selector}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
