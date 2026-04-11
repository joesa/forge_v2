import { Routes, Route } from 'react-router-dom'

function Home() {
  return (
    <div className="grid-bg min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-extrabold tracking-tight text-white" style={{ letterSpacing: '-1.5px' }}>
          FORGE
        </h1>
        <p className="mt-3 text-sm" style={{ color: 'var(--muted)' }}>
          AI-Native Development Platform
        </p>
        <div className="mt-6 flex gap-3 justify-center">
          <button className="btn btn-primary btn-lg">Start Building →</button>
          <button className="btn btn-ghost btn-lg">💡 Generate an Idea</button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
    </Routes>
  )
}
