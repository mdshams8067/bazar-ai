import { type FormEvent, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Button } from '../components/common/Button'
import { useAuthStore } from '../store/authStore'

// Mirrors backend/schemas/user.py's _PASSWORD_RULES exactly — client-side
// feedback is instant, but the backend is still the authoritative
// enforcer (never trust client-only validation for security).
const PASSWORD_RULES: { test: (pw: string) => boolean; label: string }[] = [
  { test: (pw) => pw.length >= 8, label: 'At least 8 characters' },
  { test: (pw) => /[A-Z]/.test(pw), label: 'An uppercase letter' },
  { test: (pw) => /[a-z]/.test(pw), label: 'A lowercase letter' },
  { test: (pw) => /\d/.test(pw), label: 'A number' },
  { test: (pw) => /[^A-Za-z0-9]/.test(pw), label: 'A symbol' },
]

export function SignupPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const signup = useAuthStore((s) => s.signup)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const failedRules = useMemo(() => PASSWORD_RULES.filter((r) => !r.test(password)), [password])
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (failedRules.length > 0) {
      setError('Password does not meet all the requirements below.')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      await signup({ name, email, password })
      navigate(params.get('redirect') || '/')
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not create your account')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-5 px-4 py-16">
      <h1 className="font-heading text-2xl font-extrabold text-ink">Create your account</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label className="text-sm font-semibold text-ink">
          Name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-button border border-line px-3 py-2"
          />
        </label>
        <label className="text-sm font-semibold text-ink">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-button border border-line px-3 py-2"
          />
        </label>
        <label className="text-sm font-semibold text-ink">
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-button border border-line px-3 py-2"
          />
        </label>
        <ul className="font-dense -mt-1.5 space-y-0.5 text-xs">
          {PASSWORD_RULES.map((rule) => {
            const met = rule.test(password)
            return (
              <li key={rule.label} className={met ? 'text-primary' : 'text-ink-muted'}>
                {met ? '✓' : '·'} {rule.label}
              </li>
            )
          })}
        </ul>
        <label className="text-sm font-semibold text-ink">
          Confirm password
          <input
            type="password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 w-full rounded-button border border-line px-3 py-2"
          />
          {!passwordsMatch && <span className="font-dense mt-1 block text-xs text-warning">Passwords don't match.</span>}
        </label>
        {error && <p className="text-sm text-warning">{error}</p>}
        <Button type="submit" disabled={submitting} className="mt-1">
          {submitting ? 'Creating account…' : 'Create account'}
        </Button>
      </form>
      <p className="text-sm text-ink-muted">
        Already have an account?{' '}
        <Link
          to={`/login?redirect=${encodeURIComponent(params.get('redirect') || '/')}`}
          className="font-semibold text-primary"
        >
          Sign in
        </Link>
      </p>
    </div>
  )
}
