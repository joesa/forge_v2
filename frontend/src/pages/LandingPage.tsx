export default function LandingPage() {
  return (
    <div className="grid-bg min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1
          className="font-extrabold"
          style={{ fontSize: 'clamp(48px,6.5vw,86px)', letterSpacing: '-3px', lineHeight: 0.92, color: 'var(--text)' }}
        >
          Build anything.
        </h1>
        <p className="mt-4" style={{ fontSize: 16, color: 'var(--muted)', maxWidth: 580, lineHeight: 1.7 }}>
          Placeholder — full landing page built in Session 1.7
        </p>
        <div className="mt-8 flex gap-3 justify-center">
          <a href="/register" className="btn btn-primary btn-lg">Start Building →</a>
          <a href="/login" className="btn btn-ghost btn-lg">Log In</a>
        </div>
      </div>
    </div>
  )
}
