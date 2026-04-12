import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Editor from '@monaco-editor/react'

const mockFiles = [
  { name: 'src', type: 'dir' as const, depth: 0, children: [
    { name: 'app', type: 'dir' as const, depth: 1, children: [
      { name: 'dashboard', type: 'dir' as const, depth: 2, children: [
        { name: 'page.tsx', type: 'file' as const, depth: 3, status: 'active' as const },
        { name: 'layout.tsx', type: 'file' as const, depth: 3, status: 'modified' as const },
      ]},
      { name: 'layout.tsx', type: 'file' as const, depth: 2, status: 'default' as const },
      { name: 'page.tsx', type: 'file' as const, depth: 2, status: 'default' as const },
    ]},
    { name: 'components', type: 'dir' as const, depth: 1, children: [
      { name: 'Header.tsx', type: 'file' as const, depth: 2, status: 'new' as const },
      { name: 'Sidebar.tsx', type: 'file' as const, depth: 2, status: 'default' as const },
    ]},
    { name: 'globals.css', type: 'file' as const, depth: 1, status: 'modified' as const },
  ]},
  { name: 'package.json', type: 'file' as const, depth: 0, status: 'default' as const },
  { name: 'tsconfig.json', type: 'file' as const, depth: 0, status: 'default' as const },
]

const sampleCode = `import { Card } from '@/components/ui/card'
import { BarChart, Users, Activity, DollarSign } from 'lucide-react'

export default function DashboardPage() {
  const stats = [
    { title: 'Total Revenue', value: '$45,231', icon: DollarSign, change: '+20.1%' },
    { title: 'Subscriptions', value: '+2350', icon: Users, change: '+180.1%' },
    { title: 'Sales', value: '+12,234', icon: BarChart, change: '+19%' },
    { title: 'Active Now', value: '+573', icon: Activity, change: '+201' },
  ]

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.title} className="p-6">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted">{stat.title}</span>
              <stat.icon className="h-4 w-4 text-muted" />
            </div>
            <div className="text-2xl font-bold mt-2">{stat.value}</div>
            <p className="text-xs text-green-500 mt-1">{stat.change} from last month</p>
          </Card>
        ))}
      </div>
    </div>
  )
}`

const activityIcons = ['📁', '🔍', '⚡', '🔀', '🐛', '🧪']

const statusDotColor: Record<string, string> = {
  active: '#63d9ff',
  modified: '#ff6b35',
  new: '#3dffa0',
  default: 'transparent',
}

interface FileItem {
  name: string
  type: 'file' | 'dir'
  depth: number
  status?: string
  children?: FileItem[]
}

function flattenFiles(items: FileItem[]): FileItem[] {
  const result: FileItem[] = []
  for (const item of items) {
    result.push(item)
    if (item.type === 'dir' && item.children) {
      result.push(...flattenFiles(item.children))
    }
  }
  return result
}

