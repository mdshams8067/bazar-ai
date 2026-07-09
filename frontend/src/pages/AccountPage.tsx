import { useNavigate } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { Button } from '../components/common/Button'
import { useAuthStore } from '../store/authStore'

export function AccountPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  if (!user) return null

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <h1 className="font-heading mb-6 text-2xl font-extrabold text-ink">Your account</h1>
      <div className="rounded-card border border-line bg-paper p-5">
        <p className="font-heading font-bold text-ink">{user.name}</p>
        <p className="text-sm text-ink-muted">{user.email}</p>
        {user.phone && <p className="text-sm text-ink-muted">{user.phone}</p>}
      </div>

      <Link to="/orders" className="mt-4 block rounded-card border border-line bg-paper p-4 hover:border-primary">
        <p className="font-heading font-bold text-ink">Order history</p>
        <p className="text-sm text-ink-muted">View past orders and delivery status.</p>
      </Link>

      <Button
        variant="secondary"
        className="mt-6 w-full"
        onClick={() => {
          logout()
          navigate('/')
        }}
      >
        Sign out
      </Button>
    </div>
  )
}
