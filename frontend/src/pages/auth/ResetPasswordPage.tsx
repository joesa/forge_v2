import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import apiClient from '@/api/client'

const schema = z.object({
  password: z.string().min(8, 'Minimum 8 characters'),
  confirm: z.string(),
}).refine((d) => d.password === d.confirm, { message: 'Passwords must match', path: ['confirm'] })

type ResetForm = z.infer<typeof schema>

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [serverError, setServerError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<ResetForm>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: ResetForm) => {
    setServerError('')
    try {
      const token = searchParams.get('token') ?? ''
      await apiClient.post('/auth/reset-password', { token, new_password: data.password })
      navigate('/login')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setServerError(msg ?? 'Reset failed')
    }
  }

  return (
    <div className="grid-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
      <div style={{ position: 'absolute', bottom: '15%', left: '25%', width: 400, height: 400, borderRadius: '50%', background: 'rgba(99,217,255,0.03)', filter: 'blur(130px)', pointerEvents: 'none' }} />

      <nav style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100, height: 62, padding: '0 28px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          <span style={{ fontWeight: 800, fontSize: 18, letterSpacing: '-0.5px', background: 'linear-gradient(135deg, #63d9ff, #b06bff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FORGE</span>
        </Link>
      </nav>

      <div style={{ background: '#0d0d1f', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 42, maxWidth: 440, width: '100%', position: 'relative', zIndex: 1, animation: 'fade-in 280ms ease' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}>
            <div style={{ width: 26, height: 26, background: 'linear-gradient(135deg, #63d9ff, #b06bff)', clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }} />
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', marginTop: 16, marginBottom: 5 }}>Reset your password</h1>
          <p style={{ fontSize: 12, color: 'rgba(232,232,240,0.40)', margin: 0 }}>Choose a new password for your account</p>
        </div>

        {serverError && <div style={{ background: 'var(--ember-dim)', border: '1px solid rgba(255,107,53,0.22)', borderRadius: 8, padding: '10px 14px', marginBottom: 13, fontSize: 12, color: 'var(--ember)' }}>{serverError}</div>}

        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
          <div>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>New Password</label>
            <input {...register('password')} type="password" className="input" style={{ width: '100%', boxSizing: 'border-box', borderColor: errors.password ? 'var(--ember)' : undefined }} placeholder="••••••••" />
            {errors.password && <span style={{ fontSize: 11, color: 'var(--ember)', marginTop: 4, display: 'block' }}>{errors.password.message}</span>}
          </div>
          <div>
            <label style={{ display: 'block', fontFamily: "'JetBrains Mono', monospace", fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'rgba(232,232,240,0.40)', marginBottom: 6 }}>Confirm Password</label>
            <input {...register('confirm')} type="password" className="input" style={{ width: '100%', boxSizing: 'border-box', borderColor: errors.confirm ? 'var(--ember)' : undefined }} placeholder="••••••••" />
            {errors.confirm && <span style={{ fontSize: 11, color: 'var(--ember)', marginTop: 4, display: 'block' }}>{errors.confirm.message}</span>}
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', height: 48 }} disabled={isSubmitting}>
            {isSubmitting ? 'Resetting…' : 'Reset Password →'}
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 18, fontSize: 12, color: 'rgba(232,232,240,0.40)' }}>
          <Link to="/login" style={{ color: '#63d9ff', textDecoration: 'none' }}>← Back to login</Link>
        </div>
      </div>
    </div>
  )
}
