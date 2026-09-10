import { useState } from 'react'
import { assetUrl } from '@/api/client'
import type { Job } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { KeyValue } from '@/components/ui/KeyValue'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { StatusChip } from '@/components/ui/StatusChip'
import { ko } from '@/i18n/ko'
import { fmtDateTime } from '@/lib/format'
import { jobDuration, phaseLabel, stateChip, stateLabel } from './jobUtils'
import { cs } from './strings'

export function Badge({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'muted' | 'accent'; children: string }) {
  const cls = { ok: 'bg-ok-soft text-ok-ink', warn: 'bg-warn-soft text-warn-ink', bad: 'bg-bad-soft text-bad-ink', muted: 'bg-sunken text-muted', accent: 'bg-accent-soft text-accent-ink' }[tone]
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium tracking-[.04em] ${cls}`}>{children}</span>
}

export function LastRunCard({ last }: { last: Job | null }) {
  return (
    <Card className="xl:col-span-5">
      <SectionHeader title={ko.capture.last} />
      {!last ? <EmptyState title={cs.noLast} compact /> : <Body j={last} />}
    </Card>
  )
}

function Body({ j }: { j: Job }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip label={stateLabel(j.state)} state={stateChip(j.state)} detail={phaseLabel(j.phase)} />
        {j.published ? <Badge tone="ok">{ko.capture.published}</Badge> : <Badge tone="muted">{ko.capture.notPublished}</Badge>}
        {j.fake && <Badge tone="warn">{ko.capture.fakeFrame}</Badge>}
      </div>
      <KeyValue
        cols={3}
        items={[
          { k: cs.started, v: fmtDateTime(j.started_at) },
          { k: cs.duration, v: jobDuration(j) },
          { k: cs.rows, v: `${j.ok_rows}/${j.n_rows}` },
        ]}
      />
      {j.rows.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="화분별 결과">
          {j.rows.map((r) => (
            <li key={r.plant_id} className={`num rounded-sm border px-2 py-0.5 text-[11.5px] ${r.ok ? 'border-ok/40 bg-ok-soft text-ok-ink' : 'border-bad/40 bg-bad-soft text-bad-ink'}`}>
              {r.plant_id} {r.ok ? '✓' : '✗'}
            </li>
          ))}
        </ul>
      )}
      {j.error && <div className="num rounded-md bg-bad-soft px-3 py-2 text-[12px] text-bad-ink">{j.error}</div>}
      {j.publish_error && <div className="num rounded-md bg-warn-soft px-3 py-2 text-[12px] text-warn-ink">{cs.publishError}: {j.publish_error}</div>}
      {j.img_file && <Thumb key={j.img_file} file={j.img_file} />}
    </div>
  )
}

function Thumb({ file }: { file: string }) {
  const [broken, setBroken] = useState(false)
  if (broken) return <EmptyState title={cs.imgMissing} compact />
  return (
    <a href={assetUrl(`/api/images/raw/${file}`)} target="_blank" rel="noreferrer" title={cs.openFull} className="block overflow-hidden rounded-md border border-border-soft bg-sunken">
      <img src={assetUrl(`/api/images/raw/${file}?w=480`)} alt={`촬영 이미지 ${file}`} loading="lazy" onError={() => setBroken(true)} className="aspect-[16/9] w-full object-cover" />
    </a>
  )
}
