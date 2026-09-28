import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import { MOCK, assetUrl } from '@/api/client'
import { ko } from '@/i18n/ko'
import { eventToPreview } from '@/lib/geometry'
import { MOCK_PREVIEW_SRC } from '@/mock/preview'
import { useSetup } from './setupCtx'
import { ModeHint, PausedOverlay, PointsLayer, RoiLayer, SafeFrame, StageStatusBar } from './StageOverlays'
import { ss } from './strings'

const MOVE_PX = 6
/* 회전은 서버(capture.rotation + rot_aspect)가 프레임 단계에서 처리한다 — 미리보기·촬영본·ROI 가
   한 좌표계라 화면은 그대로 그리면 된다. (예전 보기 전용 회전은 2026-09-28 폐지: 카메라를 90° 눕혀
   단 상태에서 4:3 가로를 유지하려면 서버 크롭이 필요했다.) */

/** Live MJPEG preview with the interactive SVG overlay (the only pointer target). */
export function PreviewStage({ cm, camOn = true, className = '' }: { cm: number; camOn?: boolean; className?: string }) {
  const { status, mode, run, disabled } = useSetup()
  const imgRef = useRef<HTMLImageElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const downAt = useRef<{ x: number; y: number } | null>(null)
  const [mountTs] = useState(() => Date.now())
  const [fallback, setFallback] = useState(false)
  const live = status.preview === 'live'
  const lightOn = status.light?.state === 'on'
  const lightWindow = lightOn && status.light?.by === 'window'
  const [w, h] = status.preview_size
  const dw = w, dh = h                                   // 표시 좌표계 = 미리보기 좌표계

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
    const p = dp
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
          width: '100%',
          aspectRatio: `${w} / ${h}`,
          transform: 'translate(-50%, -50%)',
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
        <SafeFrame w={w} h={h} />
        <RoiLayer status={status} mode={mode} />
        <PointsLayer status={status} />
      </svg>
      {MOCK && <span className="pointer-events-none absolute left-3 top-3 rounded-full bg-dummy-bg px-2 py-0.5 text-[10px] font-bold tracking-wider text-dummy">{ss.mockLabel}</span>}
      {live && <span className="pointer-events-none absolute right-3 top-3 rounded-full bg-accent/90 px-2.5 py-1 text-[10px] font-medium text-white">{ko.setup.live}</span>}
      <div className="absolute bottom-4 right-3 flex gap-2">
        <button
          type="button"
          role="switch"
          aria-checked={lightOn}
          title={lightWindow ? ss.lightWindowTitle : ss.lightTitle}
          disabled={disabled || lightWindow}
          onClick={() => void run('light', { on: !lightOn })}
          className={`rounded-full px-4 py-2 text-[13px] font-bold shadow-lg transition disabled:opacity-40 ${
            lightOn ? 'bg-amber-400 text-black hover:bg-amber-300' : 'bg-zinc-700/90 text-white hover:bg-zinc-600'
          }`}
        >
          {lightOn ? '💡 ' : '○ '}{lightWindow ? ss.lightWindow : lightOn ? ss.lightOn : status.light ? ss.lightOff : ss.lightUnknown}
        </button>
        <button
          type="button"
          title={ss.rotateTitle}
          disabled={disabled}
          onClick={() => void run('rotate', {})}
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
