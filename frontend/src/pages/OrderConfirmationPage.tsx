import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getOrder } from '../api/orders'
import { StatusTimeline } from '../components/order/StatusTimeline'
import { Button } from '../components/common/Button'
import { formatBdt } from '../lib/format'
import type { Order } from '../types/api'

export function OrderConfirmationPage() {
  const { id } = useParams()
  const [order, setOrder] = useState<Order | null>(null)

  useEffect(() => {
    if (id) getOrder(Number(id)).then(setOrder).catch(() => setOrder(null))
  }, [id])

  if (!order) {
    return <div className="mx-auto max-w-lg px-4 py-16 text-center text-ink-muted">Loading your order…</div>
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-16 text-center">
      <p className="text-4xl" aria-hidden>🎉</p>
      <h1 className="font-heading mt-3 text-2xl font-extrabold text-ink">Order placed!</h1>
      <p className="mt-1 text-ink-muted">Order #{order.id} — {formatBdt(order.total_bdt)}</p>

      <div className="mt-8 rounded-card border border-line bg-paper p-5">
        <StatusTimeline status={order.status} />
      </div>

      <div className="mt-6 flex justify-center gap-3">
        <Link to="/orders">
          <Button variant="secondary">View order history</Button>
        </Link>
        <Link to="/products">
          <Button>Keep shopping</Button>
        </Link>
      </div>
    </div>
  )
}
