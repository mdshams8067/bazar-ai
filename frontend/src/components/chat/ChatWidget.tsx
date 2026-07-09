import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { sendChatMessage, type ChatHistoryTurn } from '../../api/chat'
import { ApiError } from '../../api/client'
import { useAuthStore } from '../../store/authStore'
import { useCartStore } from '../../store/cartStore'
import { useChatWidgetStore } from '../../store/chatWidgetStore'
import type { ChatIntent } from '../../types/api'
import type { ChatMessageEntry } from '../../types/chat'
import { ChatMessage } from './ChatMessage'
import { TypingIndicator } from './TypingIndicator'

const WELCOME: ChatMessageEntry = {
  id: 'welcome',
  role: 'assistant',
  text: "Hi, I'm Bazar Buddy! Tell me what you're cooking — \"morog polao for 6\" or \"biryani under 1500 taka\" — and I'll fill your cart with what's in stock.",
}

const SERVING_SUGGESTIONS = [2, 4, 6, 8]

// A bounded window of recent turns, not the whole session — keeps the
// per-message token cost flat regardless of how long a chat runs. The
// welcome message and any client-side error bubbles are excluded: they're
// not something Bazar Buddy actually said, so replaying them as its own
// history would be confusing rather than helpful.
const MAX_HISTORY_MESSAGES = 6

function toHistory(messages: ChatMessageEntry[]): ChatHistoryTurn[] {
  return messages
    .filter((m) => m.id !== WELCOME.id && !m.isError)
    .slice(-MAX_HISTORY_MESSAGES)
    .map((m) => ({
      // The question is rendered as its own UI element (see ChatMessage),
      // but the LLM still needs it folded back in to remember it asked.
      role: m.role,
      text: m.followupQuestion ? `${m.text} ${m.followupQuestion}` : m.text,
    }))
}

function suggestsServings(intent: ChatIntent): boolean {
  return intent === 'cook_dish' || intent === 'budget_dish'
}

export function ChatWidget() {
  const isOpen = useChatWidgetStore((s) => s.isOpen)
  const close = useChatWidgetStore((s) => s.close)
  const user = useAuthStore((s) => s.user)
  const setCart = useCartStore((s) => s.setCart)

  const [messages, setMessages] = useState<ChatMessageEntry[]>([WELCOME])
  const [lastIntent, setLastIntent] = useState<ChatIntent | null>(null)
  const [lastServingUnit, setLastServingUnit] = useState('people')
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isSending])

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isSending) return

    // Captured from state BEFORE appending the new message — this is the
    // conversation up to but not including what we're about to send.
    const history = toHistory(messages)

    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text: trimmed }])
    setInput('')
    setIsSending(true)

    try {
      const res = await sendChatMessage(trimmed, history)
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: res.reply,
          matches: res.matches,
          followupQuestion: res.followup_question,
        },
      ])
      setLastIntent(res.intent)
      setLastServingUnit(res.serving_unit || 'people')
      // The backend already merges matched products into the real cart on
      // every message — this IS the post-merge cart, not a preview, so
      // there's no separate "confirm/add all" step to build here.
      setCart(res.cart)
    } catch (err) {
      const text =
        err instanceof ApiError
          ? err.detail
          : "Something went wrong reaching Bazar Buddy — check your connection and try again."
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'assistant', text, isError: true },
      ])
    } finally {
      setIsSending(false)
    }
  }

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-4 right-4 z-50 flex h-[min(640px,calc(100vh-2rem))] w-[min(400px,calc(100vw-2rem))] flex-col overflow-hidden rounded-card border border-line bg-paper shadow-xl"
          >
            <div className="flex items-center justify-between bg-primary px-4 py-3 text-white">
              <p className="font-heading font-extrabold">Bazar Buddy</p>
              <button
                type="button"
                onClick={close}
                aria-label="Close chat"
                className="rounded-button p-1 hover:bg-white/10"
              >
                ✕
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3">
              {messages.map((m) => (
                <ChatMessage key={m.id} message={m} />
              ))}
              {isSending && <TypingIndicator />}

              {lastIntent && suggestsServings(lastIntent) && !isSending && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1 font-dense">
                  <span className="text-xs text-ink-muted">Scale to:</span>
                  {SERVING_SUGGESTIONS.map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => send(`make it enough for ${n} ${lastServingUnit}`)}
                      className="rounded-button border border-line px-2 py-0.5 text-xs font-semibold text-ink hover:border-primary hover:text-primary"
                    >
                      {n} {lastServingUnit}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {user ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  send(input)
                }}
                className="flex gap-2 border-t border-line p-3"
              >
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="morog polao banabo… or just ask in English"
                  disabled={isSending}
                  className="flex-1 rounded-button border border-line px-3 py-2 text-base focus-visible:border-primary"
                />
                <button
                  type="submit"
                  disabled={isSending || !input.trim()}
                  className="font-heading rounded-button bg-primary px-3 py-2 text-sm font-bold text-white disabled:opacity-40"
                >
                  Send
                </button>
              </form>
            ) : (
              <div className="border-t border-line p-3 text-center text-base">
                <p className="text-ink-muted">Sign in to start shopping with Bazar Buddy.</p>
                <Link
                  to="/login?redirect=/"
                  onClick={close}
                  className="font-heading mt-2 inline-block rounded-button bg-primary px-4 py-2 font-bold text-white"
                >
                  Sign in
                </Link>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {!isOpen && (
        <button
          type="button"
          onClick={() => useChatWidgetStore.getState().open()}
          aria-label="Open Bazar Buddy chat"
          className="fixed bottom-4 right-4 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-2xl text-white shadow-xl transition-transform hover:scale-105"
        >
          💬
        </button>
      )}
    </>
  )
}
