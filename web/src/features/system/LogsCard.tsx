import { useState } from 'react'
import { useEvents, useLogs } from '@/api/queries'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Segmented } from '@/components/ui/Segmented'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtDateTime } from '@/lib/format'
import { S } from './strings'

type Unit = 'plantsvc' | 'planthub' | 'plantsnap'
const UNITS: { value: Unit; label: string }[] = [{ value: 'plantsvc', label: 'plantsvc' }, { value: 'planthub', label: 'planthub' }, { value: 'plantsnap', label: 'plantsnap' }]

export function LogsCard() {
  const [unit, setUnit] = useState<Unit>('plantsvc')
  const logs = useLogs(unit)
  const events = useEvents()
  return (
    <Card className="md:col-span-2 xl:col-span-12">
      <SectionHeader title={ko.system.logs} actions={<Segmented options={UNITS} value={unit} onChange={setUnit} size="sm" ariaLabel="journal unit" />} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <QueryState data={logs.data} isPending={logs.isPending} error={logs.error} refetch={logs.refetch} skeleton={<Skeleton className="h-64" />}>
          {(d) =>
            !d.available ? (
              <EmptyState title={S.noJournal} hint={d.error ?? undefined} />
            ) : (
              <div>
                <div className="num mb-1 text-[11px] text-muted">journalctl -u {d.unit} · {S.logs.lines(d.lines.length)}</div>
                <pre className="num max-h-[420px] overflow-auto rounded-md border border-border-soft bg-sunken p-3 text-[11.5px] leading-relaxed whitespace-pre-wrap break-all">
                  {d.lines.length ? d.lines.join('\n') : ko.common.none}
                </pre>
              </div>
            )
          }
        </QueryState>
        <div>
          <div className="label mb-2 !text-[10px]">{S.logs.events}</div>
          <QueryState data={events.data} isPending={events.isPending} error={events.error} refetch={events.refetch} skeleton={<Skeleton lines={8} />}>
            {(d) =>
              d.events.length === 0 ? (
                <EmptyState title={S.logs.noEvents} compact />
              ) : (
                <ul className="max-h-[420px] divide-y divide-border-soft overflow-auto rounded-md border border-border-soft">
                  {d.events.map((e) => (
                    <li key={e.id} className="flex flex-col gap-0.5 px-3 py-2 text-[12px]">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="num font-semibold">{e.type}</span>
                        <span className="num text-[11px] text-muted">{fmtDateTime(e.ts)}</span>
                      </div>
                      <div className="num truncate text-[11px] text-muted" title={JSON.stringify(e.data)}>{summarize(e.data)}</div>
                    </li>
                  ))}
                </ul>
              )
            }
          </QueryState>
        </div>
      </div>
    </Card>
  )
}

function summarize(d: Record<string, unknown>): string {
  if (typeof d.msg === 'string') return d.msg
  if (typeof d.error === 'string') return d.error
  return Object.entries(d).filter(([, v]) => v !== null && typeof v !== 'object').map(([k, v]) => `${k}=${String(v)}`).join(' · ')
}
