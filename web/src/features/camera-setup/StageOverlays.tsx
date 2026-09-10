import type { CameraStatus } from '@/api/types'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { capToPrev } from '@/lib/geometry'
import { trtVar } from '@/lib/treat'
import type { Mode } from './setupCtx'
import { ss } from './strings'

const NS = { vectorEffect: 'non-scaling-stroke' } as const
const FONT = 'var(--font-num)'

export function SafeFrame({ w, h }: { w: number; h: number }) {
  return <rect x={w * 0.05} y={h * 0.05} width={w * 0.9} height={h * 0.9} fill="none" stroke="rgba(242,242,242,.35)" strokeWidth={1} strokeDasharray="10 8" {...NS} />
}

/** ROI rectangles in treatment colours (mockup 3d): stable #7FB3D8, fluct #D84C27, selected = thicker dashed. */
export function RoiLayer({ status, mode }: { status: CameraStatus; mode: Mode }) {
  const order = status.order ?? []
  return (
    <g>
      {status.rois.map((roi, i) => {
        const r = capToPrev(roi, status.scale)
        const stroke = roi.out ? 'var(--overlay-bad)' : roi.treat === 'stable' || roi.treat === 'fluct' ? trtVar(roi.treat, 'fill') : 'var(--ink)'
        const pick = mode === 'naming' ? order.indexOf(i) : -1
        return (
          <g key={`${roi.plant_id}-${i}`}>
            <rect x={r.x} y={r.y} width={r.w} height={r.h} rx={4} fill={pick >= 0 ? 'rgba(216,76,39,.18)' : 'none'} stroke={stroke} strokeWidth={pick >= 0 ? 2.5 : 1.5} strokeDasharray={pick >= 0 ? '7 5' : undefined} {...NS} />
            <text x={r.x + 8} y={r.y + 22} fontSize={18} fontWeight={500} fill={stroke} fontFamily={FONT} stroke="rgba(18,40,57,.7)" strokeWidth={3} paintOrder="stroke">
              {roi.plant_id} · {roi.treat || '—'}
            </text>
            {roi.out && (
              <text x={r.x + r.w / 2} y={r.y + r.h / 2} fontSize={22} fontWeight={700} textAnchor="middle" fill="var(--overlay-bad)" fontFamily={FONT} stroke="rgba(18,40,57,.7)" strokeWidth={3} paintOrder="stroke">
                {ss.outOfFrame}
              </text>
            )}
            {pick >= 0 && (
              <g>
                <circle cx={r.x + r.w - 22} cy={r.y + 22} r={16} fill="var(--accent)" />
                <text x={r.x + r.w - 22} y={r.y + 29} fontSize={20} fontWeight={700} textAnchor="middle" fill="#F2F2F2" fontFamily={FONT}>{pick + 1}</text>
              </g>
            )}
          </g>
        )
      })}
    </g>
  )
}

export function PointsLayer({ status }: { status: CameraStatus }) {
  const pts = status.pts
  if (pts.length === 0) return null
  const two = pts.length >= 2
  const mid = two ? [(pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2] : null
  return (
    <g>
      {two && <line x1={pts[0][0]} y1={pts[0][1]} x2={pts[1][0]} y2={pts[1][1]} stroke="var(--accent)" strokeWidth={2} {...NS} />}
      {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={6} fill="var(--accent)" stroke="#F2F2F2" strokeWidth={1.5} {...NS} />)}
      {mid && (
        <text x={mid[0]} y={mid[1] - 14} fontSize={20} fontWeight={600} textAnchor="middle" fill="var(--accent-ink)" fontFamily={FONT} stroke="rgba(18,40,57,.7)" strokeWidth={3} paintOrder="stroke">
          {`${status.cm} cm → ${fmtNum(status.ppc, 1)} px/cm`}
        </text>
      )}
    </g>
  )
}

export function ModeHint({ status, mode }: { status: CameraStatus; mode: Mode }) {
  let text: string | null = null
  if (mode === 'naming') text = ko.setup.hint.naming((status.order ?? []).length, status.rois.length)
  else if (mode === 'measure') text = status.pts.length === 0 ? ko.setup.hint.p1 : status.pts.length === 1 ? ko.setup.hint.p2 : null
  if (!text) return null
  return (
    <div className="pointer-events-none absolute bottom-8 left-3 rounded-full bg-[rgba(18,40,57,.85)] px-3 py-1.5 text-[12px] font-medium text-[#F2F2F2]" role="status">
      {text}
    </div>
  )
}

/** Mockup 3d bottom-left caption: "LIVE 4608×2592 · AE/AF/AWB LOCKED · px/cm 21.44". */
export function StageStatusBar({ status }: { status: CameraStatus }) {
  const [cw, ch] = status.capture_size
  const locked = status.done.focus ? 'AE/AF/AWB LOCKED' : 'AE/AF/AWB AUTO'
  return (
    <div className="num pointer-events-none absolute bottom-2 left-3 text-[10px] text-[#C0C0C0]" style={{ textShadow: '0 1px 2px rgba(18,40,57,.8)' }}>
      {status.preview === 'live' ? 'LIVE' : status.preview.toUpperCase()} {cw}×{ch} · {locked} · {fmtNum(status.ppc, 2)} px/cm · ROI {status.nroi}
    </div>
  )
}

export function PausedOverlay({ status }: { status: CameraStatus }) {
  const bad = status.preview === 'unavailable'
  return (
    <div className="absolute inset-0 grid place-items-center bg-[rgba(18,40,57,.72)] p-4 text-center text-[#F2F2F2]" role="status">
      <div className="max-w-md rounded-[12px] bg-[rgba(30,58,84,.92)] px-5 py-4">
        <div className="text-[15px] font-semibold">{bad ? ss.unavailableTitle : ss.pausedTitle}</div>
        <div className="mt-1 text-[12.5px] opacity-85">{bad ? status.error ?? ko.setup.unavailable : `${ko.setup.paused}${status.paused_for ? ` (${status.paused_for})` : ''}`}</div>
      </div>
    </div>
  )
}
