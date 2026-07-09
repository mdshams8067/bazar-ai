import type { IngredientMatch } from './api'

// Local-only chat session state, used for the UI's scrollback (and to
// build the bounded history window sent with each new message — see
// ChatWidget.tsx's toHistory()).
export interface ChatMessageEntry {
  id: string
  role: 'user' | 'assistant'
  text: string
  matches?: IngredientMatch[]
  // Rendered AFTER the match cards, not inside `text` — a question up
  // front, "answered" by a wall of facts below it, reads as incoherent.
  followupQuestion?: string | null
  isError?: boolean
}
