import { m } from 'motion/react'
import { useAnalytics } from '@/api/queries'
import type { Silhouettes, Summary } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { TreatPill } from '@/components/ui/TreatPill'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { trtVar } from '@/lib/treat'

export function CanopySilhouettes({ summary }: { summary: Summary }) {
  const q = useAnalytics('silhouettes')
  const groups = summary.groups
  const ncol = summary.ncol
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.canopy.title} dummy={summary.dummy.includes('growth')} />
      {q.isPending && <Skeleton className="h-40" />}
      {q.data && q.data.pots.length === 0 && <EmptyState title="Waiting for camera." hint="run_capture 가 contour 를 발행하면 여기에 실루엣이 그려집니다." compact />}
      {q.data && q.data.pots.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(groups).map(([treat, pots]) => (
            <div key={treat}>
              <div className="mb-2"><TreatPill treat={treat} /></div>
              <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${Math.min(ncol, 3)}, minmax(0, 1fr))` }}>
                {pots.map((p) => {
                  const s = q.data!.pots.find((x) => x.plant_id === p)
                  return s ? <SilhouetteCard key={p} s={s} /> : <div key={p} className="text-[12px] text-muted">{p.toUpperCase()} — {ko.canopy.notEnough}</div>
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function SilhouetteCard({ s }: { s: Silhouettes['pots'][number] }) {
  const lim = s.lim || 1
  const pts = (c: [number, number][]) => c.map(([x, y]) => `${x},${y}`).join(' ')
  const gain = s.gain_pct
  return (
    <m.div initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }} className="min-w-0">
      <div className="flex items-baseline gap-2 text-[12px]">
        <b className="num font-semibold">{s.plant_id.toUpperCase()}</b>
        <span className="num font-semibold" style={{ color: trtVar(s.treat, 'ink') }}>{gain === null ? '—' : `${gain >= 0 ? '+' : ''}${fmtNum(gain, 0)}%`}</span>
        <span className="num text-[10.5px] text-muted">{fmtNum(s.gap_d, 1)}일</span>
      </div>
      <svg viewBox={`${-lim} ${-lim} ${2 * lim} ${2 * lim}`} className="card-sub mt-1 aspect-square w-full" role="img" aria-label={`${s.plant_id} 캐노피 실루엣 어제 대비 오늘 ${gain === null ? '' : fmtNum(gain, 0) + '%'}`}>
        <polygon points={pts(s.old.contour)} fill="var(--leaf)" opacity="0.14" />
        <polygon points={pts(s.new.contour)} fill="var(--leaf)" fillOpacity="0.16" stroke="var(--leaf)" strokeWidth={lim * 0.012} strokeLinejoin="round" />
      </svg>
      <div className="num mt-1 text-[10.5px] text-muted">
        {ko.canopy.caption(s.base.area_cm2 ?? 0, s.new.area_cm2 ?? 0, s.total_pct, s.span_d)}
      </div>
    </m.div>
  )
}
