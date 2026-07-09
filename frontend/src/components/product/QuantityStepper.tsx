export function QuantityStepper({
  quantity,
  max,
  onChange,
  disabled,
}: {
  quantity: number
  max: number
  onChange: (quantity: number) => void
  disabled?: boolean
}) {
  return (
    <div className="flex items-center rounded-button border border-line">
      <button
        type="button"
        disabled={disabled || quantity <= 1}
        onClick={() => onChange(quantity - 1)}
        className="px-2.5 py-1 text-ink disabled:opacity-30"
        aria-label="Decrease quantity"
      >
        −
      </button>
      <span className="font-heading min-w-6 text-center text-sm font-bold">{quantity}</span>
      <button
        type="button"
        disabled={disabled || quantity >= max}
        onClick={() => onChange(quantity + 1)}
        className="px-2.5 py-1 text-ink disabled:opacity-30"
        aria-label="Increase quantity"
      >
        +
      </button>
    </div>
  )
}
