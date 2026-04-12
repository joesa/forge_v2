import { useEffect, useRef, useCallback } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import apiClient from '@/api/client'

const AUTOSAVE_DELAY = 500

export function useEditor(projectId: string) {
  const {
    sessionId,
    activeFile,
    modifiedFiles,
    setProject,
    setSession,
    setFileTree,
    openFile,
    setFileContent,
    markSaved,
    reset,
  } = useEditorStore()

  const wsRef = useRef<WebSocket | null>(null)
  const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  // Mount: create editor session + fetch file tree
  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        const { data: session } = await apiClient.post('/editor/sessions', {
          project_id: projectId,
        })
        if (cancelled) return
        setProject(projectId, session.sandbox_id ?? null)
        setSession(session.id)

        const { data: tree } = await apiClient.get(
          `/projects/${projectId}/files`,
        )
        if (cancelled) return
        setFileTree(tree)
      } catch {
        // Session creation may fail if backend endpoints aren't ready yet
      }
    }

    init()
    return () => {
      cancelled = true
    }
  }, [projectId, setProject, setSession, setFileTree])

  // WebSocket: connect when session is ready
  useEffect(() => {
    if (!sessionId) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = import.meta.env.VITE_API_BASE_URL
      ? new URL(import.meta.env.VITE_API_BASE_URL as string).host
      : window.location.host
    const url = `${protocol}://${host}/api/v1/editor/sessions/${sessionId}/stream`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as {
          type: string
          path?: string
          content?: string
        }
        if (msg.type === 'file_updated' && msg.path && msg.content !== undefined) {
          // External update from another agent/session
          const current = useEditorStore.getState()
          if (!current.modifiedFiles.has(msg.path)) {
            setFileContent(msg.path, msg.content)
            markSaved(msg.path)
          }
        }
      } catch {
        // Ignore malformed messages
      }
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [sessionId, setFileContent, markSaved])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      debounceTimers.current.forEach((t) => clearTimeout(t))
      debounceTimers.current.clear()
      reset()
    }
  }, [reset])

  // Auto-save: 500ms debounce
  const scheduleAutoSave = useCallback(
    (path: string) => {
      const existing = debounceTimers.current.get(path)
      if (existing) clearTimeout(existing)

      const timer = setTimeout(async () => {
        debounceTimers.current.delete(path)
        const content = useEditorStore.getState().fileContents[path]
        if (content === undefined) return
        try {
          await apiClient.put(`/projects/${projectId}/files/content`, {
            path,
            content,
          })
          markSaved(path)
        } catch {
          // Save failed — file stays modified
        }
      }, AUTOSAVE_DELAY)

      debounceTimers.current.set(path, timer)
    },
    [projectId, markSaved],
  )

  // Immediate save (Ctrl/Cmd+S)
  const saveNow = useCallback(
    async (path?: string) => {
      const target = path ?? activeFile
      if (!target) return

      // Cancel pending debounce
      const existing = debounceTimers.current.get(target)
      if (existing) {
        clearTimeout(existing)
        debounceTimers.current.delete(target)
      }

      const content = useEditorStore.getState().fileContents[target]
      if (content === undefined) return
      try {
        await apiClient.put(`/projects/${projectId}/files/content`, {
          path: target,
          content,
        })
        markSaved(target)
      } catch {
        // Save failed
      }
    },
    [projectId, activeFile, markSaved],
  )

  // Handle file content change from editor
  const handleContentChange = useCallback(
    (path: string, content: string) => {
      setFileContent(path, content)
      scheduleAutoSave(path)
    },
    [setFileContent, scheduleAutoSave],
  )

  // Handle file click from tree
  const handleFileOpen = useCallback(
    async (path: string) => {
      const state = useEditorStore.getState()
      if (state.fileContents[path] !== undefined) {
        openFile(path)
        return
      }
      try {
        const { data } = await apiClient.get<{ content: string }>(
          `/projects/${projectId}/files/content`,
          { params: { path } },
        )
        openFile(path, data.content)
      } catch {
        openFile(path, `// Failed to load ${path}`)
      }
    },
    [projectId, openFile],
  )

  return {
    saveNow,
    handleContentChange,
    handleFileOpen,
    isModified: modifiedFiles.size > 0,
  }
}
