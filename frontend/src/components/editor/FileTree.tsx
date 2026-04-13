import { useState, useCallback, useRef, useEffect } from 'react'
import { useEditorStore, type FileNode } from '@/stores/editorStore'

interface FileTreeProps {
  onFileOpen: (path: string) => void
}

const MONO = "'JetBrains Mono', monospace"

function FileTreeItem({
  node,
  depth,
  activeFile,
  modifiedFiles,
  onFileOpen,
  collapsedDirs,
  toggleDir,
}: {
  node: FileNode
  depth: number
  activeFile: string | null
  modifiedFiles: Set<string>
  onFileOpen: (path: string) => void
  collapsedDirs: Set<string>
  toggleDir: (path: string) => void
}) {
  const isActive = node.path === activeFile
  const isModified = modifiedFiles.has(node.path)
  const isDir = node.type === 'dir'
  const isCollapsed = collapsedDirs.has(node.path)

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null)
  const closeRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    return () => {
      if (closeRef.current) {
        document.removeEventListener('click', closeRef.current)
      }
    }
  }, [])

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      if (closeRef.current) {
        document.removeEventListener('click', closeRef.current)
      }
      setContextMenu({ x: e.clientX, y: e.clientY })
      const close = () => {
        setContextMenu(null)
        document.removeEventListener('click', close)
        closeRef.current = null
      }
      closeRef.current = close
      document.addEventListener('click', close)
    },
    [],
  )

  const handleClick = () => {
    if (isDir) {
      toggleDir(node.path)
    } else {
      onFileOpen(node.path)
    }
  }

  const dotColor = isActive
    ? '#63d9ff'
    : isModified
      ? '#ff6b35'
      : 'transparent'

  const textColor = isActive
    ? '#63d9ff'
    : isDir
      ? 'var(--text)'
      : 'rgba(232,232,240,0.42)'

  return (
    <>
      <div
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 8px',
          paddingLeft: 8 + depth * 11,
          fontFamily: MONO,
          fontSize: 11,
          color: textColor,
          background: isActive ? 'rgba(99,217,255,0.08)' : 'transparent',
          cursor: 'pointer',
        }}
      >
        {isDir ? (
          <span style={{ fontSize: 8, color: '#f5c842', transition: 'transform 120ms', transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)' }}>▶</span>
        ) : (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: dotColor,
              flexShrink: 0,
            }}
          />
        )}
        {node.name}
      </div>

      {/* Children */}
      {isDir && !isCollapsed && node.children?.map((child) => (
        <FileTreeItem
          key={child.path}
          node={child}
          depth={depth + 1}
          activeFile={activeFile}
          modifiedFiles={modifiedFiles}
          onFileOpen={onFileOpen}
          collapsedDirs={collapsedDirs}
          toggleDir={toggleDir}
        />
      ))}

      {/* Context menu */}
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            zIndex: 1000,
            background: '#111125',
            border: '1px solid rgba(255,255,255,0.10)',
            borderRadius: 6,
            padding: '4px 0',
            minWidth: 140,
          }}
        >
          {['New File', 'Rename', 'Delete', 'Copy Path'].map((action) => (
            <div
              key={action}
              style={{
                padding: '5px 12px',
                fontSize: 11,
                fontFamily: MONO,
                color: action === 'Delete' ? '#ff6b35' : 'var(--text)',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.05)'
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLDivElement).style.background = 'transparent'
              }}
              onClick={() => {
                if (action === 'Copy Path') {
                  void navigator.clipboard.writeText(node.path)
                }
                // Other actions: Phase 2
                setContextMenu(null)
              }}
            >
              {action}
            </div>
          ))}
        </div>
      )}
    </>
  )
}

export default function FileTree({ onFileOpen }: FileTreeProps) {
  const { fileTree, activeFile, modifiedFiles } = useEditorStore()
  const [collapsedDirs, setCollapsedDirs] = useState<Set<string>>(new Set())

  const toggleDir = useCallback((path: string) => {
    setCollapsedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }, [])

  return (
    <div style={{ borderRight: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div
        style={{
          fontFamily: MONO,
          fontSize: 9,
          textTransform: 'uppercase',
          letterSpacing: 1,
          color: 'rgba(232,232,240,0.40)',
          padding: '9px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>Explorer</span>
        <span style={{ color: '#63d9ff', cursor: 'pointer' }}>+</span>
      </div>
      <div style={{ padding: '6px 0', overflowY: 'auto', flex: 1 }}>
        {fileTree.map((node) => (
          <FileTreeItem
            key={node.path}
            node={node}
            depth={0}
            activeFile={activeFile}
            modifiedFiles={modifiedFiles}
            onFileOpen={onFileOpen}
            collapsedDirs={collapsedDirs}
            toggleDir={toggleDir}
          />
        ))}
      </div>
    </div>
  )
}
