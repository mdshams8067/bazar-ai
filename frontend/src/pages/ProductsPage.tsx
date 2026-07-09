import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { listCategories, listProducts } from '../api/products'
import { EmptyState } from '../components/common/EmptyState'
import { ProductCard } from '../components/product/ProductCard'
import { CATEGORY_ICONS, DEFAULT_CATEGORY_ICON } from '../lib/categoryIcons'
import type { CategoryCount, Product, SortOption } from '../types/api'

const PAGE_SIZE = 24

export function ProductsPage() {
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? ''
  const search = params.get('search') ?? ''
  const sort = (params.get('sort') as SortOption) ?? 'relevance'
  const page = Number(params.get('page') ?? '1')

  const [searchInput, setSearchInput] = useState(search)
  const [categories, setCategories] = useState<CategoryCount[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]))
  }, [])

  useEffect(() => {
    setLoading(true)
    listProducts({ category: category || undefined, search: search || undefined, sort, page, page_size: PAGE_SIZE })
      .then((res) => {
        setProducts(res.items)
        setTotal(res.total)
      })
      .catch(() => {
        setProducts([])
        setTotal(0)
      })
      .finally(() => setLoading(false))
  }, [category, search, sort, page])

  // Debounce the search box -> URL param.
  useEffect(() => {
    const handle = setTimeout(() => {
      if (searchInput !== search) {
        setParams((prev) => {
          const next = new URLSearchParams(prev)
          if (searchInput) next.set('search', searchInput)
          else next.delete('search')
          next.delete('page')
          return next
        })
      }
    }, 350)
    return () => clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput])

  function setParam(key: string, value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      next.delete('page')
      return next
    })
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        {/* Category-first filter sidebar */}
        <aside className="space-y-1">
          <h2 className="font-heading mb-2 font-bold text-ink">Categories</h2>
          <button
            type="button"
            onClick={() => setParam('category', '')}
            className={`block w-full rounded-button px-2.5 py-1.5 text-left text-sm ${!category ? 'bg-primary-light font-bold text-primary-dark' : 'text-ink hover:bg-paper-warm'}`}
          >
            All products
          </button>
          {categories.map((c) => (
            <button
              key={c.category}
              type="button"
              onClick={() => setParam('category', c.category)}
              className={`flex w-full items-center justify-between rounded-button px-2.5 py-1.5 text-left text-sm ${category === c.category ? 'bg-primary-light font-bold text-primary-dark' : 'text-ink hover:bg-paper-warm'}`}
            >
              <span>
                {CATEGORY_ICONS[c.category] ?? DEFAULT_CATEGORY_ICON} {c.category}
              </span>
              <span className="text-xs text-ink-muted">{c.count}</span>
            </button>
          ))}
        </aside>

        <div>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search this catalog…"
              className="flex-1 rounded-button border border-line px-3 py-2 text-sm"
            />
            <select
              value={sort}
              onChange={(e) => setParam('sort', e.target.value)}
              className="rounded-button border border-line px-3 py-2 text-sm"
            >
              <option value="relevance">Relevance</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
            </select>
          </div>

          {loading ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="aspect-[3/4] animate-pulse rounded-card bg-line/50" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <EmptyState
              title="Nothing here yet"
              message="Try a different search term or category — or ask Bazar Buddy, they know the catalog better than any filter."
            />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
                {products.map((p) => (
                  <ProductCard key={p.id} product={p} />
                ))}
              </div>

              {totalPages > 1 && (
                <div className="mt-6 flex items-center justify-center gap-3">
                  <button
                    disabled={page <= 1}
                    onClick={() => setParams((prev) => new URLSearchParams({ ...Object.fromEntries(prev), page: String(page - 1) }))}
                    className="rounded-button border border-line px-3 py-1.5 text-sm disabled:opacity-30"
                  >
                    ← Prev
                  </button>
                  <span className="text-sm text-ink-muted">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setParams((prev) => new URLSearchParams({ ...Object.fromEntries(prev), page: String(page + 1) }))}
                    className="rounded-button border border-line px-3 py-1.5 text-sm disabled:opacity-30"
                  >
                    Next →
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
