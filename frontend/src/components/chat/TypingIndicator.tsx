export function TypingIndicator() {
  return (
    <div className="flex w-fit items-center gap-1 rounded-card bg-paper-warm px-3 py-2.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-muted"
          style={{ animationDelay: `${i * 120}ms` }}
        />
      ))}
    </div>
  )
}
