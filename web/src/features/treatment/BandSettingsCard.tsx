import { useConfig } from '@/api/queries'
import type { Summary } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { trtVar } from '@/lib/treat'

/** Mockup 3b right column: "밴드 설정 (raw)" — ON/OFF raw thresholds per group, pots, and the shared centre. */
export function BandSettingsCard({ summary }: { summary: Summary }) {
  const q = useConfig()
  const raw = q.data?.config.bands.raw ?? {}
  const treats = Object.keys(raw)
  const centres = treats.map((t) => (raw[t][0] + raw[t][1]) / 2)
  const same = centres.length > 1 && centres.every((c) => Math.abs(c - centres[0]) < 1)
  return (
    <Card padded>
      <div className="card-title mb-2.5 !text-[12.5px]">{ko.bands.title}</div>
      {q.isPending && <Skeleton lines={3} />}
      {q.data && (
        <div className="flex flex-col gap-2 text-[12px] text-muted">
          {treats.map((t) => {
            const [off, on] = raw[t]            // config stores [wet(OFF), dry(ON)] raw counts
            const pots = (summary.groups[t] ?? []).map((p) => p.toUpperCase()).join(' ')
            return (
              <div key={t} className="flex gap-2">
                <span className="w-16 shrink-0" style={{ color: trtVar(t, 'ink') }}>{t}</span>
                <span className="num">{ko.bands.onOff(on, off)}</span>
                <span className="num ml-auto text-ink">{pots || '—'}</span>
              </div>
            )
          })}
          <div className="flex gap-2 border-t border-border-soft pt-2">
            <span className="w-16 shrink-0">{ko.bands.centre}</span>
            <span className="num">{same ? `${ko.bands.centreEq(fmtNum(centres[0], 0))} 동일` : centres.map((c, i) => `${treats[i][0].toUpperCase()} ${fmtNum(c, 0)}`).join(' · ')}</span>
          </div>
        </div>
      )}
    </Card>
  )
}
