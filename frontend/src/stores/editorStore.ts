import { create } from 'zustand'

export interface Annotation {
  id: string
  x_pct: number
  y_pct: number
  comment: string
  resolved: boolean
}

export interface Snapshot {
  id: string
  url: string
  agent: string
  timestamp: string
}

export interface FileNode {
  path: string
  name: string
  type: 'file' | 'dir'
  children?: FileNode[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  pending?: boolean
}

export type SyncStepStatus = 'idle' | 'active' | 'done' | 'error'

export interface SyncSteps {
  parsing: SyncStepStatus
  saving: SyncStepStatus
  syncing: SyncStepStatus
  applied: SyncStepStatus
  live: SyncStepStatus
  currentFile: string | null
}

const IDLE_SYNC: SyncSteps = {
  parsing: 'idle',
  saving: 'idle',
  syncing: 'idle',
  applied: 'idle',
  live: 'idle',
  currentFile: null,
}

interface EditorState {
  projectId: string | null
  sandboxId: string | null
  sessionId: string | null

  fileTree: FileNode[]
  openFiles: string[]
  activeFile: string | null
  fileContents: Record<string, string>
  modifiedFiles: Set<string>

  previewVisible: boolean
  previewDevice: 'mobile' | 'desktop'
  previewRoute: string

  annotationMode: boolean
  annotations: Annotation[]
  snapshots: Snapshot[]
  selectedSnapshot: string | null

  devConsoleErrors: number
  chatVisible: boolean
  chatMessages: ChatMessage[]
  chatStreaming: boolean
  syncSteps: SyncSteps

  setProject: (projectId: string, sandboxId: string | null) => void
  setSession: (sessionId: string) => void
  setFileTree: (tree: FileNode[]) => void
  openFile: (path: string, content?: string) => void
  closeFile: (path: string) => void
  setActiveFile: (path: string) => void
  setFileContent: (path: string, content: string) => void
  markSaved: (path: string) => void
  markAllSaved: () => void

  togglePreview: () => void
  setPreviewDevice: (device: 'mobile' | 'desktop') => void
  setPreviewRoute: (route: string) => void

  toggleAnnotationMode: () => void
  setAnnotations: (annotations: Annotation[]) => void
  setSnapshots: (snapshots: Snapshot[]) => void
  selectSnapshot: (id: string | null) => void

  setDevConsoleErrors: (count: number) => void
  setChatVisible: (visible: boolean) => void
  addChatMessage: (msg: ChatMessage) => void
  updateLastAssistantMessage: (content: string) => void
  setChatStreaming: (streaming: boolean) => void
  clearChat: () => void
  setSyncStep: (step: keyof Omit<SyncSteps, 'currentFile'>, status: SyncStepStatus) => void
  setSyncFile: (file: string | null) => void
  resetSyncSteps: () => void

  reset: () => void
}

const initialState = {
  projectId: null as string | null,
  sandboxId: null as string | null,
  sessionId: null as string | null,
  fileTree: [] as FileNode[],
  openFiles: [] as string[],
  activeFile: null as string | null,
  fileContents: {} as Record<string, string>,
  modifiedFiles: new Set<string>(),
  previewVisible: false,
  previewDevice: 'desktop' as const,
  previewRoute: '/',
  annotationMode: false,
  annotations: [] as Annotation[],
  snapshots: [] as Snapshot[],
  selectedSnapshot: null as string | null,
  devConsoleErrors: 0,
  chatVisible: true,
  chatMessages: [] as ChatMessage[],
  chatStreaming: false,
  syncSteps: { ...IDLE_SYNC } as SyncSteps,
}

export const useEditorStore = create<EditorState>((set) => ({
  ...initialState,

  setProject: (projectId, sandboxId) => set({ projectId, sandboxId }),
  setSession: (sessionId) => set({ sessionId }),
  setFileTree: (tree) => set({ fileTree: tree }),

  openFile: (path, content) =>
    set((state) => {
      const openFiles = state.openFiles.includes(path)
        ? state.openFiles
        : [...state.openFiles, path]
      const fileContents =
        content !== undefined
          ? { ...state.fileContents, [path]: content }
          : state.fileContents
      return { openFiles, activeFile: path, fileContents }
    }),

  closeFile: (path) =>
    set((state) => {
      const openFiles = state.openFiles.filter((f) => f !== path)
      const activeFile =
        state.activeFile === path
          ? openFiles[openFiles.length - 1] ?? null
          : state.activeFile
      const { [path]: _, ...fileContents } = state.fileContents
      void _
      const modifiedFiles = new Set(state.modifiedFiles)
      modifiedFiles.delete(path)
      return { openFiles, activeFile, fileContents, modifiedFiles }
    }),

  setActiveFile: (path) => set({ activeFile: path }),

  setFileContent: (path, content) =>
    set((state) => {
      const modifiedFiles = new Set(state.modifiedFiles)
      modifiedFiles.add(path)
      return {
        fileContents: { ...state.fileContents, [path]: content },
        modifiedFiles,
      }
    }),

  markSaved: (path) =>
    set((state) => {
      const modifiedFiles = new Set(state.modifiedFiles)
      modifiedFiles.delete(path)
      return { modifiedFiles }
    }),

  markAllSaved: () => set({ modifiedFiles: new Set() }),

  togglePreview: () => set((s) => ({ previewVisible: !s.previewVisible })),
  setPreviewDevice: (device) => set({ previewDevice: device }),
  setPreviewRoute: (route) => set({ previewRoute: route }),

  toggleAnnotationMode: () => set((s) => ({ annotationMode: !s.annotationMode })),
  setAnnotations: (annotations) => set({ annotations }),
  setSnapshots: (snapshots) => set({ snapshots }),
  selectSnapshot: (id) => set({ selectedSnapshot: id }),

  setDevConsoleErrors: (count) => set({ devConsoleErrors: count }),
  setChatVisible: (visible) => set({ chatVisible: visible }),
  addChatMessage: (msg) => set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
  updateLastAssistantMessage: (content) =>
    set((s) => {
      const msgs = [...s.chatMessages]
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i] = { ...msgs[i], content, pending: false }
          break
        }
      }
      return { chatMessages: msgs }
    }),
  setChatStreaming: (streaming) => set({ chatStreaming: streaming }),
  clearChat: () => set({ chatMessages: [], chatStreaming: false }),
  setSyncStep: (step, status) =>
    set((s) => ({ syncSteps: { ...s.syncSteps, [step]: status } })),
  setSyncFile: (file) =>
    set((s) => ({ syncSteps: { ...s.syncSteps, currentFile: file } })),
  resetSyncSteps: () => set({ syncSteps: { ...IDLE_SYNC } }),

  reset: () => set({ ...initialState, modifiedFiles: new Set(), syncSteps: { ...IDLE_SYNC } }),
}))
