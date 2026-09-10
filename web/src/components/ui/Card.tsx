import { m } from 'motion/react'
import type { HTMLAttributes, ReactNode } from 'react'

interface Props extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean
  animate?: boolean
  children: ReactNode
}

export const cardEnter = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }

export function Card({ padded = true, animate = true, className = '', children, ...rest }: Props) {
  const cls = `card ${padded ? 'p-4 md:p-5' : ''} ${className}`
  if (!animate) return <section className={cls} {...rest}>{children}</section>
  return (
    <m.section variants={cardEnter} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }} className={cls} {...(rest as object)}>
      {children}
    </m.section>
  )
}

/** Stagger container for a page of cards; animates only on first mount. */
export function CardGrid({ className = '', children }: { className?: string; children: ReactNode }) {
  return (
    <m.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.04 } } }} className={className}>
      {children}
    </m.div>
  )
}
