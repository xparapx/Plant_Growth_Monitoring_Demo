import { AnimatePresence, m } from 'motion/react'
import { useEffect, type ReactNode } from 'react'

export function PageTransition({ pathname, children }: { pathname: string; children: ReactNode }) {
  useEffect(() => { window.scrollTo({ top: 0 }) }, [pathname])
  return (
    <AnimatePresence mode="wait" initial={false}>
      <m.div
        key={pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.2, ease: [0.2, 0.8, 0.2, 1] }}
      >
        {children}
      </m.div>
    </AnimatePresence>
  )
}
