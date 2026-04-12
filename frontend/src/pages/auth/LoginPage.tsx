import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '@/stores/authStore'
import apiClient from '@/api/client'

const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
})

type LoginForm = z.infer<typeof schema>

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const login = useAuthStore((s) => s.login)
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState('')

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginForm>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: LoginForm) => {
    setServerError('')
    try {
      const res = await apiClient.post('/auth/login', data)
      login(res.data.user, res.data.access_token, res.data.refresh_token)
      const redirect = searchParams.get('redirect') ?? '/dashboard'
      navigate(redirect)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setServerError(msg ?? 'Login failed')
    }
  }

  return (
    <div className="grid-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
      {/* Glow orbs */}
      <div style={{ position: 'absolute', top: '10%', right: '20%', width: 500, height: 500, borderRadius: '50%', background: 'rgba(176,107,255,0.03)', filter: 'blur(130px)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: '10%', left: '20%', width: 400, height: 400, borderRadius: '50%', background: 'rgba(99,217,255,0.03)', filter: 'blur(130px)', pointerEvents: 'none' }} />

      {/* Simplified nav */}
      <nav style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100, height: 62, padding: '0 28px', display: 'flex', alignItems: 'center', gap: 10, background: 'transparent' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
        </Link>
      </nav>

      {/* Auth card */}
      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 42, maxWidth: 440, width: '100%', position: 'relative', zIndex: 1, animation: 'fade-in 280ms ease' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          </div>
          <div style={{ fontWeight: 800, fontSize: 22, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', marginTop: 16, marginBottom: 5 }}>Welcome back</h1>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', margin: 0 }}>Sign in to your workspace</p>
        </div>

        {serverError && (
          <div style={{ background: 'var(--ember-dim)', border: '1px solid rgba(255,107,53,0.22)', borderRadius: 8, padding: '10px 14px', marginBottom: 13, fontSize: 12, color: 'var(--ember)' }}>{serverError}</div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
          <div>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Email Address</label>
            <input {...register('email')} className="input" style={{ width: '100%', boxSizing: 'border-box', borderColor: errors.email ? 'var(--ember)' : undefined }} placeholder="you@example.com" />
            {errors.email && <span style={{ fontSize: 11, color: 'var(--ember)', marginTop: 4, display: 'block' }}>{errors.email.message}</span>}
          </div>

          <div>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Password</label>
            <div style={{ position: 'relative' }}>
              <input {...register('password')} type={showPassword ? 'text' : 'password'} className="input" style={{ width: '100%', boxSizing: 'border-box', paddingRight: 40, borderColor: errors.password ? 'var(--ember)' : undefined }} placeholder="••••••••" />
              <button type="button" onClick={() => setShowPassword(!showPassword)} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'rgba(232,232,240,0.40)', cursor: 'pointer', fontSize: 12 }}>
                {showPassword ? '🙈' : '👁'}
              </button>
            </div>
            {errors.password && <span style={{ fontSize: 11, color: 'var(--ember)', marginTop: 4, display: 'block' }}>{errors.password.message}</span>}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'rgba(232,232,240,0.45)', cursor: 'pointer' }}>
              <input type="checkbox" style={{ accentColor: '#63d9ff' }} /> Remember me
            </label>
            <Link to="/forgot-password" style={{ fontSize: 11, color: '#63d9ff', textDecoration: 'none' }}>Forgot password?</Link>
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', height: 48, marginTop: 4 }} disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign In →'}
          </button>
        </form>

        {/* Divider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '18px 0' }}>
          <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
          <span style={{ fontSize: 11, color: 'rgba(232,232,240,0.25)' }}>or continue with</span>
          <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
        </div>

        {/* OAuth buttons */}
        <div style={{ display: 'flex', gap: 9 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }}>🐙 GitHub</button>
          <button className="btn btn-ghost" style={{ flex: 1 }}>G Google</button>
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', marginTop: 18, fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
          Don&apos;t have an account?{' '}
          <Link to="/register" style={{ color: '#63d9ff', textDecoration: 'none', cursor: 'pointer' }}>Create account →</Link>
        </div>
      </div>
    </div>
  )
}
