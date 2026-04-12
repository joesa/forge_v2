import { useRef, useEffect } from 'react'
import { useEditorStore } from '@/stores/editorStore'

const MONO = "'JetBrains Mono', monospace"

export default function EditorTabs() {
  const { openFiles, activeFile, modifiedFiles, setActiveFile, closeFile } =
    useEditorStore()
  const containerRef = useRef<HTMLDivElement>(null)

  // Scroll active tab into view
  useEffect(() => {
    if (!containerRef.current || !activeFile) return
    const idx = openFiles.indexOf(activeFile)
    const tab = containerRef.current.children[idx] as HTMLElement | undefined
    tab?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
  }, [activeFile, openFiles])

  if (openFiles.length === 0) return null

  return (
    <div
      ref={containerRef}
      style={{
        height: 34,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        overflowX: 'auto',
        flexShrink: 0,
      }}
    >
      {openFiles.map((path) => {
        const name = path.split('/').pop() ?? path
        const isActive = path === activeFile
        const isModified = modifiedFiles.has(path)

        return (
          <div
            key={path}
            onClick={() => setActiveFile(path)}
            style={{
              minWidth: 90,
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              padding: '0 13px',
              fontFamily: MONO,
              fontSize: 10,
              color: isActive ? 'var(--text)' : 'rgba(232,232,240,0.40)',
              borderBottom: isActive
                ? '2px solid #63d9ff'
                : '2px solid transparent',
              background: isActive ? 'rgba(255,255,255,0.02)' : 'transparent',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            {isModified && (
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#ff6b35',
                  flexShrink: 0,
                }}
              />
            )}
            {name}
            <span
              onClick={(e) => {
                e.stopPropagation()
                closeFile(path)
              }}
              style={{
                marginLeft: 'auto',
                fontSize: 10,
                color: 'rgba(232,232,240,0.25)',
                cursor: 'pointer',
                padding: '0 2px',
              }}
            >
              ×
            </span>
          </div>
        )
      })}
    </div>
  )
}
