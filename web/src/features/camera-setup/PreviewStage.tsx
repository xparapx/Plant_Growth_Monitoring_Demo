import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import { MOCK, assetUrl } from '@/api/client'
import { ko } from '@/i18n/ko'
import { eventToPreview } from '@/lib/geometry'
import { MOCK_PREVIEW_SRC } from '@/mock/preview'
import { useSetup } from './setupCtx'
import { ModeHint, PausedOverlay, PointsLayer, RoiLayer, SafeFrame, StageStatusBar } from './StageOverlays'
import { ss } from './strings'

const MOVE_PX = 6
const VIEWROT_KEY = 'plantlab.viewRot'

/* ── 보기 전용 회전 ──────────────────────────────────────────────
   카메라 데이터(스트림·촬영본·ROI 좌표)는 원본 그대로 두고, <화면 표시만>
   90도 단위로 돌린다 — 사진이 재인코딩·왜곡되지 않고, 회전을 바꿔도
   배율·ROI·기준사진을 다시 잡을 필요가 없다. 회전값은 이 브라우저에만
   저장된다(localStorage). 서버 쪽 capture.rotation 은 쓰지 않는다.      */
function loadViewRot(): number {
  try { const v = Number(localStorage.getItem(VIEWROT_KEY)); return [0, 90, 180, 270].includes(v) ? v : 0 } catch { return 0 }
}

/** 표시 좌표(dw×dh) -> 원본 미리보기 좌표(w×h). viewRot 는 시계방향 표시 회전. */
function displayToPreview(dx: number, dy: number, rot: number, w: number, h: number) {
  if (rot === 90) return { x: dy, y: h - dx }
  if (rot === 180) return { x: w - dx, y: h - dy }
  if (rot === 270) return { x: w - dy, y: dx }
  return { x: dx, y: dy }
}

/** 원본 좌표계로 그려진 오버레이를 표시 좌표계로 옮기는 SVG transform. */
function overlayTransform(rot: number, dw: number, dh: number) {
  if (rot === 90) return `translate(${dw} 0) rotate(90)`
  if (rot === 180) return `translate(${dw} ${dh}) rotate(180)`
  if (rot === 270) return `translate(0 ${dh}) rotate(270)`
  return undefined
}

/** Live MJPEG preview with the interactive SVG overlay (the only pointer target). */
export function PreviewStage({ cm, camOn = true, className = '' }: { cm: number; camOn?: boolean; className?: string }) {
  const { status, mode, run, disabled } = useSetup()
  const imgRef = useRef<HTMLImageElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const downAt = useRef<{ x: number; y: number } | null>(null)
  const [mountTs] = useState(() => Date.now())
  const [fallback, setFallback] = useState(false)
  const [viewRot, setViewRot] = useState(loadViewRot)
  const live = status.preview === 'live'
  const [w, h] = status.preview_size
  const swap = viewRot % 180 !== 0
  const dw = swap ? h : w, dh = swap ? w : h            // 표시 좌표계 크기

  const rotateView = () => {
    const next = (viewRot + 90) % 360
    setViewRot(next)
    try { localStorage.setItem(VIEWROT_KEY, String(next)) } catch { /* per-viewer convenience */ }
  }

  // camOn=false 면 스트림 자체를 끊는다 — 열어 달라는 요청이 다시 가면 close 가 무효가 되므로
  const streamSrc = !camOn
    ? undefined
    : MOCK
      ? MOCK_PREVIEW_SRC
      : live
        ? assetUrl(fallback ? `/api/camera/frame.jpg?t=${mountTs}` : `/api/camera/stream.mjpg?overlay=0&t=${mountTs}`)
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
    const dp = eventToPreview(e, svgRef.current, [dw, dh])
    const p = displayToPreview(dp.x, dp.y, viewRot, w, h)   // 클릭은 원본 좌표로 되돌려 보낸다
    const x = Math.round(p.x), y = Math.round(p.y)
    if (mode === 'naming') void run('pickroi', { x, y })
    else if (mode === 'measure') void run('point', { x, y, cm })
  }

  const interactive = live && mode !== 'idle' && !disabled
  return (
    <div
      className={`relative mx-auto overflow-hidden rounded-[16px] bg-sunken ${className}`}
      // 세로 보기(90/270°)에서는 화면 높이에 맞춰 폭을 줄인다 — 가로는 min() 이 100% 를 고른다.
      style={{ aspectRatio: `${dw} / ${dh}`, width: `min(100%, calc(60vh * ${(dw / dh).toFixed(4)}))` }}
    >
      {/* 이미지 래퍼 — 원본 비율 그대로 두고 CSS 로만 돌린다 (왜곡 없음) */}
      <div
        className="absolute left-1/2 top-1/2"
        style={{
          width: swap ? `${((dh / dw) * 100).toFixed(4)}%` : '100%',
          aspectRatio: `${w} / ${h}`,
          transform: `translate(-50%, -50%) rotate(${viewRot}deg)`,
        }}
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
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${dw} ${dh}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={ss.stageAria(status.nroi, status.ppc)}
        onPointerDown={onDown}
        onPointerUp={onUp}
        onPointerCancel={() => { downAt.current = null }}
        className={`absolute inset-0 h-full w-full touch-none ${interactive ? 'cursor-crosshair' : ''}`}
      >
        {/* 오버레이는 원본 좌표로 그려지고, g transform 이 표시 회전을 입힌다 */}
        <g transform={overlayTransform(viewRot, dw, dh)}>
          <SafeFrame w={w} h={h} />
          <RoiLayer status={status} mode={mode} />
          <PointsLayer status={status} />
        </g>
      </svg>
      {MOCK && <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-dummy-bg px-2 py-0.5 text-[10px] font-bold tracking-wider text-dummy">{ss.mockLabel}</span>}
      {live && <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-accent/90 px-2.5 py-1 text-[10px] font-medium text-white">{ko.setup.live}</span>}
      <div className="absolute bottom-4 right-3 flex gap-2">
        <button
          type="button"
          title={ss.lightTitle}
          disabled={disabled}
          onClick={() => void run('light', { on: true })}
          className="rounded-full bg-amber-400 px-4 py-2 text-[13px] font-bold text-black shadow-lg transition hover:bg-amber-300 disabled:opacity-40"
        >
          💡 {ss.lightOn}
        </button>
        <button
          type="button"
          title={ss.lightTitle}
          disabled={disabled}
          onClick={() => void run('light', { on: false })}
          className="rounded-full bg-white/90 px-4 py-2 text-[13px] font-bold text-black shadow-lg transition hover:bg-white disabled:opacity-40"
        >
          {ss.lightOff}
        </button>
        <button
          type="button"
          title={ss.rotateTitle}
          onClick={rotateView}
          className="rounded-full bg-accent px-4 py-2 text-[13px] font-bold text-white shadow-lg transition hover:opacity-85"
        >
          ⟳ {ss.rotate}
        </button>
      </div>
      {live && camOn && <ModeHint status={status} mode={mode} />}
      <StageStatusBar status={status} />
      {!live && <PausedOverlay status={status} />}
      {!camOn && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/60">
          <span className="rounded-full bg-black/70 px-4 py-2 text-[12.5px] font-medium text-white">{ss.camOffMsg}</span>
        </div>
      )}
    </div>
  )
}
