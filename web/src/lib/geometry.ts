import type { Roi } from '@/api/types'

/** Capture-pixel ROI -> preview-pixel rect (same FOV, pure proportion). */
export function capToPrev(r: Roi, scale: number) {
  return { x: r.x * scale, y: r.y * scale, w: r.w * scale, h: r.h * scale }
}

/** Pointer event inside an element -> preview pixel coordinates (default 1280x720). */
export function eventToPreview(e: { clientX: number; clientY: number }, el: Element, size: [number, number] = [1280, 720]) {
  const r = el.getBoundingClientRect()
  return { x: ((e.clientX - r.left) * size[0]) / r.width, y: ((e.clientY - r.top) * size[1]) / r.height }
}

export function dist(a: [number, number], b: [number, number]) {
  return Math.hypot(a[0] - b[0], a[1] - b[1])
}
