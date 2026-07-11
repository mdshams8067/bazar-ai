import { useEffect, useState } from 'react'

// Bazar Buddy checks real stock and matches ingredients against the
// catalog rather than guessing, which is genuinely slower than a plain
// chat reply — plain bouncing dots for several seconds can read as
// stuck rather than working. The hint only appears after a delay so a
// fast reply still just shows the dots, never a flash of text that
// disappears a moment later.
const HINT_DELAY_MS = 2500

export function TypingIndicator() {
  const [showHint, setShowHint] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setShowHint(true), HINT_DELAY_MS)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex w-fit flex-col gap-1.5 rounded-card bg-paper-warm px-3 py-2.5">
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-muted"
            style={{ animationDelay: `${i * 120}ms` }}
          />
        ))}
      </div>
      {showHint && (
        <p className="text-xs text-ink-muted">
          Checking real stock and finding the best match — this can take a few seconds…
        </p>
      )}
    </div>
  )
}
