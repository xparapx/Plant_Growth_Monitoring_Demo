import type { UseQueryResult } from '@tanstack/react-query'
import type { SystemStatus } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { KeyValue } from '@/components/ui/KeyValue'
import { Meter } from '@/components/ui/Meter'
import { QueryState } from '@/components/ui/QueryState'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip } from '@/components/ui/StatusChip'
import { ko } from '@/i18n/ko'
import { fmtBytes, fmtDateTime, fmtDuration, fmtNum } from '@/lib/format'
import { S } from './strings'

const H = S.host
const orNone = (v: string | null | undefined) => v ?? ko.common.none

export function HostCard({ q }: { q: UseQueryResult<SystemStatus> }) {
  return (
    <Card className="xl:col-span-7">
      <SectionHeader title={ko.system.host} />
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<Skeleton lines={8} />}>
        {(sys) => <HostBody sys={sys} />}
      </QueryState>
    </Card>
  )
}

function HostBody({ sys }: { sys: SystemStatus }) {
  const diskPct = sys.disk.total ? (sys.disk.used / sys.disk.total) * 100 : 0
  const tone = diskPct > 95 ? 'bad' : diskPct > 85 ? 'warn' : undefined
  const camState = sys.camera.state ?? 'closed'
  return (
    <div className="flex flex-col gap-4">
      <KeyValue
        cols={3}
        items={[
          { k: H.hostname, v: sys.hostname },
          { k: H.platform, v: sys.platform },
          { k: H.python, v: sys.python },
          { k: H.opencv, v: orNone(sys.opencv) },
          { k: H.picamera2, v: orNone(sys.picamera2) },
          { k: H.gpiozero, v: orNone(sys.gpiozero) },
          { k: H.tz, v: sys.tz },
          { k: H.time, v: fmtDateTime(sys.time) },
          { k: H.cpu, v: sys.cpu_temp_c === null ? ko.common.dash : `${fmtNum(sys.cpu_temp_c, 1)} °C` },
          { k: H.uptime, v: fmtDuration(sys.uptime_s) },
          { k: H.serviceUptime, v: fmtDuration(sys.service_uptime_s), note: `${H.pid} ${sys.pid} · ${fmtDateTime(sys.started_at)}` },
          { k: H.version, v: `${sys.version} · ${sys.git_rev ?? ko.common.dash}` },
        ]}
      />
      <div>
        <div className="mb-1 flex items-baseline justify-between text-[12px]">
          <span className="label !text-[9.5px]">{H.disk}</span>
          <span className={`num ${tone === 'bad' ? 'text-bad-ink' : tone === 'warn' ? 'text-warn-ink' : 'text-muted'}`}>
            {fmtBytes(sys.disk.used)} / {fmtBytes(sys.disk.total)} · {fmtNum(diskPct, 0)}%
          </span>
        </div>
        <Meter value={sys.disk.used} max={sys.disk.total} label={H.disk} tone={tone} />
        <div className="num mt-1 truncate text-[11px] text-muted" title={sys.data_dir}>{H.dataDir} {sys.data_dir}</div>
      </div>
      <div className="flex flex-wrap gap-2">
        <StatusChip label={H.camera} state={camState === 'open' ? 'ok' : camState === 'error' ? 'bad' : 'off'} detail={`${sys.camera.driver ?? '?'} · ${camState}${sys.camera.preview === 'paused_capture' ? ' · paused' : ''}`} />
        <StatusChip label={H.led} state={!sys.led.installed ? 'off' : sys.led.state === 'on' ? 'ok' : 'info'} detail={sys.led.installed ? `${sys.led.driver} · ${sys.led.state}` : ko.capture.ledNotInstalled.split(' — ')[0]} />
        <StatusChip label={H.mqtt} state={sys.mqtt.disabled ? 'off' : sys.mqtt.connected ? 'ok' : 'bad'} detail={`${sys.mqtt.broker ?? ko.common.dash}${sys.mqtt.messages !== undefined ? ` · ${sys.mqtt.messages} msg` : ''}`} title={sys.mqtt.error ?? undefined} />
        <StatusChip label={H.wsClients} state="info" detail={String(sys.ws_clients)} />
        <StatusChip label={H.dummyFill} state={sys.dummy_fill === 'off' ? 'off' : 'info'} detail={sys.dummy_fill} />
      </div>
    </div>
  )
}
