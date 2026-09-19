import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import { MOCK, assetUrl } from '@/api/client'
import { ko } from '@/i18n/ko'
import { eventToPreview } from '@/lib/geometry'
import { MOCK_PREVIEW_SRC } from '@/mock/preview'
import { useSetup } from './setupCtx'
import { ModeHint, PausedOverlay, PointsLayer, RoiLayer, SafeFrame, StageStatusBar } from './StageOverlays'
import { ss } from './strings'

const MOVE_PX = 6

/** Live MJPEG preview with the interactive SVG overlay (the only pointer target). */
export function PreviewStage({ cm, className = '' }: { cm: number; className?: string }) {
  const { status, mode, run, disabled } = useSetup()
  const imgRef = useRef<HTMLImageElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const downAt = useRef<{ x: number; y: number } | null>(null)
  const [mountTs] = useState(() => Date.now())
  const [fallback, setFallback] = useState(false)
  const live = status.preview === 'live'
  const [w, h] = status.preview_size

  // rot 를 쿼리에 넣어 회전이 바뀌면 스트림을 재연결한다 — MJPEG <img> 는 첫 프레임
  // 크기로 래스터가 고정되므로, 기존 연결로는 회전된 프레임이 눌려 보인다.
  const rot = status.capture.rotation ?? 0
  const streamSrc = MOCK
    ? MOCK_PREVIEW_SRC
    : live
      ? assetUrl(fallback ? `/api/camera/frame.jpg?t=${mountTs}&r=${rot}` : `/api/camera/stream.mjpg?overlay=0&t=${mountTs}&r=${rot}`)
      : undefined

  // Stop the MJPEG socket when paused and on unmount.
  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    img.src = streamSrc ?? ''
    return () => { img.src = '' }
  }, [streamSrc])
  useEffect(() => { if (live) setFallback(false) }, [live])

  const onDown = (e: RPointerEvent<SVGSVGElement>) => { downAt.current = { x: e.clientX, y: e.clientY } }
  const onUp = (e: RPointerEvent<SVGSVGElement>) => {
    const d = downAt.current
    downAt.current = null
    if (!d || !svgRef.current || disabled) return
    if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > MOVE_PX) return
    const p = eventToPreview(e, svgRef.current, status.preview_size)
    const x = Math.round(p.x), y = Math.round(p.y)
    if (mode === 'naming') void run('pickroi', { x, y })
    else if (mode === 'measure') void run('point', { x, y, cm })
  }

  const interactive = live && mode !== 'idle' && !disabled
  return (
    <div
      className={`relative w-full overflow-hidden rounded-[16px] bg-sunken ${className}`}
      style={{ aspectRatio: `${w} / ${h}` }}
    >
      <img
        ref={imgRef}
        src={streamSrc}
        alt=""
        aria-hidden="true"
        draggable={false}
        onError={() => { if (!MOCK && !fallback) setFallback(true) }}
        className="absolute inset-0 h-full w-full object-fill"
      />
      <svg
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={ss.stageAria(status.nroi, status.ppc)}
        onPointerDown={onDown}
        onPointerUp={onUp}
        onPointerCancel={() => { downAt.current = null }}
        className={`absolute inset-0 h-full w-full touch-none ${interactive ? 'cursor-crosshair' : ''}`}
      >
        <SafeFrame w={w} h={h} />
        <RoiLayer status={status} mode={mode} />
        <PointsLayer status={status} />
      </svg>
      {MOCK && <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-dummy-bg px-2 py-0.5 text-[10px] font-bold tracking-wider text-dummy">{ss.mockLabel}</span>}
      {live && <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-accent/90 px-2.5 py-1 text-[10px] font-medium text-white">{ko.setup.live}</span>}
      <button
        type="button"
        title={ss.rotateTitle}
        disabled={disabled}
        onClick={() => void run('rotate')}
        className="absolute bottom-3 right-3 rounded-full bg-black/55 px-3 py-1.5 text-[11px] font-medium text-white backdrop-blur-sm transition hover:bg-black/75 disabled:opacity-40"
      >
        ⟳ {ss.rotate}
      </button>
      {live && <ModeHint status={status} mode={mode} />}
      <StageStatusBar status={status} />
      {!live && <PausedOverlay status={status} />}
    </div>
  )
}
