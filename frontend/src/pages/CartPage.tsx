import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { CartLineItem } from '../components/cart/CartLineItem'
import { Button } from '../components/common/Button'
import { EmptyState } from '../components/common/EmptyState'
import { formatBdt } from '../lib/format'
import { useCartStore } from '../store/cartStore'

export function CartPage() {
  const navigate = useNavigate()
  const cart = useCartStore((s) => s.cart)
  const loading = useCartStore((s) => s.loading)
  const updateItem = useCartStore((s) => s.updateItem)
  const removeItem = useCartStore((s) => s.removeItem)
  const [error, setError] = useState<string | null>(null)

  async function handleUpdate(itemId: number, quantity: number) {
    setError(null)
    try {
      await updateItem(itemId, quantity)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not update quantity')
    }
  }

  if (loading && !cart) {
    return <div className="mx-auto max-w-3xl px-4 py-16 text-center text-ink-muted">Loading your cart…</div>
  }

  if (!cart || cart.items.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <EmptyState
          title="Your cart's as empty as a Monday fridge"
          message="Let's fix that — browse the catalog or tell Bazar Buddy what you're cooking."
          action={
            <Link to="/products">
              <Button>Browse products</Button>
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="font-heading mb-4 text-2xl font-extrabold text-ink">Your cart</h1>

      <div className="rounded-card border border-line bg-paper px-4">
        {cart.items.map((item) => (
          <CartLineItem
            key={item.id}
            item={item}
            onUpdate={(q) => handleUpdate(item.id, q)}
            onRemove={() => removeItem(item.id)}
          />
        ))}
      </div>
      {error && <p className="mt-2 text-sm text-warning">{error}</p>}

      <div className="sticky bottom-4 mt-6 rounded-card border border-line bg-paper p-4 shadow-lg">
        <div className="flex items-center justify-between">
          <p className="text-ink-muted">
            Subtotal ({cart.item_count} item{cart.item_count === 1 ? '' : 's'})
          </p>
          <p className="font-heading text-xl font-extrabold text-ink">{formatBdt(cart.subtotal_bdt)}</p>
        </div>
        <Button variant="primary" className="mt-3 w-full" onClick={() => navigate('/checkout')}>
          Proceed to checkout
        </Button>
      </div>
    </div>
  )
}
