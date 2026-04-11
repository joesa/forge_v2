import type { ReactNode } from 'react'
import TopNav from './TopNav'
import Sidebar from './Sidebar'

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--void)' }}>
      <TopNav />
      <Sidebar />
      <main
        style={{
          marginLeft: 220,
          paddingTop: 0,
          minHeight: 'calc(100vh - 62px)',
        }}
        className="grid-bg"
      >
        {children}
      </main>
    </div>
  )
}
