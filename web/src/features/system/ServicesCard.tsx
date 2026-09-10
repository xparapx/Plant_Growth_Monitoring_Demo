import type { UseQueryResult } from '@tanstack/react-query'
import type { ServiceState, SystemStatus } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip, type ChipState } from '@/components/ui/StatusChip'
import { ko } from '@/i18n/ko'
import { S } from './strings'

const UNITS = ['mosquitto', 'planthub', 'plantsvc', 'plantsnap.timer', 'plantsnap-catchup'] as const

function chipState(s: ServiceState | undefined): ChipState {
  if (!s || s.active === null || s.active === undefined) return 'off'
  if (s.active === 'active') return 'ok'
  if (s.active === 'failed') return 'bad'
  if (s.active === 'activating' || s.active === 'reloading') return 'amber'
  return 'off'
}

export function ServicesCard({ q }: { q: UseQueryResult<SystemStatus> }) {
  return (
    <Card className="xl:col-span-5">
      <SectionHeader title={ko.system.services} sub="systemd 유닛 — mosquitto · planthub · plantsvc · plantsnap" />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton lines={5} />}>
        {(sys) => (sys.services === null ? <EmptyState title={S.noSystemd} compact /> : <ServiceRows services={sys.services} />)}
      </QueryState>
    </Card>
  )
}

function ServiceRows({ services }: { services: Record<string, ServiceState> }) {
  return (
    <ul className="flex flex-col divide-y divide-border-soft">
      {UNITS.map((u) => {
        const s = services[u]
        const st = chipState(s)
        return (
          <li key={u} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
            <span className="num min-w-[150px] text-[13px] font-semibold">{u}</span>
            <StatusChip label={s?.active ?? ko.common.none} state={st} detail={s?.sub ?? s?.error ?? undefined} />
            <span className="ml-auto flex flex-col items-end text-[11px] text-muted">
              <span className="num">{S.since} {s?.since ?? ko.common.dash}</span>
              <span className="num">{S.enabled} {s?.enabled ?? ko.common.dash}</span>
            </span>
          </li>
        )
      })}
    </ul>
  )
}
