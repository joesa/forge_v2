import { useState, useRef, useEffect, useCallback } from 'react'
import { useEditorStore, type Snapshot } from '@/stores/editorStore'

const MONO = "'JetBrains Mono', monospace"

const AGENT_NAMES = [
  'Scaffold',
  'Router',
  'Component',
  'Page',
  'API',
  'DB',
  'Auth',
  'Style',
  'Test',
  'Review',
] as const

interface HoverInfo {
  index: number
  rect: DOMRect
}

export default function SnapshotTimeline() {
  const { snapshots, selectedSnapshot, selectSnapshot } = useEditorStore()

  const [hover, setHover] = useState<HoverInfo | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const dotRefs = useRef<(HTMLDivElement | null)[]>([])

  // Clean up hover on unmount
  useEffect(() => {
    return () => setHover(null)
  }, [])

  const snapshotMap = new Map<number, Snapshot>()
  for (const snap of snapshots) {
    const idx = AGENT_NAMES.findIndex(
      (n) => n.toLowerCase() === snap.agent.toLowerCase(),
    )
    if (idx !== -1) snapshotMap.set(idx, snap)
  }

  const latestIndex = snapshots.length > 0
    ? Math.max(...Array.from(snapshotMap.keys()))
    : -1

  const handleDotClick = useCallback(
    (index: number) => {
      const snap = snapshotMap.get(index)
      if (!snap) return

      // Click selected or LIVE → deselect
      if (selectedSnapshot === snap.id || index === latestIndex) {
        selectSnapshot(null)
      } else {
        selectSnapshot(snap.id)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [snapshots, selectedSnapshot, selectSnapshot, latestIndex],
  )

  const handleMouseEnter = useCallback((index: number) => {
    const el = dotRefs.current[index]
    if (!el) return
    setHover({ index, rect: el.getBoundingClientRect() })
  }, [])

  const handleMouseLeave = useCallback(() => {
    setHover(null)
  }, [])

  // Status text
  const liveSnap = latestIndex >= 0 ? snapshotMap.get(latestIndex) : undefined
  const selectedSnap = selectedSnapshot
    ? snapshots.find((s) => s.id === selectedSnapshot)
    : null
  const selectedIdx = selectedSnap
    ? AGENT_NAMES.findIndex(
        (n) => n.toLowerCase() === selectedSnap.agent.toLowerCase(),
      )
    : -1

  let statusText: string
  let statusColor: string
  if (selectedSnap && selectedIdx >= 0) {
    statusText = `After ${AGENT_NAMES[selectedIdx]}`
    statusColor = 'rgba(232,232,240,0.42)'
  } else if (liveSnap) {
    statusText = '● LIVE'
    statusColor = '#3dffa0'
  } else {
    statusText = ''
    statusColor = 'rgba(232,232,240,0.42)'
  }

  // Format timestamp for popover
  function formatTime(ts: string): string {
    try {
      return new Date(ts).toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
      })
    } catch {
      return ''
    }
  }

  return (
    <div
      style={{
        height: 38,
        flexShrink: 0,
        background: 'rgba(4,4,10,0.95)',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 10px',
        gap: 8,
        position: 'relative',
      }}
    >
      {/* BUILD label */}
      <span
        style={{
          fontFamily: MONO,
          fontSize: 9,
          color: 'rgba(232,232,240,0.42)',
          letterSpacing: 1,
          textTransform: 'uppercase',
          flexShrink: 0,
        }}
      >
        BUILD
      </span>

      {/* 10-dot track */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flex: 1,
          minWidth: 0,
        }}
      >
        {AGENT_NAMES.map((_, i) => {
          const snap = snapshotMap.get(i)
          const exists = !!snap
          const isSelected = exists && snap.id === selectedSnapshot
          const isLive = i === latestIndex && exists

          // Dot color/style
          let dotBg: string
          let dotBorder: string | undefined
          let dotShadow: string | undefined
          let dotAnimation: string | undefined
          let cursor: string

          if (isSelected) {
            dotBg = '#63d9ff'
            dotBorder = '2px solid #63d9ff'
            dotShadow = '0 0 3px rgba(99,217,255,0.6)'
            cursor = 'pointer'
          } else if (isLive) {
            dotBg = '#3dffa0'
            dotAnimation = 'jade-pulse 2s ease-in-out infinite'
            cursor = 'pointer'
          } else if (exists) {
            dotBg = '#3dffa0'
            cursor = 'pointer'
          } else {
            dotBg = 'rgba(255,255,255,0.10)'
            cursor = 'default'
          }

          return (
            <div
              key={i}
              style={{ display: 'flex', alignItems: 'center', flex: i < 9 ? 1 : undefined }}
            >
              {/* Dot */}
              <div
                ref={(el) => { dotRefs.current[i] = el }}
                onClick={() => exists && handleDotClick(i)}
                onMouseEnter={() => exists && handleMouseEnter(i)}
                onMouseLeave={handleMouseLeave}
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: dotBg,
                  border: dotBorder,
                  boxShadow: dotShadow,
                  animation: dotAnimation,
                  cursor,
                  flexShrink: 0,
                  boxSizing: 'border-box',
                }}
              />
              {/* Segment after dot (not after last) */}
              {i < 9 && (
                <div
                  style={{
                    flex: 1,
                    height: 1,
                    background: 'rgba(255,255,255,0.06)',
                    minWidth: 4,
                  }}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Status text */}
      {statusText && (
        <span
          style={{
            fontFamily: MONO,
            fontSize: 9,
            color: statusColor,
            letterSpacing: 0.5,
            flexShrink: 0,
            whiteSpace: 'nowrap',
          }}
        >
          {statusText}
        </span>
      )}

      {/* Hover popover — positioned ABOVE the dot */}
      {hover && snapshotMap.has(hover.index) && (() => {
        const snap = snapshotMap.get(hover.index)!
        const agentName = AGENT_NAMES[hover.index]
        return (
          <div
            ref={popoverRef}
            style={{
              position: 'fixed',
              left: hover.rect.left + hover.rect.width / 2,
              top: hover.rect.top - 8,
              transform: 'translate(-50%, -100%)',
              background: '#0d0d1f',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 6,
              padding: '5px 10px',
              zIndex: 50,
              pointerEvents: 'none',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
            }}
          >
            <span
              style={{
                fontFamily: MONO,
                fontSize: 9,
                color: '#e8e8f0',
                whiteSpace: 'nowrap',
              }}
            >
              {agentName}
            </span>
            <span
              style={{
                fontFamily: MONO,
                fontSize: 8,
                color: 'rgba(232,232,240,0.42)',
                whiteSpace: 'nowrap',
              }}
            >
              {formatTime(snap.timestamp)}
            </span>
          </div>
        )
      })()}
    </div>
  )
}
