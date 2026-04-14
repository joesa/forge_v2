import { useState, useRef, useEffect, useCallback } from 'react'
import { useEditorStore, type Snapshot, type SyncStepStatus } from '@/stores/editorStore'

const MONO = "'JetBrains Mono', monospace"

// ── Pipeline build agents (original 10-dot track) ────────────────
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

// ── Chat edit sync steps ─────────────────────────────────────────
const SYNC_STEP_KEYS = ['parsing', 'saving', 'syncing', 'applied', 'live'] as const
const SYNC_STEP_LABELS: Record<typeof SYNC_STEP_KEYS[number], string> = {
  parsing: 'Parsing',
  saving: 'Saving',
  syncing: 'Syncing',
  applied: 'Applied',
  live: 'Live',
}

interface HoverInfo {
  index: number
  rect: DOMRect
}

// ── Sync step dot ────────────────────────────────────────────────
function SyncDot({ status, label, isLast }: { status: SyncStepStatus; label: string; isLast: boolean }) {
  let bg: string
  let border: string | undefined
  let shadow: string | undefined
  let animation: string | undefined

  switch (status) {
    case 'active':
      bg = '#f5c842'
      border = '2px solid #f5c842'
      shadow = '0 0 6px rgba(245,200,66,0.5)'
      animation = 'gold-pulse 1s ease-in-out infinite'
      break
    case 'done':
      bg = '#3dffa0'
      shadow = '0 0 3px rgba(61,255,160,0.4)'
      break
    case 'error':
      bg = '#ff5050'
      shadow = '0 0 4px rgba(255,80,80,0.5)'
      break
    default:
      bg = 'rgba(255,255,255,0.10)'
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', flex: isLast ? undefined : 1 }} title={label}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: bg,
          border,
          boxShadow: shadow,
          animation,
          flexShrink: 0,
          boxSizing: 'border-box',
          transition: 'background 0.2s, box-shadow 0.2s',
        }}
      />
      {!isLast && (
        <div
          style={{
            flex: 1,
            height: 1,
            background: status === 'done' ? 'rgba(61,255,160,0.25)' : 'rgba(255,255,255,0.06)',
            minWidth: 4,
            transition: 'background 0.3s',
          }}
        />
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────
export default function SnapshotTimeline() {
  const { snapshots, selectedSnapshot, selectSnapshot, syncSteps, chatStreaming } = useEditorStore()

  const [hover, setHover] = useState<HoverInfo | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const dotRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    return () => setHover(null)
  }, [])

  // Determine mode: show sync steps when chat is streaming or steps are active
  const syncActive = chatStreaming ||
    SYNC_STEP_KEYS.some((k) => syncSteps[k] === 'active' || syncSteps[k] === 'done')

  // ── Pipeline snapshot map ──────────────────────────────────────
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

  // ── Status text ────────────────────────────────────────────────
  let statusText: string
  let statusColor: string

  if (syncActive) {
    const activeStep = SYNC_STEP_KEYS.find((k) => syncSteps[k] === 'active')
    if (activeStep) {
      const file = syncSteps.currentFile
      statusText = file
        ? `${SYNC_STEP_LABELS[activeStep]}: ${file.split('/').pop()}`
        : SYNC_STEP_LABELS[activeStep]
      statusColor = '#f5c842'
    } else if (syncSteps.live === 'done') {
      statusText = '● LIVE'
      statusColor = '#3dffa0'
    } else {
      statusText = '● Processing...'
      statusColor = '#f5c842'
    }
  } else {
    const liveSnap = latestIndex >= 0 ? snapshotMap.get(latestIndex) : undefined
    const selectedSnap = selectedSnapshot
      ? snapshots.find((s) => s.id === selectedSnapshot)
      : null
    const selectedIdx = selectedSnap
      ? AGENT_NAMES.findIndex(
          (n) => n.toLowerCase() === selectedSnap.agent.toLowerCase(),
        )
      : -1

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
  }

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
      {/* Label */}
      <span
        style={{
          fontFamily: MONO,
          fontSize: 9,
          color: syncActive ? '#f5c842' : 'rgba(232,232,240,0.42)',
          letterSpacing: 1,
          textTransform: 'uppercase',
          flexShrink: 0,
          transition: 'color 0.2s',
        }}
      >
        {syncActive ? 'SYNC' : 'BUILD'}
      </span>

      {/* Dot track */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flex: 1,
          minWidth: 0,
        }}
      >
        {syncActive
          ? // ── Chat edit sync steps (5 dots) ──
            SYNC_STEP_KEYS.map((key, i) => (
              <SyncDot
                key={key}
                status={syncSteps[key]}
                label={SYNC_STEP_LABELS[key]}
                isLast={i === SYNC_STEP_KEYS.length - 1}
              />
            ))
          : // ── Pipeline build agents (10 dots) ──
            AGENT_NAMES.map((_, i) => {
              const snap = snapshotMap.get(i)
              const exists = !!snap
              const isSelected = exists && snap.id === selectedSnapshot
              const isLive = i === latestIndex && exists

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
            transition: 'color 0.2s',
          }}
        >
          {statusText}
        </span>
      )}

      {/* Hover popover — pipeline snapshots only */}
      {!syncActive && hover && snapshotMap.has(hover.index) && (() => {
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
            <span style={{ fontFamily: MONO, fontSize: 9, color: '#e8e8f0', whiteSpace: 'nowrap' }}>
              {agentName}
            </span>
            <span style={{ fontFamily: MONO, fontSize: 8, color: 'rgba(232,232,240,0.42)', whiteSpace: 'nowrap' }}>
              {formatTime(snap.timestamp)}
            </span>
          </div>
        )
      })()}
    </div>
  )
}
