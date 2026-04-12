import { NavLink, Outlet } from 'react-router-dom'

const settingsNav = [
  { label: 'Profile', to: '/settings/profile', icon: '👤' },
  { label: 'AI Providers', to: '/settings/ai-providers', icon: '🤖' },
  { label: 'Model Routing', to: '/settings/model-routing', icon: '⚡' },
  { label: 'Integrations', to: '/settings/integrations', icon: '🔗' },
  { label: 'API Keys', to: '/settings/api-keys', icon: '🔑' },
  { label: 'Security', to: '/settings/security', icon: '🔒' },
  { label: 'Billing', to: '/settings/billing', icon: '💳' },
]

export default function SettingsLayout() {
  return (
    <div style={{ display: 'flex', minHeight: 'calc(100vh - 62px)' }}>
      <nav
        style={{
          width: 200,
          borderRight: '1px solid rgba(255,255,255,0.06)',
          padding: '20px 0',
          flexShrink: 0,
        }}
      >
        {settingsNav.map((item) => (
          <NavLink key={item.to} to={item.to} style={{ textDecoration: 'none' }}>
            {({ isActive }) => (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 16px',
                  fontSize: 12,
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? '#63d9ff' : 'rgba(232,232,240,0.45)',
                  background: isActive ? 'rgba(99,217,255,0.10)' : 'transparent',
                  borderLeft: isActive ? '2px solid #63d9ff' : '2px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 150ms',
                }}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </div>
            )}
          </NavLink>
        ))}
      </nav>
      <div style={{ flex: 1 }}>
        <Outlet />
      </div>
    </div>
  )
}
