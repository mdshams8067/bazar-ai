import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { Button } from '../components/common/Button'
import { useAuthStore } from '../store/authStore'

export function SignupPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const signup = useAuthStore((s) => s.signup)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
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
