import { useAuthStore } from '@/stores/authStore'

function HexLogo() {
  return (
    <div
      style={{
        width: 26,
        height: 26,
        background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
        clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
      }}
    />
  )
}

function Wordmark() {
  return (
    <span
      style={{
        fontFamily: "'Syne', sans-serif",
        fontWeight: 800,
        fontSize: 18,
        letterSpacing: '-0.5px',
        background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
      }}
    >
      FORGE
    </span>
  )
}

function UserAvatar() {
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
    <div
      style={{
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #63d9ff, #b06bff)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 11,
        fontWeight: 700,
        color: 'var(--void)',
      }}
    >
      {initials}
    </div>
  )
}

export default function TopNav() {
  return (
    <nav
      style={{
        height: 62,
        background: 'rgba(4,4,10,0.88)',
        backdropFilter: 'blur(24px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        padding: '0 28px',
        display: 'flex',
        alignItems: 'center',
        gap: 14,
      }}
    >
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <HexLogo />
        <Wordmark />
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'var(--jade)',
          }}
        >
          ● All systems normal
        </span>
        <div
          style={{
            width: 1,
            height: 24,
            background: 'rgba(255,255,255,0.06)',
          }}
        />
        <UserAvatar />
      </div>
    </nav>
  )
}
