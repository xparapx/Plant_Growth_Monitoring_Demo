import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'alt' | 'accent' | 'ghost' | 'ghost-accent' | 'sub'
  size?: 'sm' | 'md' | 'lg'
  busy?: boolean
  icon?: ReactNode
}

/* Mockup buttons: FIND LEAF = #2C5979/#F2F2F2 (primary), AUTO ROI = #F2F2F2/#173046 (alt),
   저장 → config.json = #D84C27 (accent), SHUFFLE = accent outline (ghost-accent). */
const V: Record<NonNullable<Props['variant']>, string> = {
  primary: 'bg-btn text-btn-ink hover:brightness-110 border-transparent',
  alt: 'bg-btn-alt text-btn-alt-ink hover:brightness-95 border-transparent',
  accent: 'bg-accent text-white hover:brightness-110 border-transparent',
  ghost: 'bg-transparent text-ink hover:bg-sunken border-border-soft',
  'ghost-accent': 'bg-accent-soft text-accent-ink hover:brightness-110 border-accent/40',
  sub: 'bg-sunken text-ink hover:brightness-110 border-transparent',
}
const S: Record<NonNullable<Props['size']>, string> = { sm: 'h-8 px-3 text-[11px] font-medium tracking-[.02em]', md: 'h-10 px-4 text-[12px]', lg: 'h-11 px-5 text-[13px]' }

export function Button({ variant = 'primary', size = 'md', busy, icon, className = '', children, disabled, ...rest }: Props) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-1.5 rounded-[9px] border font-semibold transition-[filter,background-color] duration-[var(--dur-fast)] disabled:cursor-not-allowed disabled:opacity-50 ${V[variant]} ${S[size]} ${className}`}
      {...rest}
    >
      {busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  )
}
