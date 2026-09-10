import type { CameraStatus } from '@/api/types'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { capToPrev } from '@/lib/geometry'
import type { Mode } from './setupCtx'
import { ss } from './strings'

const NS = { vectorEffect: 'non-scaling-stroke' } as const
const FONT = 'var(--font-num)'

export function SafeFrame({ w, h }: { w: number; h: number }) {
  return <rect x={w * 0.05} y={h * 0.05} width={w * 0.9} height={h * 0.9} fill="none" stroke="rgba(255,255,255,.55)" strokeWidth={1.5} strokeDasharray="10 8" {...NS} />
}

export function RoiLayer({ status, mode }: { status: CameraStatus; mode: Mode }) {
  const order = status.order ?? []
  return (
    <g>
      {status.rois.map((roi, i) => {
        const r = capToPrev(roi, status.scale)
        const stroke = roi.out ? 'var(--overlay-bad)' : 'var(--overlay-roi)'
        const pick = mode === 'naming' ? order.indexOf(i) : -1
        return (
          <g key={`${roi.plant_id}-${i}`}>
            <rect x={r.x} y={r.y} width={r.w} height={r.h} fill={pick >= 0 ? 'rgba(255,170,0,.22)' : 'none'} stroke={stroke} strokeWidth={2} {...NS} />
            <text x={r.x + 8} y={r.y + 26} fontSize={22} fontWeight={700} fill={stroke} fontFamily={FONT} stroke="rgba(0,0,0,.6)" strokeWidth={3} paintOrder="stroke">
              {roi.plant_id} {roi.treat}
            </text>
            {roi.out && (
              <text x={r.x + r.w / 2} y={r.y + r.h / 2} fontSize={22} fontWeight={800} textAnchor="middle" fill="var(--overlay-bad)" fontFamily={FONT} stroke="rgba(0,0,0,.6)" strokeWidth={3} paintOrder="stroke">
                {ss.outOfFrame}
              </text>
            )}
            {pick >= 0 && (
              <g>
                <circle cx={r.x + r.w - 22} cy={r.y + 22} r={18} fill="var(--overlay-roi)" />
                <text x={r.x + r.w - 22} y={r.y + 30} fontSize={22} fontWeight={800} textAnchor="middle" fill="#000" fontFamily={FONT}>{pick + 1}</text>
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
      {two && <line x1={pts[0][0]} y1={pts[0][1]} x2={pts[1][0]} y2={pts[1][1]} stroke="var(--overlay-pt)" strokeWidth={2} {...NS} />}
      {pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={7} fill="var(--overlay-pt)" stroke="#000" strokeWidth={1.5} {...NS} />)}
      {mid && (
        <text x={mid[0]} y={mid[1] - 14} fontSize={22} fontWeight={700} textAnchor="middle" fill="var(--overlay-pt)" fontFamily={FONT} stroke="rgba(0,0,0,.65)" strokeWidth={3} paintOrder="stroke">
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
    <div className="pointer-events-none absolute bottom-2 left-2 rounded-full bg-[rgba(23,48,70,.85)] px-3 py-1.5 text-[12px] font-semibold text-white shadow-1" role="status">
      {text}
    </div>
  )
}

export function StageStatusBar({ status }: { status: CameraStatus }) {
  return (
    <div className="num pointer-events-none absolute bottom-2 right-2 rounded-md bg-[rgba(23,48,70,.85)] px-2.5 py-1 text-[11.5px] text-white">
      {fmtNum(status.ppc, 1)} px/cm · ROI {status.nroi}
    </div>
  )
}

export function PausedOverlay({ status }: { status: CameraStatus }) {
  const bad = status.preview === 'unavailable'
  return (
    <div className="absolute inset-0 grid place-items-center bg-[rgba(23,48,70,.72)] p-4 text-center text-white" role="status">
      <div className="max-w-md rounded-lg bg-[rgba(15,31,46,.85)] px-5 py-4">
        <div className="text-[15px] font-bold">{bad ? ss.unavailableTitle : ss.pausedTitle}</div>
        <div className="mt-1 text-[12.5px] opacity-85">{bad ? status.error ?? ko.setup.unavailable : `${ko.setup.paused}${status.paused_for ? ` (${status.paused_for})` : ''}`}</div>
      </div>
    </div>
  )
}
