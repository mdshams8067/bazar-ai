import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-dark disabled:bg-line disabled:text-ink-muted',
  secondary:
    'bg-transparent text-primary border border-primary hover:bg-primary-light disabled:opacity-50',
  ghost: 'bg-transparent text-ink hover:bg-paper-warm disabled:opacity-50',
}

export function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`font-heading rounded-button px-5 py-2.5 text-sm font-bold tracking-wide transition-colors duration-150 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  )
}
