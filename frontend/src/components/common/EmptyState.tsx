import type { ReactNode } from 'react'

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string
  message: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-paper px-6 py-16 text-center">
      <svg width="56" height="56" viewBox="0 0 56 56" fill="none" className="text-primary-light">
        <circle cx="28" cy="28" r="27" stroke="currentColor" strokeWidth="2" />
        <path
          d="M18 24h20l-2 16a3 3 0 0 1-3 3H23a3 3 0 0 1-3-3l-2-16Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        <path d="M22 24v-3a6 6 0 1 1 12 0v3" stroke="currentColor" strokeWidth="2" />
      </svg>
      <h3 className="font-heading text-lg font-bold text-ink">{title}</h3>
      <p className="font-body max-w-sm text-base text-ink-muted">{message}</p>
      {action}
    </div>
  )
}
