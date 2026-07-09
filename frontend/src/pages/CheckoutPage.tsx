import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createOrder } from '../api/orders'
import { ApiError } from '../api/client'
import { Button } from '../components/common/Button'
import { formatBdt } from '../lib/format'
import { useCartStore } from '../store/cartStore'

type PaymentMethod = 'bkash' | 'card' | 'cod'

const PAYMENT_METHODS: { id: PaymentMethod; label: string; icon: string }[] = [
  { id: 'bkash', label: 'bKash', icon: '📱' },
  { id: 'card', label: 'Card', icon: '💳' },
  { id: 'cod', label: 'Cash on delivery', icon: '💵' },
]

export function CheckoutPage() {
  const navigate = useNavigate()
  const cart = useCartStore((s) => s.cart)
  const setCart = useCartStore((s) => s.setCart)

  const [method, setMethod] = useState<PaymentMethod>('bkash')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      // Checkout creating the Order IS the entire "payment" step from the
      // backend's point of view — this sandbox payment UI is presentational
      // only, there's no real gateway call behind it (see README).
      const order = await createOrder()
      setCart({ items: [], subtotal_bdt: 0, item_count: 0 })
      navigate(`/order-confirmation/${order.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not place your order')
      setSubmitting(false)
    }
  }

  if (!cart || cart.items.length === 0) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="text-ink-muted">Your cart is empty — nothing to check out yet.</p>
        <Button className="mt-4" onClick={() => navigate('/products')}>
          Browse products
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="font-heading mb-6 text-2xl font-extrabold text-ink">Checkout</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="rounded-card border border-line bg-paper p-4">
          <h2 className="font-heading mb-3 font-bold text-ink">Delivery details</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <input required placeholder="Full name" className="rounded-button border border-line px-3 py-2 text-sm sm:col-span-2" />
            <input required placeholder="Phone number" className="rounded-button border border-line px-3 py-2 text-sm" />
            <input required placeholder="Area (e.g. Gulshan)" className="rounded-button border border-line px-3 py-2 text-sm" />
            <textarea required placeholder="Full address" rows={2} className="rounded-button border border-line px-3 py-2 text-sm sm:col-span-2" />
          </div>
        </section>

        <section className="rounded-card border border-line bg-paper p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-heading font-bold text-ink">Payment</h2>
            <span className="rounded-full bg-accent-blue-tint px-2 py-0.5 text-xs font-bold text-accent-blue">
              Sandbox Payment
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {PAYMENT_METHODS.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMethod(m.id)}
                className={`rounded-button border px-3 py-2.5 text-sm font-semibold ${
                  method === m.id ? 'border-primary bg-primary-light text-primary-dark' : 'border-line text-ink'
                }`}
              >
                <span className="mr-1" aria-hidden>{m.icon}</span>
                {m.label}
              </button>
            ))}
          </div>
          {method === 'bkash' && (
            <input placeholder="bKash number" className="mt-3 w-full rounded-button border border-line px-3 py-2 text-sm" />
          )}
          {method === 'card' && (
            <input placeholder="Card number" className="mt-3 w-full rounded-button border border-line px-3 py-2 text-sm" />
          )}
          <p className="mt-2 text-xs text-ink-muted">
            This is a sandboxed checkout for demo purposes — no real charge is made.
          </p>
        </section>

        <section className="rounded-card border border-line bg-paper p-4">
          <h2 className="font-heading mb-3 font-bold text-ink">Order summary</h2>
          {cart.items.map((item) => (
            <div key={item.id} className="flex justify-between py-1 text-sm">
              <span className="text-ink-muted">
                {item.quantity} × {item.product.name_en}
              </span>
              <span className="font-semibold text-ink">{formatBdt(item.line_total_bdt)}</span>
            </div>
          ))}
          <div className="mt-2 flex justify-between border-t border-line pt-2">
            <span className="font-heading font-bold text-ink">Total</span>
            <span className="font-heading font-bold text-ink">{formatBdt(cart.subtotal_bdt)}</span>
          </div>
        </section>

        {error && <p className="text-sm text-warning">{error}</p>}

        <Button type="submit" variant="primary" disabled={submitting} className="w-full !py-3 !text-base">
          {submitting ? 'Placing order…' : `Place order — ${formatBdt(cart.subtotal_bdt)}`}
        </Button>
      </form>
    </div>
  )
}
