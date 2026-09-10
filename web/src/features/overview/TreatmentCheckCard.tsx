import type { Summary } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { VerdictPill } from '@/components/ui/TreatPill'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'

/** Mockup 3a right column, top: "Treatment check" — Δμ 정렬 · σf/σs with verdict pills. */
export function TreatmentCheckCard({ summary }: { summary: Summary }) {
  const v = summary.validity
  return (
    <Card className="flex flex-col gap-2.5" padded>
      <div className="flex items-center gap-2">
        <span className="card-title">{ko.check.title}</span>
        {summary.dummy.includes('soil') && <DummyBadge />}
      </div>
      {!v.enough_groups ? (
        <p className="text-[11.5px] text-muted">{ko.check.needBoth}</p>
      ) : (
        <>
          <Row label={ko.check.dmu} value={`${fmtNum(v.dmu, 2)} %p`} pill={<VerdictPill ok={!!v.aligned}>{v.aligned ? ko.validity.aligned : ko.validity.drift}</VerdictPill>} />
          <Row label={ko.check.ratio} value={`${fmtNum(v.ratio, 2)} ×`} pill={<VerdictPill ok={false} tone={v.separated ? 'accent' : 'stable'}>{v.separated ? ko.validity.separated : ko.validity.tooClose}</VerdictPill>} />
        </>
      )}
    </Card>
  )
}

function Row({ label, value, pill }: { label: string; value: string; pill: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-[11.5px] text-muted">{label}</span>
      <span className="num flex items-center gap-2 text-[22px] font-semibold leading-none text-ink">
        {value}
        {pill}
      </span>
    </div>
  )
}
