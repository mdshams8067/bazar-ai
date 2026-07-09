import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useCartStore } from '../../store/cartStore'
import { useChatWidgetStore } from '../../store/chatWidgetStore'

export function Header() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const user = useAuthStore((s) => s.user)
  const itemCount = useCartStore((s) => s.cart?.item_count ?? 0)
  const openChat = useChatWidgetStore((s) => s.open)

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    const q = search.trim()
    navigate(q ? `/products?search=${encodeURIComponent(q)}` : '/products')
  }

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Link to="/" className="font-heading shrink-0 text-xl font-extrabold text-primary">
          Bazar AI
        </Link>

        <form onSubmit={handleSearch} className="hidden flex-1 items-center sm:flex">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search rice, fish, spices…"
            className="w-full rounded-button border border-line bg-paper-warm px-4 py-2 text-sm focus-visible:bg-paper"
          />
        </form>

        <button
          type="button"
          onClick={openChat}
          className="font-heading hidden shrink-0 items-center gap-1.5 rounded-button bg-primary-light px-3 py-2 text-sm font-bold text-primary-dark hover:bg-primary/20 md:flex"
        >
          <span aria-hidden>💬</span> Ask Bazar Buddy
        </button>

        <Link
          to="/cart"
          className="relative shrink-0 rounded-button p-2 text-ink hover:bg-paper-warm"
          aria-label={`Cart, ${itemCount} item(s)`}
        >
          <CartIcon />
          {itemCount > 0 && (
            <span className="font-heading absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-warning px-1 text-[10px] font-bold text-white">
              {itemCount}
            </span>
          )}
        </Link>

        <Link
          to={user ? '/account' : '/login'}
          className="font-heading shrink-0 text-sm font-bold text-ink hover:text-primary"
        >
          {user ? user.name.split(' ')[0] : 'Sign in'}
        </Link>
      </div>

      {/* Mobile: chat + search still need to be reachable below sm/md breakpoints */}
      <div className="flex gap-2 border-t border-line px-4 py-2 sm:hidden">
        <form onSubmit={handleSearch} className="flex-1">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search products…"
            className="w-full rounded-button border border-line bg-paper-warm px-3 py-1.5 text-sm"
          />
        </form>
        <button
          type="button"
          onClick={openChat}
          className="font-heading shrink-0 rounded-button bg-primary-light px-3 py-1.5 text-sm font-bold text-primary-dark"
        >
          💬 Ask
        </button>
      </div>
    </header>
  )
}

function CartIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path
        d="M3 4h2l2.4 12.4a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 2-1.6L21 8H6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="10" cy="21" r="1.4" fill="currentColor" />
      <circle cx="18" cy="21" r="1.4" fill="currentColor" />
    </svg>
  )
}
