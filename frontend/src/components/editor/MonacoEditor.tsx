import { useRef, useCallback, useEffect } from 'react'
import Editor, { type OnMount, type BeforeMount } from '@monaco-editor/react'
import type { editor as MonacoEditor } from 'monaco-editor'

interface MonacoEditorProps {
  value: string
  language?: string
  onChange: (value: string) => void
  onSave: () => void
}

const FORGE_THEME = 'forge-dark'

const beforeMount: BeforeMount = (monaco) => {
  monaco.editor.defineTheme(FORGE_THEME, {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'keyword', foreground: 'b06bff' },
      { token: 'identifier', foreground: '63d9ff' },
      { token: 'string', foreground: '3dffa0' },
      { token: 'type', foreground: 'f5c842' },
      { token: 'comment', foreground: 'e8e8f047', fontStyle: 'italic' },
      { token: 'delimiter', foreground: 'ff6b35' },
      { token: 'number', foreground: 'ff6b35' },
    ],
    colors: {
      'editor.background': '#04040a',
      'editor.foreground': '#e8e8f0',
      'editor.lineHighlightBackground': '#ffffff06',
      'editor.selectionBackground': '#63d9ff1f',
      'editorLineNumber.foreground': '#e8e8f026',
    },
  })
}

function langFromPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'ts':
    case 'tsx':
      return 'typescript'
    case 'js':
    case 'jsx':
      return 'javascript'
    case 'css':
      return 'css'
    case 'html':
      return 'html'
    case 'json':
      return 'json'
    case 'md':
      return 'markdown'
    case 'py':
      return 'python'
    case 'yaml':
    case 'yml':
      return 'yaml'
    default:
      return 'plaintext'
  }
}

export { langFromPath }

export default function ForgeMonacoEditor({
  value,
  language = 'typescript',
  onChange,
  onSave,
}: MonacoEditorProps) {
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null)
  const onSaveRef = useRef(onSave)

  useEffect(() => {
    onSaveRef.current = onSave
  }, [onSave])

  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor
    monaco.editor.setTheme(FORGE_THEME)

    // Ctrl/Cmd+S → immediate save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      onSaveRef.current()
    })
  }, [])

  return (
    <Editor
      height="100%"
      language={language}
      value={value}
      theme={FORGE_THEME}
      beforeMount={beforeMount}
      onMount={handleMount}
      onChange={(val) => {
        if (val !== undefined) onChange(val)
      }}
      options={{
        fontSize: 12,
        lineHeight: 1.85,
        wordWrap: 'on',
        minimap: { enabled: true, size: 'proportional' },
        fontFamily: "'JetBrains Mono', monospace",
        scrollBeyondLastLine: false,
        padding: { top: 16 },
        renderLineHighlight: 'all',
        automaticLayout: true,
      }}
    />
  )
}
