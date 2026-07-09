import { Link } from 'react-router-dom'
import { formatBdt, formatPack } from '../../lib/format'
import type { CartItem } from '../../types/api'
import { Badge } from '../common/Badge'
import { QuantityStepper } from '../product/QuantityStepper'

export function CartLineItem({
  item,
  onUpdate,
  onRemove,
}: {
  item: CartItem
  onUpdate: (quantity: number) => void
  onRemove: () => void
}) {
  const { product } = item

  return (
    <div className="flex gap-3 border-b border-line py-4 last:border-b-0">
      <Link to={`/products/${product.id}`} className="h-20 w-20 shrink-0 overflow-hidden rounded-card bg-paper-warm">
        {product.image_url ? (
          <img src={product.image_url} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-2xl">🛒</div>
        )}
      </Link>

      <div className="min-w-0 flex-1 font-dense">
        <div className="flex items-start justify-between gap-2">
          <Link to={`/products/${product.id}`} className="text-sm font-semibold text-ink">
            {product.name_en}
          </Link>
          <button type="button" onClick={onRemove} className="text-xs text-ink-muted hover:text-warning">
            Remove
          </button>
        </div>
        <p className="text-xs text-ink-muted">{formatPack(product.unit, product.unit_value)}</p>

        {item.added_via === 'assistant' && (
          <Badge tone="blue">💬 Added by Bazar Buddy</Badge>
        )}
        {item.substitution_note && (
          <p className="mt-1 text-xs italic text-ink-muted">{item.substitution_note}</p>
        )}

        <div className="mt-2 flex items-center justify-between">
          <QuantityStepper quantity={item.quantity} max={product.stock_qty} onChange={onUpdate} />
          <p className="font-bold text-ink">{formatBdt(item.line_total_bdt)}</p>
        </div>
      </div>
    </div>
  )
}
