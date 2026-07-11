import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listProducts } from '../api/products'
import { CategoryGrid } from '../components/product/CategoryGrid'
import { ProductCard } from '../components/product/ProductCard'
import { Button } from '../components/common/Button'
import { useChatWidgetStore } from '../store/chatWidgetStore'
import type { Product } from '../types/api'

const HOW_IT_WORKS = [
  { icon: '💬', title: 'Tell Bazar Buddy', body: 'Say what you\'re cooking — English, Bangla, or Banglish.' },
  { icon: '🧾', title: 'It checks real stock', body: 'Every ingredient is matched against our live catalog, not guessed.' },
  { icon: '🔁', title: 'Honest substitutions', body: 'Out of stock? You get a real substitute, or an honest skip — never a silent guess.' },
  { icon: '🛒', title: 'Cart, filled', body: "Everything in stock lands straight in your cart, ready to check out." },
]

// A few categories sampled for the homepage "Popular picks" row — plain
// `listProducts({ in_stock_only: true })` with no filter returns products
// ordered by id ascending, and the catalog happens to seed a long run of
// near-identical oil SKUs first, so an unfiltered fetch looks repetitive
// rather than "popular." Pulling one product from several categories
// instead gives real variety without needing real trending analytics.
const SAMPLE_CATEGORIES = ['Rice', 'Meat', 'Fish', 'Spices', 'Dairy', 'Eggs', 'Snacks', 'Beverages', 'Fruits And Vegetables', 'Daal Or Lentil']

export function HomePage() {
  const openChat = useChatWidgetStore((s) => s.open)
  const [popular, setPopular] = useState<Product[]>([])

  useEffect(() => {
    Promise.all(
      SAMPLE_CATEGORIES.map((category) =>
        listProducts({ category, in_stock_only: true, page_size: 1 }).then((res) => res.items[0]),
      ),
    )
      .then((items) => setPopular(items.filter((p): p is Product => Boolean(p))))
      .catch(() => setPopular([]))
  }, [])

  return (
    <div>
      {/* Hero */}
      <section className="border-b border-line bg-primary-light">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-4 px-4 py-14 sm:py-20">
          <p className="font-heading rounded-full bg-white/60 px-3 py-1 text-xs font-bold text-primary-dark">
            AI-assisted shopping
          </p>
          <h1 className="font-heading max-w-xl text-4xl font-extrabold leading-tight text-ink sm:text-5xl">
            Tell us what you're cooking. We'll sort out the rest.
          </h1>
          <p className="font-body max-w-lg text-lg text-ink-muted">
            No more hunting through 12 categories for one recipe. Just tell us what you're making.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Button variant="primary" onClick={openChat} className="!px-6 !py-3 !text-base">
              💬 Tell Bazar Buddy what you're cooking
            </Button>
            <Link to="/products">
              <Button variant="secondary" className="!px-6 !py-3 !text-base">
                Browse the catalog
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="mx-auto max-w-6xl px-4 py-10">
        <h2 className="font-heading mb-4 text-xl font-extrabold text-ink">Shop by category</h2>
        <CategoryGrid />
      </section>

      {/* How it works */}
      <section className="bg-paper-warm py-10">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="font-heading mb-6 text-xl font-extrabold text-ink">How Bazar Buddy works</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {HOW_IT_WORKS.map((step) => (
              <div key={step.title} className="rounded-card border border-line bg-paper p-4">
                <span className="text-2xl" aria-hidden>
                  {step.icon}
                </span>
                <p className="font-heading mt-2 font-bold text-ink">{step.title}</p>
                <p className="mt-1 text-sm text-ink-muted">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Popular picks */}
      {popular.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-10">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-heading text-xl font-extrabold text-ink">Popular picks</h2>
            <Link to="/products" className="text-sm font-bold text-primary">
              See all →
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {popular.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}

      {/* Trust strip */}
      <section className="border-t border-line bg-paper py-8">
        <div className="mx-auto grid max-w-6xl gap-4 px-4 text-center sm:grid-cols-3">
          <div>
            <p className="text-2xl" aria-hidden>🚚</p>
            <p className="font-heading mt-1 font-bold">Same-day delivery</p>
            <p className="text-sm text-ink-muted">Across Dhaka, order before 6pm.</p>
          </div>
          <div>
            <p className="text-2xl" aria-hidden>📦</p>
            <p className="font-heading mt-1 font-bold">Real stock, checked live</p>
            <p className="text-sm text-ink-muted">No surprise out-of-stock at checkout.</p>
          </div>
          <div>
            <p className="text-2xl" aria-hidden>🔒</p>
            <p className="font-heading mt-1 font-bold">Secure checkout</p>
            <p className="text-sm text-ink-muted">SSLCommerz (bKash, Nagad, cards), or cash on delivery.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
