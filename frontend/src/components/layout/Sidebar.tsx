import { NavLink } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

interface NavItem {
  label: string
  to: string
  icon: string
  indent?: boolean
}

const mainItems: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: '🏠' },
  { label: 'Projects', to: '/projects', icon: '📁' },
  { label: 'Ideate', to: '/ideate', icon: '💡' },
]

const settingsItems: NavItem[] = [
  { label: 'Profile', to: '/settings/profile', icon: '👤', indent: true },
  { label: 'AI Providers', to: '/settings/ai-providers', icon: '🤖', indent: true },
  { label: 'Model Routing', to: '/settings/model-routing', icon: '⚡', indent: true },
  { label: 'Integrations', to: '/settings/integrations', icon: '🔗', indent: true },
  { label: 'API Keys', to: '/settings/api-keys', icon: '🔑', indent: true },
  { label: 'Security', to: '/settings/security', icon: '🔒', indent: true },
  { label: 'Billing', to: '/settings/billing', icon: '💳', indent: true },
]

function SidebarLink({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      style={{ textDecoration: 'none' }}
    >
      {({ isActive }) => (
        <div
          style={{
            height: 38,
            padding: `8px ${item.indent ? '11px' : '11px'}`,
            paddingLeft: item.indent ? 32 : isActive ? 12 : 11,
            borderRadius: isActive ? '0 6px 6px 0' : 6,
            marginBottom: 2,
            marginLeft: isActive ? -1 : 0,
            borderLeft: isActive ? '2px solid #63d9ff' : 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            fontSize: 13,
            fontWeight: isActive ? 600 : 400,
            color: isActive ? '#63d9ff' : 'rgba(232,232,240,0.45)',
            background: isActive ? 'rgba(99,217,255,0.10)' : 'transparent',
            cursor: 'pointer',
            transition: 'color 150ms, background 150ms',
          }}
          onMouseEnter={(e) => {
            if (!isActive) {
              e.currentTarget.style.color = '#e8e8f0'
              e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
            }
          }}
          onMouseLeave={(e) => {
            if (!isActive) {
              e.currentTarget.style.color = 'rgba(232,232,240,0.45)'
              e.currentTarget.style.background = 'transparent'
            }
          }}
        >
          <span style={{ fontSize: 15 }}>{item.icon}</span>
          <span>{item.label}</span>
        </div>
      )}
    </NavLink>
  )
}

export default function Sidebar() {
  const user = useAuthStore((s) => s.user)
  const initials = user?.display_name
    ? user.display_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : '?'

  return (
    <aside
      style={{
        position: 'fixed',
        left: 0,
        top: 62,
        bottom: 0,
        width: 220,
        background: 'rgba(4,4,10,0.70)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        padding: '14px 10px',
        overflowY: 'auto',
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* User section */}
      <div
        style={{
          padding: '8px 10px 14px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12,
            fontWeight: 700,
            color: 'var(--void)',
            flexShrink: 0,
          }}
        >
          {initials}
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)' }}>
          {user?.display_name ?? 'User'}
        </span>
        <span className="tag tag-forge" style={{ marginLeft: 'auto' }}>
          PRO
        </span>
      </div>

      {/* Main nav */}
      <div>
        {mainItems.map((item) => (
          <SidebarLink key={item.to} item={item} />
        ))}
      </div>

      {/* Divider */}
      <div
        style={{
          height: 1,
          background: 'rgba(255,255,255,0.06)',
          margin: '8px 0',
        }}
      />

      {/* Settings label */}
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          textTransform: 'uppercase',
          letterSpacing: 1,
          color: 'rgba(232,232,240,0.20)',
          padding: '6px 11px',
        }}
      >
        SETTINGS
      </div>

      {/* Settings nav */}
      <div>
        {settingsItems.map((item) => (
          <SidebarLink key={item.to} item={item} />
        ))}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Token usage */}
      <div
        style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          paddingTop: 12,
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'rgba(232,232,240,0.30)',
          }}
        >
          TOKEN USAGE
        </div>
        <div
          style={{
            height: 3,
            background: 'rgba(255,255,255,0.07)',
            borderRadius: 2,
            marginTop: 8,
          }}
        >
          <div
            style={{
              width: '42%',
              height: '100%',
              background: '#63d9ff',
              borderRadius: 2,
            }}
          />
        </div>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'rgba(232,232,240,0.30)',
            marginTop: 4,
          }}
        >
          847k / 2M tokens
        </div>
      </div>
    </aside>
  )
}
