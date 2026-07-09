import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { advanceOrderStatus, getOrder, NEXT_ORDER_STATUS } from '../api/orders'
import { Button } from '../components/common/Button'
import { StatusTimeline } from '../components/order/StatusTimeline'
import { formatBdt } from '../lib/format'
import type { Order } from '../types/api'

export function OrderDetailPage() {
  const { id } = useParams()
  const [order, setOrder] = useState<Order | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [advancing, setAdvancing] = useState(false)

  useEffect(() => {
    if (!id) return
    getOrder(Number(id))
      .then(setOrder)
      .catch(() => setNotFound(true))
  }, [id])

  async function handleAdvance() {
    if (!order) return
    const next = NEXT_ORDER_STATUS[order.status]
    if (!next) return
    setAdvancing(true)
    try {
      setOrder(await advanceOrderStatus(order.id, next))
    } finally {
      setAdvancing(false)
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <p className="font-heading text-xl font-bold">Order not found</p>
        <Link to="/orders" className="mt-2 inline-block text-primary">
          Back to your orders
        </Link>
      </div>
    )
  }

  if (!order) {
    return <div className="mx-auto max-w-2xl px-4 py-16 text-center text-ink-muted">Loading order…</div>
  }

  const next = NEXT_ORDER_STATUS[order.status]

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <Link to="/orders" className="text-sm font-semibold text-primary">
        ← Back to orders
      </Link>
      <h1 className="font-heading mt-2 text-2xl font-extrabold text-ink">Order #{order.id}</h1>
      <p className="text-sm text-ink-muted">Placed {new Date(order.created_at).toLocaleString()}</p>

      <div className="mt-6 rounded-card border border-line bg-paper p-5">
        <StatusTimeline status={order.status} />
        {next && (
          <div className="mt-4 text-center">
            <Button variant="secondary" onClick={handleAdvance} disabled={advancing}>
              {advancing ? 'Updating…' : `Simulate: mark as ${next}`}
            </Button>
            <p className="mt-1 text-xs text-ink-muted">Demo control — not wired to a real courier.</p>
          </div>
        )}
      </div>

      <div className="mt-6 rounded-card border border-line bg-paper p-4">
        <h2 className="font-heading mb-3 font-bold text-ink">Items</h2>
        {order.items.map((item) => (
          <div key={item.id} className="flex justify-between border-b border-line py-2 text-sm last:border-b-0">
            <span className="text-ink">
              {item.quantity} × {item.product_name_snapshot}
            </span>
            <span className="font-semibold text-ink">{formatBdt(item.unit_price_bdt * item.quantity)}</span>
          </div>
        ))}
        <div className="mt-2 flex justify-between pt-2">
          <span className="font-heading font-bold text-ink">Total</span>
          <span className="font-heading font-bold text-ink">{formatBdt(order.total_bdt)}</span>
        </div>
      </div>
    </div>
  )
}
