import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Button } from '../components/common/Button'
import { useAuthStore } from '../store/authStore'

export function LoginPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const login = useAuthStore((s) => s.login)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
      navigate(params.get('redirect') || '/')
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not sign in')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-5 px-4 py-16">
      <h1 className="font-heading text-2xl font-extrabold text-ink">Welcome back</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
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
        {error && <p className="text-sm text-warning">{error}</p>}
        <Button type="submit" disabled={submitting} className="mt-1">
          {submitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      <p className="text-sm text-ink-muted">
        New to Bazar AI?{' '}
        <Link
          to={`/signup?redirect=${encodeURIComponent(params.get('redirect') || '/')}`}
          className="font-semibold text-primary"
        >
          Create an account
        </Link>
      </p>
    </div>
  )
}
