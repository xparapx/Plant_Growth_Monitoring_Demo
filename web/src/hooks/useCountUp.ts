import { useEffect, useRef, useState } from 'react'

const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Animates from the previous value to `value` over `ms` (skips when reduced motion or first null). */
export function useCountUp(value: number | null | undefined, ms = 600): number | null {
  const [shown, setShown] = useState<number | null>(value ?? null)
  const prev = useRef<number | null>(value ?? null)
  useEffect(() => {
    if (value === null || value === undefined) { setShown(null); prev.current = null; return }
    const from = prev.current
    prev.current = value
    if (from === null || reduced() || from === value) { setShown(value); return }
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / ms)
      const e = 1 - Math.pow(1 - k, 3)
      setShown(from + (value - from) * e)
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, ms])
  return shown
}
