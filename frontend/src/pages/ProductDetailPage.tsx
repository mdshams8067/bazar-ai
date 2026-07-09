import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getProduct, listProducts } from '../api/products'
import { ApiError } from '../api/client'
import { Badge } from '../components/common/Badge'
import { Button } from '../components/common/Button'
import { ProductCard } from '../components/product/ProductCard'
import { QuantityStepper } from '../components/product/QuantityStepper'
import { formatBdt, formatPack } from '../lib/format'
import { useAuthStore } from '../store/authStore'
import { useCartStore } from '../store/cartStore'
import type { Product } from '../types/api'

export function ProductDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const addItem = useCartStore((s) => s.addItem)

  const [product, setProduct] = useState<Product | null>(null)
  const [related, setRelated] = useState<Product[]>([])
  const [quantity, setQuantity] = useState(1)
  const [status, setStatus] = useState<'idle' | 'adding' | 'added'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!id) return
    setNotFound(false)
    getProduct(Number(id))
      .then((p) => {
        setProduct(p)
        setQuantity(1)
        return listProducts({ category: p.category, page_size: 6 })
      })
      .then((res) => setRelated(res.items.filter((p) => p.id !== Number(id))))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) setNotFound(true)
      })
  }, [id])

  async function handleAdd() {
    if (!product) return
    if (!user) {
      navigate(`/login?redirect=${encodeURIComponent(`/products/${product.id}`)}`)
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

  if (notFound) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center">
        <p className="font-heading text-xl font-bold">Product not found</p>
        <Link to="/products" className="mt-2 inline-block text-primary">
          Back to the catalog
        </Link>
      </div>
    )
  }

  if (!product) {
    return <div className="mx-auto max-w-6xl px-4 py-16 text-center text-ink-muted">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="grid gap-8 md:grid-cols-2">
        <div className="aspect-square rounded-card bg-paper-warm">
          {product.image_url ? (
            <img src={product.image_url} alt={product.name_en} className="h-full w-full rounded-card object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-6xl">🛒</div>
          )}
        </div>

        <div>
          <Link to={`/products?category=${encodeURIComponent(product.category)}`} className="text-sm font-semibold text-primary">
            {product.category}
          </Link>
          <h1 className="font-heading mt-1 text-2xl font-extrabold text-ink">{product.name_en}</h1>
          <p className="mt-1 text-ink-muted">{formatPack(product.unit, product.unit_value)} pack</p>

          <div className="mt-4 flex items-center gap-3">
            <p className="font-heading text-3xl font-extrabold text-ink">{formatBdt(product.price_bdt)}</p>
            <Badge tone={product.in_stock ? 'primary' : 'warning'}>
              {product.in_stock ? `${product.stock_qty} in stock` : 'Out of stock'}
            </Badge>
          </div>

          <div className="mt-6 flex items-center gap-3">
            <QuantityStepper
              quantity={quantity}
              max={Math.max(product.stock_qty, 1)}
              onChange={setQuantity}
              disabled={!product.in_stock}
            />
            <Button
              variant="primary"
              disabled={!product.in_stock || status === 'adding'}
              onClick={handleAdd}
              className="flex-1"
            >
              {status === 'added' ? 'Added to cart ✓' : 'Add to cart'}
            </Button>
          </div>
          {error && <p className="mt-2 text-sm text-warning">{error}</p>}
        </div>
      </div>

      {related.length > 0 && (
        <div className="mt-12">
          <h2 className="font-heading mb-4 text-xl font-extrabold text-ink">You might also need</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
