import { useState } from 'react'
import { ApiError } from '../../api/client'
import { formatBdt, formatPack } from '../../lib/format'
import { useCartStore } from '../../store/cartStore'
import type { IngredientMatch } from '../../types/api'
import { Badge } from '../common/Badge'

const STATUS_TAG: Record<
  IngredientMatch['status'],
  { label: string; tone: 'primary' | 'blue' | 'warning' | 'muted'; icon: string }
> = {
  ok: { label: 'Added', tone: 'primary', icon: '✅' },
  substituted_brand: { label: 'Brand swap', tone: 'blue', icon: '🔁' },
  substituted_functional: { label: 'Substitute', tone: 'warning', icon: '⚠️' },
  substituted_diy: { label: 'DIY substitute', tone: 'blue', icon: '🧪' },
  skipped_optional: { label: 'Skipped (optional)', tone: 'muted', icon: '➖' },
  unavailable_essential: { label: "Couldn't fulfil", tone: 'warning', icon: '⚠️' },
  unmatched: { label: 'Not found', tone: 'muted', icon: '➖' },
  error: { label: 'Error', tone: 'muted', icon: '➖' },
  needs_clarification: { label: 'Pick a size', tone: 'blue', icon: '❓' },
}

export function MatchCard({ match }: { match: IngredientMatch }) {
  if (match.status === 'needs_clarification' && match.candidates?.length) {
    return <PackSizePicker match={match} />
  }

  if (match.status === 'substituted_diy' && match.components?.length) {
    return <DiySubstituteCard match={match} />
  }

  const tag = STATUS_TAG[match.status]
  const { product } = match

  return (
    <div className="flex items-center gap-3 rounded-card border border-line bg-paper p-2.5">
      <div className="h-12 w-12 shrink-0 overflow-hidden rounded-card bg-paper-warm">
        {product?.image_url && (
          <img src={product.image_url} alt="" className="h-full w-full object-cover" loading="lazy" />
        )}
      </div>
      <div className="min-w-0 flex-1 font-dense">
        <p className="truncate text-sm font-semibold text-ink">{product?.name_en ?? 'Not in catalog'}</p>
        <div className="mt-0.5 flex items-center gap-2">
          <Badge tone={tag.tone}>
            {tag.icon} {tag.label}
          </Badge>
          {product && (
            <span className="text-xs text-ink-muted">
              {formatPack(product.unit, product.unit_value)} · {formatBdt(product.price_bdt)}
            </span>
          )}
        </div>
        {match.note && <p className="mt-1 text-xs leading-snug text-ink-muted">{match.note}</p>}
      </div>
    </div>
  )
}

/**
 * An essential ingredient with no direct substitute product (e.g. heavy
 * cream) — Bazar Buddy already added the real components that approximate
 * it (e.g. butter + milk) to the cart; this just shows what and why.
 */
function DiySubstituteCard({ match }: { match: IngredientMatch }) {
  const tag = STATUS_TAG.substituted_diy
  return (
    <div className="rounded-card border border-line bg-paper p-2.5 font-dense">
      <div className="flex items-center gap-2">
        <Badge tone={tag.tone}>
          {tag.icon} {tag.label}
        </Badge>
      </div>
      {match.note && <p className="mt-1.5 text-xs leading-snug text-ink-muted">{match.note}</p>}
      <div className="mt-2 space-y-1.5">
        {match.components!.map((c) => (
          <div key={c.product.id} className="flex items-center gap-2">
            <div className="h-8 w-8 shrink-0 overflow-hidden rounded-button bg-paper-warm">
              {c.product.image_url && (
                <img src={c.product.image_url} alt="" className="h-full w-full object-cover" loading="lazy" />
              )}
            </div>
            <p className="min-w-0 flex-1 truncate text-xs font-semibold text-ink">{c.product.name_en}</p>
            <span className="shrink-0 text-xs text-ink-muted">
              {formatPack(c.product.unit, c.product.unit_value)} · {formatBdt(c.product.price_bdt)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * A genuinely ambiguous add-item (e.g. "add ketchup" — 250ml/500ml/1kg all
 * exist in stock) — nothing was added to the cart for this ingredient.
 * Picking a button calls the real cart API directly with that product's
 * id; no LLM round-trip needed since the frontend already has the exact
 * options from this response.
 */
function PackSizePicker({ match }: { match: IngredientMatch }) {
  const addItem = useCartStore((s) => s.addItem)
  const [addedId, setAddedId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function pick(productId: number) {
    setError(null)
    try {
      await addItem(productId, 1)
      setAddedId(productId)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Could not add that.')
    }
  }

  return (
    <div className="rounded-card border border-line bg-paper p-2.5 font-dense">
      <p className="mb-2 text-sm font-semibold text-ink">{match.note ?? 'Which size would you like?'}</p>
      <div className="flex flex-wrap gap-1.5">
        {match.candidates!.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => pick(p.id)}
            disabled={addedId !== null}
            className={`rounded-button border px-2.5 py-1.5 text-xs font-semibold disabled:opacity-50 ${
              addedId === p.id
                ? 'border-primary bg-primary-light text-primary-dark'
                : 'border-line text-ink hover:border-primary hover:text-primary'
            }`}
          >
            {addedId === p.id ? '✓ ' : ''}
            {formatPack(p.unit, p.unit_value)} · {formatBdt(p.price_bdt)}
          </button>
        ))}
      </div>
      {error && <p className="mt-1.5 text-xs text-warning">{error}</p>}
    </div>
  )
}
