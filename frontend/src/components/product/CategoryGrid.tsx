import { Link } from 'react-router-dom'
import { FEATURED_CATEGORIES } from '../../lib/categoryIcons'

export function CategoryGrid() {
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-11">
      {FEATURED_CATEGORIES.map(({ label, category, icon }) => (
        <Link
          key={label}
          to={`/products?category=${encodeURIComponent(category)}`}
          className="flex flex-col items-center gap-2 rounded-card border border-line bg-paper p-3 text-center transition-colors hover:border-primary hover:bg-primary-light"
        >
          <span className="text-3xl" aria-hidden>
            {icon}
          </span>
          <span className="font-heading text-xs font-bold text-ink">{label}</span>
        </Link>
      ))}
    </div>
  )
}
