import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { formatBdt, formatPack } from '../../lib/format'
import { useAuthStore } from '../../store/authStore'
import { useCartStore } from '../../store/cartStore'
import type { Product } from '../../types/api'
import { Badge } from '../common/Badge'
import { Button } from '../common/Button'
import { QuantityStepper } from './QuantityStepper'

export function ProductCard({ product }: { product: Product }) {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const addItem = useCartStore((s) => s.addItem)
  const [quantity, setQuantity] = useState(1)
  const [status, setStatus] = useState<'idle' | 'adding' | 'added'>('idle')
  const [error, setError] = useState<string | null>(null)

  async function handleAdd() {
    if (!user) {
      navigate(`/login?redirect=${encodeURIComponent('/products')}`)
      return
    }
    setStatus('adding')
    setError(null)
    try {
      await addItem(product.id, quantity)
      setStatus('added')
      setTimeout(() => setStatus('idle'), 1500)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not add to cart')
      setStatus('idle')
    }
  }

  return (
    <div className="flex flex-col overflow-hidden rounded-card border border-line bg-paper transition-shadow hover:shadow-md">
      <Link to={`/products/${product.id}`} className="block aspect-square bg-paper-warm">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name_en}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-3xl">🛒</div>
        )}
      </Link>
      <div className="flex flex-1 flex-col gap-1.5 p-3 font-dense">
        <Link to={`/products/${product.id}`}>
          <p className="line-clamp-2 text-sm font-semibold text-ink">{product.name_en}</p>
        </Link>
        <p className="text-xs text-ink-muted">{formatPack(product.unit, product.unit_value)}</p>
        <div className="flex items-center justify-between">
          <p className="font-bold text-ink">{formatBdt(product.price_bdt)}</p>
          <Badge tone={product.in_stock ? 'primary' : 'warning'}>
            {product.in_stock ? 'In stock' : 'Out of stock'}
          </Badge>
        </div>

        <div className="mt-auto flex items-center gap-2 pt-2">
          <QuantityStepper
            quantity={quantity}
            max={Math.max(product.stock_qty, 1)}
            onChange={setQuantity}
            disabled={!product.in_stock}
          />
          <Button
            variant="primary"
            className="flex-1 !px-3 !py-1.5 text-xs"
            disabled={!product.in_stock || status === 'adding'}
            onClick={handleAdd}
          >
            {status === 'added' ? 'Added ✓' : 'Add'}
          </Button>
        </div>
        {error && <p className="text-xs text-warning">{error}</p>}
      </div>
    </div>
  )
}
