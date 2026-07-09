import { MatchCard } from './MatchCard'
import type { ChatMessageEntry } from '../../types/chat'

export function ChatMessage({ message }: { message: ChatMessageEntry }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[88%] rounded-card px-3 py-2.5 font-body text-base leading-relaxed ${
          isUser
            ? 'bg-primary text-white'
            : message.isError
              ? 'bg-warning-tint text-warning'
              : 'bg-paper-warm text-ink'
        }`}
      >
        <p>{message.text}</p>
        {message.matches && message.matches.length > 0 && (
          <div className="mt-2.5 space-y-2">
            {message.matches.map((m, i) => (
              <MatchCard key={i} match={m} />
            ))}
          </div>
        )}
        {message.followupQuestion && (
          <p className="font-dense mt-2.5 font-semibold">{message.followupQuestion}</p>
        )}
      </div>
    </div>
  )
}
