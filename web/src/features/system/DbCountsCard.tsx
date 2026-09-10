import type { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatus } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { KeyValue } from '@/components/ui/KeyValue'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { ko } from '@/i18n/ko'
import { fmtBytes, fmtDateTime, fmtNum } from '@/lib/format'
import { S } from './strings'

const TABLES = ['readings', 'soil', 'pump_log', 'growth'] as const

export function DbCountsCard({ q }: { q: UseQueryResult<SystemStatus> }) {
  return (
    <Card className="xl:col-span-5">
      <SectionHeader title={ko.system.db} sub="plant.db — run_collector.py 가 유일한 작성자" />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton lines={6} />}>
        {(sys) => (
          <div className="flex flex-col gap-4">
            <div className="overflow-x-auto">
              <table className="tbl">
                <thead>
                  <tr><th>{S.db.table}</th><th className="text-right">{S.db.rows}</th><th>{S.db.maxTs}</th></tr>
                </thead>
                <tbody>
                  {TABLES.map((t) => {
                    const row = sys.db.tables[t]
                    return (
                      <tr key={t}>
                        <td>{t}</td>
                        <td className="text-right">{fmtNum(row?.rows ?? 0, 0)}</td>
                        <td className={row?.max_ts ? '' : 'text-faint'}>{fmtDateTime(row?.max_ts)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <KeyValue
              cols={3}
              items={[
                { k: S.db.path, v: sys.db.path },
                { k: S.db.size, v: fmtBytes(sys.db.size) },
                { k: S.db.exists, v: sys.db.exists ? S.db.yes : S.db.no },
              ]}
            />
            <div>
              <div className="label mb-1 !text-[9.5px]">{S.db.photos}</div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12px]">
                {Object.entries(sys.photos).map(([k, n]) => (
                  <span key={k} className="num"><span className="text-muted">{k}</span> {fmtNum(n, 0)}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </QueryState>
    </Card>
  )
}
