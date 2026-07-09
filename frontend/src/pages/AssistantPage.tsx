import { useEffect } from 'react'
import { useChatWidgetStore } from '../store/chatWidgetStore'

// A richer, focused entry point for Bazar Buddy — the chat itself is the
// same global floating widget (one implementation, not a duplicated
// chat UI), just auto-opened against a fuller backdrop.
export function AssistantPage() {
  const open = useChatWidgetStore((s) => s.open)

  useEffect(() => {
    open()
  }, [open])

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-2xl flex-col items-center justify-center px-4 text-center">
      <p className="text-5xl" aria-hidden>💬</p>
      <h1 className="font-heading mt-4 text-3xl font-extrabold text-ink">Bazar Buddy is ready</h1>
      <p className="font-body mt-2 max-w-md text-base text-ink-muted">
        Tell it what you're cooking — a dish name, servings, even a budget — and it'll fill your
        cart from the real catalog, substitutions explained honestly.
      </p>
    </div>
  )
}
