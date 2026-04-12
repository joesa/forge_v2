import { useState, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '@/stores/authStore'
import apiClient from '@/api/client'

const schema = z.object({
  display_name: z.string().min(2, 'Name required'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Minimum 8 characters'),
  terms: z.boolean().refine((v) => v, 'You must agree to the terms'),
})

type RegisterForm = z.infer<typeof schema>

function PasswordStrength({ password }: { password: string }) {
  const segments = useMemo(() => {
    const len = password.length
    if (len >= 16) return 4
    if (len >= 12) return 2
    if (len >= 8) return 1
    return 0
  }, [password])

  return (
    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i < segments ? '#63d9ff' : 'rgba(255,255,255,0.08)', transition: 'background 200ms' }} />
      ))}
    </div>
  )
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [showPassword, setShowPassword] = useState(false)
  const [serverError, setServerError] = useState('')

  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<RegisterForm>({
    resolver: zodResolver(schema),
    defaultValues: { terms: false },
  })

  const passwordValue = watch('password', '')

  const onSubmit = async (data: RegisterForm) => {
    setServerError('')
    try {
      const res = await apiClient.post('/auth/register', {
        email: data.email,
        password: data.password,
        display_name: data.display_name,
      })
      login(res.data.user, res.data.access_token, res.data.refresh_token)
      navigate('/onboarding')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setServerError(msg ?? 'Registration failed')
    }
  }

  return (
    <div className="grid-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
      <div style={{ position: 'absolute', top: '10%', right: '20%', width: 500, height: 500, borderRadius: '50%', background: 'rgba(176,107,255,0.03)', filter: 'blur(130px)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', bottom: '10%', left: '20%', width: 400, height: 400, borderRadius: '50%', background: 'rgba(99,217,255,0.03)', filter: 'blur(130px)', pointerEvents: 'none' }} />

      <nav style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100, height: 62, padding: '0 28px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
        </Link>
      </nav>

      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 42, maxWidth: 480, width: '100%', position: 'relative', zIndex: 1, animation: 'fade-in 280ms ease' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          </div>
          <div style={{ fontWeight: 800, fontSize: 22, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', marginTop: 16, marginBottom: 5 }}>Create your account</h1>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', margin: 0 }}>Start building production apps with AI</p>
        </div>

        {serverError && (
          <div style={{ background: 'var(--ember-dim)', border: '1px solid rgba(255,107,53,0.22)', borderRadius: 8, padding: '10px 14px', marginBottom: 13, fontSize: 12, color: 'var(--ember)' }}>{serverError}</div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
          <div>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Display Name</label>
            <input {...register('display_name')} className="input" style={{ width: '100%', boxSizing: 'border-box', borderColor: errors.display_name ? 'var(--ember)' : undefined }} placeholder="Jane Smith" />
            {errors.display_name && <span style={{ fontSize: 11, color: 'var(--ember)', marginTop: 4, display: 'block' }}>{errors.display_name.message}</span>}
          </div>

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
            <PasswordStrength password={passwordValue} />
            {errors.password && <span style={{ fontSize: 11, color: 'var(--ember)', marginTop: 4, display: 'block' }}>{errors.password.message}</span>}
          </div>

          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: 11, color: 'rgba(232,232,240,0.45)', cursor: 'pointer' }}>
            <input {...register('terms')} type="checkbox" style={{ accentColor: '#63d9ff', marginTop: 2 }} />
            I agree to the Terms of Service and Privacy Policy
          </label>
          {errors.terms && <span style={{ fontSize: 11, color: 'var(--ember)' }}>{errors.terms.message}</span>}

          <button type="submit" className="btn btn-primary" style={{ width: '100%', height: 48, marginTop: 4 }} disabled={isSubmitting}>
            {isSubmitting ? 'Creating account…' : 'Create Account →'}
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '18px 0' }}>
          <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
          <span style={{ fontSize: 11, color: 'rgba(232,232,240,0.25)' }}>or continue with</span>
          <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.06)' }} />
        </div>

        <div style={{ display: 'flex', gap: 9 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }}>🐙 GitHub</button>
          <button className="btn btn-ghost" style={{ flex: 1 }}>G Google</button>
        </div>

        <div style={{ textAlign: 'center', marginTop: 18, fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: '#63d9ff', textDecoration: 'none' }}>Sign in →</Link>
        </div>
      </div>
    </div>
  )
}