export default function EditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [showPreview, setShowPreview] = useState(false)
  const [activeActivity, setActiveActivity] = useState(0)
  const flat = flattenFiles(mockFiles)

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#04040a' }}>
      {/* Top bar */}
      <div style={{ height: 46, background: '#080812', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0, zIndex: 50, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 11 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 22, height: 22, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 16, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
          <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)', margin: '0 4px' }} />
          <span style={{ fontSize: 12, color: 'rgba(232,232,240,0.55)', cursor: 'pointer' }}>SaaS Dashboard ▼</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.30)', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: 10 }}>○ main</span>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'var(--ember)' }}>● 2 errors</span>
          <button className="btn btn-ghost btn-sm" style={{ height: 28, fontSize: 11 }} onClick={() => setShowPreview(!showPreview)}>
            {showPreview ? '⊟' : '⊞'} Preview
          </button>
          <button className="btn btn-primary btn-sm" style={{ height: 28, fontSize: 11 }}>▲ Deploy</button>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: 'var(--void)' }}>JS</div>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: `46px 210px 1fr ${showPreview ? '310px' : ''} 295px`, overflow: 'hidden', minHeight: 0 }}>
        {/* Activity bar — 46px */}
        <div style={{ background: 'rgba(4,4,10,0.90)', borderRight: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '10px 0', gap: 5 }}>
          {activityIcons.map((icon, i) => (
            <div
              key={i}
              onClick={() => setActiveActivity(i)}
              style={{
                width: 34, height: 34, borderRadius: activeActivity === i ? '0 6px 6px 0' : 6,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, cursor: 'pointer',
                color: activeActivity === i ? '#63d9ff' : 'rgba(232,232,240,0.40)',
                background: activeActivity === i ? 'rgba(99,217,255,0.08)' : 'transparent',
                borderLeft: activeActivity === i ? '2px solid #63d9ff' : '2px solid transparent',
                marginLeft: activeActivity === i ? -1 : 0,
              }}
            >{icon}</div>
          ))}
          <div style={{ flex: 1 }} />
          <div style={{ width: 34, height: 34, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, cursor: 'pointer', color: 'rgba(232,232,240,0.40)' }} onClick={() => navigate(`/projects/${id}/settings`)}>⚙️</div>
        </div>

        {/* File tree */}
        <div style={{ borderRight: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', padding: '9px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between' }}>
            <span>Explorer</span>
            <span style={{ color: '#63d9ff', cursor: 'pointer' }}>+</span>
          </div>
          <div style={{ padding: '6px 0', overflowY: 'auto', flex: 1 }}>
            {flat.map((f, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: `3px 8px`, paddingLeft: 8 + f.depth * 11,
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
                color: f.status === 'active' ? '#63d9ff' : f.type === 'dir' ? 'var(--text)' : 'rgba(232,232,240,0.42)',
                background: f.status === 'active' ? 'rgba(99,217,255,0.08)' : 'transparent',
                cursor: 'pointer',
              }}>
                {f.type === 'dir' ? (
                  <span style={{ fontSize: 8, color: '#f5c842' }}>▶</span>
                ) : (
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: statusDotColor[f.status ?? 'default'], flexShrink: 0 }} />
                )}
                {f.name}
              </div>
            ))}
          </div>
        </div>

        {/* Main editor area */}
        <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Tab bar */}
          <div style={{ height: 34, borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', overflowX: 'auto', flexShrink: 0 }}>
            {[{ name: 'page.tsx', active: true, modified: false }, { name: 'layout.tsx', active: false, modified: true }].map((tab) => (
              <div key={tab.name} style={{
                minWidth: 90, display: 'flex', alignItems: 'center', gap: 7, padding: '0 13px',
                fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
                color: tab.active ? 'var(--text)' : 'rgba(232,232,240,0.40)',
                borderBottom: tab.active ? '2px solid #63d9ff' : '2px solid transparent',
                background: tab.active ? 'rgba(255,255,255,0.02)' : 'transparent',
                cursor: 'pointer',
              }}>
                {tab.modified && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff6b35' }} />}
                {tab.name}
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'rgba(232,232,240,0.25)', cursor: 'pointer' }}>×</span>
              </div>
            ))}
          </div>

          {/* Breadcrumb */}
          <div style={{ padding: '5px 14px', background: 'rgba(255,255,255,0.015)', borderBottom: '1px solid rgba(255,255,255,0.06)', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.30)' }}>
            src › app › dashboard › <span style={{ color: '#63d9ff' }}>page.tsx</span>
          </div>

          {/* Monaco */}
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <Editor
              height="100%"
              defaultLanguage="typescript"
              defaultValue={sampleCode}
              theme="vs-dark"
              options={{
                fontSize: 12,
                lineHeight: 1.85,
                minimap: { enabled: true, size: 'proportional' },
                fontFamily: "'JetBrains Mono', monospace",
                scrollBeyondLastLine: false,
                padding: { top: 16 },
                renderLineHighlight: 'all',
              }}
              beforeMount={(monaco) => {
                monaco.editor.defineTheme('forge-dark', {
                  base: 'vs-dark',
                  inherit: true,
                  rules: [
                    { token: 'keyword', foreground: 'b06bff' },
                    { token: 'identifier', foreground: '63d9ff' },
                    { token: 'string', foreground: '3dffa0' },
                    { token: 'type', foreground: 'f5c842' },
                    { token: 'comment', foreground: '6b6b88', fontStyle: 'italic' },
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
              }}
              onMount={(editor, monaco) => {
                monaco.editor.setTheme('forge-dark')
                // Suppress unused warning
                void editor
              }}
            />
          </div>
        </div>

        {/* Preview pane (conditional) */}
        {showPreview && (
          <div style={{ borderLeft: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Preview toolbar */}
            <div style={{ height: 38, background: 'rgba(4,4,10,0.95)', borderBottom: '1px solid rgba(255,255,255,0.06)', padding: '0 10px', display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
              <span style={{ fontSize: 11, color: 'rgba(232,232,240,0.30)', cursor: 'pointer' }}>←</span>
              <span style={{ fontSize: 11, color: 'rgba(232,232,240,0.30)', cursor: 'pointer' }}>→</span>
              <div style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(232,232,240,0.30)', background: 'rgba(255,255,255,0.04)', borderRadius: 4, padding: '4px 8px' }}>localhost:3000/dashboard</div>
              <span style={{ fontSize: 10, cursor: 'pointer', color: 'rgba(232,232,240,0.30)' }}>📱</span>
              <span style={{ fontSize: 10, cursor: 'pointer', color: '#63d9ff' }}>💻</span>
            </div>

            {/* Preview body — placeholder */}
            <div style={{ flex: 1, background: '#04040a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(232,232,240,0.20)' }}>Preview — Phase 3</span>
            </div>

            {/* Snapshot timeline — placeholder */}
            <div style={{ height: 38, background: 'rgba(4,4,10,0.95)', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', padding: '0 10px', gap: 5, flexShrink: 0 }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 7, color: 'rgba(232,232,240,0.30)' }}>BUILD</span>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 3 }}>
                {Array.from({ length: 10 }, (_, i) => (
                  <div key={i} style={{ width: 8, height: 8, borderRadius: '50%', background: i < 6 ? '#3dffa0' : 'rgba(232,232,240,0.15)' }} />
                ))}
              </div>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#3dffa0', animation: 'jade-pulse 2s ease-in-out infinite' }} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 7, color: '#3dffa0' }}>● LIVE</span>
            </div>
          </div>
        )}

        {/* Chat panel */}
        <div style={{ borderLeft: '1px solid rgba(255,255,255,0.06)', background: '#080812', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Chat header */}
          <div style={{ padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
            <div style={{ width: 26, height: 26, borderRadius: '50%', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>⚡</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 700 }}>Forge AI</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#3dffa0' }}>● active · claude-sonnet-4</div>
            </div>
            <span style={{ fontSize: 12, color: 'rgba(232,232,240,0.30)', cursor: 'pointer' }}>⚙</span>
          </div>

          {/* Chat messages */}
          <div style={{ flex: 1, padding: 12, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 9 }}>
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, fontWeight: 700, letterSpacing: 0.5, color: 'rgba(232,232,240,0.35)', marginBottom: 3 }}>YOU</div>
              <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, padding: '9px 11px', fontSize: 11, lineHeight: 1.6, color: 'rgba(232,232,240,0.65)' }}>
                Add a dark theme to the dashboard with chart components
              </div>
            </div>
            <div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, fontWeight: 700, letterSpacing: 0.5, color: '#63d9ff', marginBottom: 3 }}>FORGE AI</div>
              <div style={{ background: 'rgba(99,217,255,0.08)', border: '1px solid rgba(99,217,255,0.14)', borderRadius: 8, padding: '9px 11px', fontSize: 11, lineHeight: 1.6 }}>
                I&apos;ll add a dark theme with chart components. Updating 3 files...
                <div style={{ background: '#04040a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 7, overflow: 'hidden', marginTop: 6 }}>
                  <div style={{ padding: '6px 10px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#63d9ff' }}>globals.css</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button className="btn btn-ghost" style={{ height: 22, padding: '0 6px', fontSize: 9 }}>Copy</button>
                      <button className="btn btn-primary" style={{ height: 22, padding: '0 6px', fontSize: 9 }}>Apply</button>
                    </div>
                  </div>
                  <div style={{ padding: '9px 11px', fontFamily: "'JetBrains Mono', monospace", fontSize: 9, lineHeight: 1.7, color: 'rgba(232,232,240,0.55)' }}>
                    :root {'{'}<br />
                    &nbsp;&nbsp;--background: #04040a;<br />
                    &nbsp;&nbsp;--foreground: #e8e8f0;<br />
                    {'}'}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Chat input */}
          <div style={{ padding: '9px 10px', borderTop: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 6 }}>
              {['/build', '/deploy', '/test', '/lint'].map((cmd) => (
                <span key={cmd} style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 8, padding: '2px 6px', background: 'rgba(99,217,255,0.08)', color: '#63d9ff', border: '1px solid rgba(99,217,255,0.18)', borderRadius: 3, cursor: 'pointer' }}>{cmd}</span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 5 }}>
              <textarea rows={2} style={{ flex: 1, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, resize: 'none', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 5, padding: '6px 9px', color: 'var(--text)', outline: 'none' }} placeholder="Ask Forge AI..." />
              <button style={{ width: 28, height: 28, background: '#63d9ff', border: 'none', borderRadius: 5, color: '#04040a', fontSize: 13, fontWeight: 700, cursor: 'pointer', flexShrink: 0, alignSelf: 'flex-end' }}>→</button>
            </div>
          </div>
        </div>
      </div>

      {/* Status bar */}
      <div style={{ height: 22, background: '#63d9ff', flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 16, fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#04040a', fontWeight: 700 }}>
        <span>⚡ Forge</span>
        <span>TypeScript</span>
        <span>Ln 24, Col 8</span>
        <span>No errors</span>
        <div style={{ flex: 1 }} />
        <span>Sandbox: ● Running</span>
        <span>main</span>
      </div>
    </div>
  )
}
