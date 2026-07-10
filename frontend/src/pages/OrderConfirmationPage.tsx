import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { getOrder } from '../api/orders'
import { initSslcommerzPayment } from '../api/payment'
import { ApiError } from '../api/client'
import { StatusTimeline } from '../components/order/StatusTimeline'
import { Button } from '../components/common/Button'
import { formatBdt } from '../lib/format'
import type { Order } from '../types/api'

// Set by routers/payment.py's success/fail/cancel redirects after the
// customer returns from SSLCommerz's hosted checkout page.
type PaymentQueryStatus = 'success' | 'failed' | 'cancelled' | null

export function OrderConfirmationPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const paymentStatus = params.get('payment') as PaymentQueryStatus
  const [order, setOrder] = useState<Order | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)

  useEffect(() => {
    if (id) getOrder(Number(id)).then(setOrder).catch(() => setOrder(null))
  }, [id])

  if (!order) {
    return <div className="mx-auto max-w-lg px-4 py-16 text-center text-ink-muted">Loading your order…</div>
  }

  async function retryPayment() {
    setRetrying(true)
    setRetryError(null)
    try {
      const { gateway_url } = await initSslcommerzPayment(Number(id))
      window.location.href = gateway_url
    } catch (err) {
      setRetryError(err instanceof ApiError ? err.detail : 'Could not start payment')
      setRetrying(false)
    }
  }

  const paymentDidNotComplete = paymentStatus === 'failed' || paymentStatus === 'cancelled'

  return (
    <div className="mx-auto max-w-lg px-4 py-16 text-center">
      {paymentDidNotComplete ? (
        <>
          <p className="text-4xl" aria-hidden>⚠️</p>
          <h1 className="font-heading mt-3 text-2xl font-extrabold text-ink">
            {paymentStatus === 'cancelled' ? 'Payment cancelled' : 'Payment failed'}
          </h1>
          <p className="font-dense mt-1 text-ink-muted">
            Order #{order.id} is saved as pending — no payment went through. You can retry below.
          </p>
        </>
      ) : (
        <>
          <p className="text-4xl" aria-hidden>🎉</p>
          <h1 className="font-heading mt-3 text-2xl font-extrabold text-ink">Order placed!</h1>
          <p className="mt-1 text-ink-muted">Order #{order.id} — {formatBdt(order.total_bdt)}</p>
        </>
      )}

      <div className="mt-8 rounded-card border border-line bg-paper p-5">
        <StatusTimeline status={order.status} />
      </div>

      {paymentDidNotComplete && order.status === 'pending' ? (
        <div className="mt-6">
          {retryError && <p className="font-dense mb-2 text-sm text-warning">{retryError}</p>}
          <Button onClick={retryPayment} disabled={retrying} variant="primary">
            {retrying ? 'Redirecting…' : `Retry payment — ${formatBdt(order.total_bdt)}`}
          </Button>
        </div>
      ) : (
        <div className="mt-6 flex justify-center gap-3">
          <Link to="/orders">
            <Button variant="secondary">View order history</Button>
          </Link>
          <Link to="/products">
            <Button>Keep shopping</Button>
          </Link>
        </div>
      )}
    </div>
  )
}
