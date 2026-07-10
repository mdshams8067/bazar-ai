import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createOrder } from '../api/orders'
import { initSslcommerzPayment } from '../api/payment'
import { ApiError } from '../api/client'
import { Button } from '../components/common/Button'
import { formatBdt } from '../lib/format'
import { useCartStore } from '../store/cartStore'
import type { Cart } from '../types/api'

type PaymentChoice = 'sslcommerz' | 'cod'

export function CheckoutPage() {
  const navigate = useNavigate()
  const cart = useCartStore((s) => s.cart)
  const setCart = useCartStore((s) => s.setCart)

  const [method, setMethod] = useState<PaymentChoice>('sslcommerz')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Set once an SSLCommerz order exists (pending, awaiting payment) — lets
  // a failed gateway call be retried without placing a second order. COD
  // never reaches this state: it navigates straight to the confirmation
  // page once the order is created, no gateway round trip involved.
  const [pendingOrderId, setPendingOrderId] = useState<number | null>(null)
  // The cart is cleared as soon as the order is created, but the summary
  // below must keep showing what was ordered (e.g. across a retry) —
  // snapshot it at that moment instead of reading the (now-empty) live cart.
  const [orderSummary, setOrderSummary] = useState<Cart | null>(null)
  const summary = orderSummary ?? cart

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      if (pendingOrderId !== null) {
        // Retrying a payment on an already-created SSLCommerz order.
        const { gateway_url } = await initSslcommerzPayment(pendingOrderId)
        window.location.href = gateway_url
        return
      }

      if (method === 'cod') {
        const order = await createOrder('cod')
        setCart({ items: [], subtotal_bdt: 0, item_count: 0 })
        navigate(`/order-confirmation/${order.id}`)
        return
      }

      setOrderSummary(cart)
      const order = await createOrder()
      setPendingOrderId(order.id)
      setCart({ items: [], subtotal_bdt: 0, item_count: 0 })
      const { gateway_url } = await initSslcommerzPayment(order.id)
      // A real SSLCommerz-hosted page — a full browser redirect, not a
      // route in this SPA, so window.location, not react-router's navigate.
      window.location.href = gateway_url
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not place your order')
      setSubmitting(false)
    }
  }

  if (!summary || (summary.items.length === 0 && pendingOrderId === null)) {
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
            {method === 'sslcommerz' && (
              <span className="rounded-full bg-accent-blue-tint px-2 py-0.5 text-xs font-bold text-accent-blue">
                SSLCommerz Sandbox
              </span>
            )}
          </div>

          {pendingOrderId !== null ? (
            <p className="font-dense text-sm text-ink-muted">
              Payment for order #{pendingOrderId} wasn't completed yet — retry below.
            </p>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setMethod('sslcommerz')}
                  className={`rounded-button border px-3 py-2.5 text-sm font-semibold ${
                    method === 'sslcommerz' ? 'border-primary bg-primary-light text-primary-dark' : 'border-line text-ink'
                  }`}
                >
                  <span className="mr-1" aria-hidden>💳</span>
                  Pay online
                </button>
                <button
                  type="button"
                  onClick={() => setMethod('cod')}
                  className={`rounded-button border px-3 py-2.5 text-sm font-semibold ${
                    method === 'cod' ? 'border-primary bg-primary-light text-primary-dark' : 'border-line text-ink'
                  }`}
                >
                  <span className="mr-1" aria-hidden>💵</span>
                  Cash on delivery
                </button>
              </div>
              <p className="font-dense mt-2 text-sm text-ink-muted">
                {method === 'sslcommerz'
                  ? "You'll be redirected to SSLCommerz's secure checkout to pay by bKash, Nagad, card, or bank — this is a real sandbox transaction (no real money moves)."
                  : 'Pay in cash when your order arrives.'}
              </p>
            </>
          )}
        </section>

        <section className="rounded-card border border-line bg-paper p-4">
          <h2 className="font-heading mb-3 font-bold text-ink">Order summary</h2>
          {summary.items.map((item) => (
            <div key={item.id} className="flex justify-between py-1 text-sm">
              <span className="text-ink-muted">
                {item.quantity} × {item.product.name_en}
              </span>
              <span className="font-semibold text-ink">{formatBdt(item.line_total_bdt)}</span>
            </div>
          ))}
          <div className="mt-2 flex justify-between border-t border-line pt-2">
            <span className="font-heading font-bold text-ink">Total</span>
            <span className="font-heading font-bold text-ink">{formatBdt(summary.subtotal_bdt)}</span>
          </div>
        </section>

        {error && (
          <div className="font-dense text-sm text-warning">
            {error}
            {pendingOrderId !== null && <p className="mt-1 text-ink-muted">Your order is saved — retry when ready.</p>}
          </div>
        )}

        <Button type="submit" variant="primary" disabled={submitting} className="w-full !py-3 !text-base">
          {submitting
            ? method === 'cod' && pendingOrderId === null
              ? 'Placing order…'
              : 'Redirecting to payment…'
            : pendingOrderId !== null
              ? `Retry payment — ${formatBdt(summary.subtotal_bdt)}`
              : method === 'cod'
                ? `Place order (Cash on delivery) — ${formatBdt(summary.subtotal_bdt)}`
                : `Pay with SSLCommerz — ${formatBdt(summary.subtotal_bdt)}`}
        </Button>
      </form>
    </div>
  )
}
