import { useLedStatus } from '@/api/queries'
import { useLedMutation } from '@/api/mutations'
import { ApiError } from '@/api/client'
import type { LedStatus } from '@/api/types'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { KeyValue } from '@/components/ui/KeyValue'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip } from '@/components/ui/StatusChip'
import { Toggle } from '@/components/ui/Toggle'
import { ko } from '@/i18n/ko'
import { cs } from './strings'

export function LedCard({ led, jobRunning }: { led: LedStatus | undefined; jobRunning: boolean }) {
  const fallback = useLedStatus()
  const data = led ?? fallback.data
  return (
    <Card className="xl:col-span-5">
      <SectionHeader title={ko.capture.led} />
      {!data ? <Skeleton lines={3} /> : data.installed ? <Installed led={data} jobRunning={jobRunning} /> : <NotInstalled led={data} />}
    </Card>
  )
}

function NotInstalled({ led }: { led: LedStatus }) {
  return (
    <div className="flex flex-col gap-3">
      <AlertBanner level="info">{ko.capture.ledNotInstalled}</AlertBanner>
      <KeyValue
        items={[
          { k: cs.ledPin, v: String(led.pin) },
          { k: cs.ledWarmup, v: String(led.warmup_s) },
          { k: cs.ledDriver, v: led.driver },
          { k: cs.ledReason, v: led.reason ?? '—' },
        ]}
      />
    </div>
  )
}

function Installed({ led, jobRunning }: { led: LedStatus; jobRunning: boolean }) {
  const m = useLedMutation()
  const err = m.error instanceof ApiError ? m.error.message : m.error instanceof Error ? m.error.message : null
  const on = led.state === 'on'
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <StatusChip label={on ? cs.ledOn : cs.ledOff} state={on ? 'ok' : 'off'} detail={led.driver} />
        <Toggle checked={on} onChange={(v) => m.mutate(v ? 'on' : 'off')} label={cs.ledToggle} disabled={jobRunning || m.isPending} />
        <Button variant="sub" size="sm" onClick={() => m.mutate('test')} disabled={jobRunning} busy={m.isPending && m.variables === 'test'} title={jobRunning ? cs.jobDisabled : undefined}>
          {ko.capture.ledTest}
        </Button>
      </div>
      <KeyValue items={[{ k: cs.ledPin, v: String(led.pin) }, { k: cs.ledWarmup, v: String(led.warmup_s) }]} />
      {err && <div className="num text-[12px] text-bad-ink">{err}</div>}
    </div>
  )
}
