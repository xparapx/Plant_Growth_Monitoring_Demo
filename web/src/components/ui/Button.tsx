import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'accent' | 'ghost' | 'sub'
  size?: 'sm' | 'md' | 'lg'
  busy?: boolean
  icon?: ReactNode
}

const V: Record<NonNullable<Props['variant']>, string> = {
  primary: 'bg-primary text-primary-ink hover:brightness-110 border-transparent',
  accent: 'bg-accent text-white hover:brightness-110 border-transparent',
  ghost: 'bg-transparent text-ink hover:bg-sunken border-border-soft',
  sub: 'bg-sunken text-ink hover:bg-border-soft border-transparent',
}
const S: Record<NonNullable<Props['size']>, string> = { sm: 'h-8 px-2.5 text-[12px]', md: 'h-10 px-3.5 text-[13px]', lg: 'h-11 px-4 text-[14px]' }

export function Button({ variant = 'primary', size = 'md', busy, icon, className = '', children, disabled, ...rest }: Props) {
  return (
    <button
      type="button"
      disabled={disabled || busy}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md border font-semibold transition-[filter,background-color] duration-[var(--dur-fast)] disabled:cursor-not-allowed disabled:opacity-50 ${V[variant]} ${S[size]} ${className}`}
      {...rest}
    >
      {busy ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  )
}
