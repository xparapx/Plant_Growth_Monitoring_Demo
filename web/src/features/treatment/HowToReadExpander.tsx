import { useMemo, type ReactNode } from 'react'
import { useAnalytics } from '@/api/queries'
import { ChartFrame } from '@/charts/ChartFrame'
import { howToReadOption } from '@/charts/options/howToRead'
import { Expander } from '@/components/ui/Expander'
import { useIsMobile } from '@/hooks/useBreakpoint'
import { ko } from '@/i18n/ko'
import { trtVar } from '@/lib/treat'
import { T } from './strings'

/**
 * Reference, never data (manual rule): default-CLOSED, both curvatures drawn symmetrically.
 * Body (and the /reference query) only mounts after the first open — Expander is lazy.
 */
export function HowToReadExpander() {
  return (
    <div className="md:col-span-2">
      <Expander summary={ko.howto.title}>
        <Body />
      </Expander>
    </div>
  )
}

function Body() {
  const mobile = useIsMobile()
  const q = useAnalytics('reference')
  const ref = q.data
  const left = useMemo(() => howToReadOption('concave', ref, mobile), [ref, mobile])
  const right = useMemo(() => howToReadOption('convex', ref, mobile), [ref, mobile])
  const h = mobile ? 180 : 210
  return (
    <div>
      <div className="grid gap-4 md:grid-cols-2">
        <Panel title={ko.howto.concave} color={trtVar('stable', 'ink')}>
          <ChartFrame option={left} height={h} ariaLabel="참고 곡선 — 오목(concave): 변동군이 손해" />
        </Panel>
        <Panel title={ko.howto.convex} color={trtVar('fluct', 'ink')}>
          <ChartFrame option={right} height={h} ariaLabel="참고 곡선 — 볼록(convex): 변동군이 이득" />
        </Panel>
      </div>
      <p className="mt-2 text-[11px] text-faint">
        {ref && ref.p05 !== null && ref.p95 !== null
          ? T.howtoChord(ref.p05, ref.p95, ref.mean)
          : T.howtoNoRef}
      </p>
      <p className="mt-2 text-[12px] text-muted">{ko.howto.caption}</p>
    </div>
  )
}

function Panel({ title, color, children }: { title: string; color: string; children: ReactNode }) {
  return (
    <div className="min-w-0 rounded-md border border-border-soft p-2">
      <div className="label mb-1 !text-[10px]" style={{ color }}>{title}</div>
      {children}
    </div>
  )
}
