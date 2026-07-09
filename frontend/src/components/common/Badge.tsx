import type { ReactNode } from 'react'

type Tone = 'primary' | 'blue' | 'warning' | 'muted'

const TONE_CLASSES: Record<Tone, string> = {
  primary: 'bg-primary-light text-primary-dark',
  blue: 'bg-accent-blue-tint text-accent-blue',
  warning: 'bg-warning-tint text-warning',
  muted: 'bg-line text-ink-muted',
}

export function Badge({ tone = 'muted', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`font-heading inline-flex items-center gap-1 rounded-card px-2 py-0.5 text-xs font-bold ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  )
}
