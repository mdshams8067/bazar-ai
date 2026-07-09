import type { OrderStatus } from '../../types/api'

const STEPS: { status: OrderStatus; label: string; icon: string }[] = [
  { status: 'pending', label: 'Pending', icon: '🕒' },
  { status: 'confirmed', label: 'Confirmed', icon: '✅' },
  { status: 'delivered', label: 'Delivered', icon: '📦' },
]

export function StatusTimeline({ status }: { status: OrderStatus }) {
  const currentIndex = STEPS.findIndex((s) => s.status === status)

  return (
    <div className="flex items-center">
      {STEPS.map((step, i) => (
        <div key={step.status} className="flex flex-1 items-center last:flex-none">
          <div className="flex flex-col items-center gap-1">
            <div
              className={`flex h-9 w-9 items-center justify-center rounded-full text-sm ${
                i <= currentIndex ? 'bg-primary text-white' : 'bg-line text-ink-muted'
              }`}
            >
              {step.icon}
            </div>
            <span
              className={`font-heading text-xs font-bold ${i <= currentIndex ? 'text-ink' : 'text-ink-muted'}`}
            >
              {step.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`mx-2 h-0.5 flex-1 ${i < currentIndex ? 'bg-primary' : 'bg-line'}`} />
          )}
        </div>
      ))}
    </div>
  )
}
