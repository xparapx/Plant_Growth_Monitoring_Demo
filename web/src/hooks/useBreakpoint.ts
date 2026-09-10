import { useEffect, useState } from 'react'

export type Bp = 'sm' | 'md' | 'xl'

function current(): Bp {
  if (typeof window === 'undefined') return 'xl'
  if (window.matchMedia('(min-width: 1280px)').matches) return 'xl'
  if (window.matchMedia('(min-width: 768px)').matches) return 'md'
  return 'sm'
}

export function useBreakpoint(): Bp {
  const [bp, setBp] = useState<Bp>(current)
  useEffect(() => {
    const qs = [window.matchMedia('(min-width: 1280px)'), window.matchMedia('(min-width: 768px)')]
    const h = () => setBp(current())
    qs.forEach((q) => q.addEventListener('change', h))
    return () => qs.forEach((q) => q.removeEventListener('change', h))
  }, [])
  return bp
}

export const useIsMobile = () => useBreakpoint() === 'sm'
