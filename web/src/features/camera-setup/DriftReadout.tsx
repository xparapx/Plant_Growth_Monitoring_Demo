import { useDrift } from '@/api/queries'
import type { Drift } from '@/api/types'
import { KeyValue } from '@/components/ui/KeyValue'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip, type ChipState } from '@/components/ui/StatusChip'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { ss } from './strings'

const CHIP: Record<Drift['level'], ChipState> = { ok: 'ok', drift: 'amber', fail: 'bad', unreliable: 'bad', unknown: 'off' }

export function DriftReadout({ enabled }: { enabled: boolean }) {
  const q = useDrift(enabled)
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border-soft px-3 py-2.5">
      <div className="label !text-[10px]">{ko.setup.drift}</div>
      {!enabled ? (
        <div className="text-[12px] text-muted">{ss.driftOff}</div>
      ) : q.isPending ? (
        <Skeleton lines={2} />
      ) : q.data ? (
        <Body d={q.data} />
      ) : null}
    </div>
  )
}

function px(v: number | undefined, mm?: number | null) {
  if (v === undefined) return '—'
  return `${fmtNum(v, 1)} px${mm !== undefined && mm !== null ? ` (${fmtNum(mm, 2)} mm)` : ''}`
}

function Body({ d }: { d: Drift }) {
  const level = d.level ?? 'unknown'
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip label={ss.driftLevel[level] ?? level} state={CHIP[level] ?? 'off'} detail={d.cur ?? undefined} />
        {d.msg && <span className="text-[12px] text-muted">{d.msg}</span>}
      </div>
      {level !== 'unknown' && (
        <KeyValue
          cols={3}
          items={[
            { k: ss.driftDx, v: px(d.dx) },
            { k: ss.driftDy, v: px(d.dy) },
            { k: ss.driftMag, v: px(d.mag, d.mag_mm) },
            { k: ss.driftDeg, v: d.deg === undefined ? '—' : `${fmtNum(d.deg, 2)}°` },
            { k: ss.driftScale, v: d.scale === undefined ? '—' : `×${fmtNum(d.scale, 3)}` },
            { k: ss.driftResp, v: d.resp === undefined ? '—' : fmtNum(d.resp, 2) },
          ]}
        />
      )}
    </>
  )
}
