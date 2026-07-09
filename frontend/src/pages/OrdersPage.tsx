import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listOrders } from '../api/orders'
import { Badge } from '../components/common/Badge'
import { EmptyState } from '../components/common/EmptyState'
import { formatBdt } from '../lib/format'
import type { Order, OrderStatus } from '../types/api'

const STATUS_TONE: Record<OrderStatus, 'primary' | 'blue' | 'muted'> = {
  pending: 'muted',
  confirmed: 'blue',
  delivered: 'primary',
}

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null)

  useEffect(() => {
    listOrders()
      .then((res) => setOrders(res.items))
      .catch(() => setOrders([]))
  }, [])

  if (orders === null) {
    return <div className="mx-auto max-w-3xl px-4 py-16 text-center text-ink-muted">Loading orders…</div>
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="font-heading mb-6 text-2xl font-extrabold text-ink">Your orders</h1>

      {orders.length === 0 ? (
        <EmptyState title="No orders yet" message="Once you check out, your order history shows up here." />
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <Link
              key={order.id}
              to={`/orders/${order.id}`}
              className="flex items-center justify-between rounded-card border border-line bg-paper p-4 hover:border-primary"
            >
              <div>
                <p className="font-heading font-bold text-ink">Order #{order.id}</p>
                <p className="text-sm text-ink-muted">{new Date(order.created_at).toLocaleDateString()}</p>
              </div>
              <div className="text-right">
                <p className="font-heading font-bold text-ink">{formatBdt(order.total_bdt)}</p>
                <Badge tone={STATUS_TONE[order.status]}>{order.status}</Badge>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
