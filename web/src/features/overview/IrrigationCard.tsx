import { usePumpRecent } from '@/api/queries'
import type { PumpRecentRow, Summary } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { ResponsiveTable, type Col } from '@/components/ui/ResponsiveTable'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtNum } from '@/lib/format'
import { trtVar } from '@/lib/treat'

const COLS: Col<PumpRecentRow>[] = [
  { key: 'ago', header: 'Ago', render: (r) => (r.ago_h === null ? '—' : `${r.ago_h}h`) },
  { key: 'pot', header: 'Pot', render: (r) => <b>{r.pot}</b> },
  { key: 'trt', header: 'Trt', render: (r) => <span style={{ color: trtVar(r.treat?.toLowerCase(), 'ink') }}>{r.treat ?? '—'}</span> },
  { key: 'pump', header: 'Pump', render: (r) => (r.pump_s === null ? '—' : `${fmtNum(r.pump_s, 1)}s`), align: 'right' },
  { key: 'before', header: 'Before', render: (r) => fmtNum(r.before, 1), align: 'right' },
  { key: 'after', header: 'After', render: (r) => fmtNum(r.after, 1), align: 'right' },
  { key: 'rise', header: 'Rise', render: (r) => fmtNum(r.rise, 1, { sign: true }), align: 'right' },
  { key: 'reason', header: 'Reason', render: (r) => r.reason ?? '—' },
]

export function IrrigationCard({ summary }: { summary: Summary }) {
  const q = usePumpRecent(5)
  return (
    <Card className="xl:col-span-6">
      <SectionHeader title={ko.irrigation.title} dummy={summary.dummy.includes('pump')} />
      {q.isPending && <Skeleton lines={5} />}
      {q.data && (
        <ResponsiveTable
          columns={COLS}
          rows={q.data.rows}
          rowKey={(r) => r.ts + r.pot}
          cardTitle={(r) => `${r.pot} · ${r.ago_h ?? '—'}h ago`}
          rowTone={(r) => (r.reason === 'verify fail' || r.reason === 'no rise' ? 'bad' : undefined)}
          empty={<EmptyState title="급수 이벤트가 아직 없습니다" compact />}
        />
      )}
    </Card>
  )
}
