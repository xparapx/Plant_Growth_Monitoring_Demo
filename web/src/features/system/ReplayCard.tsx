import { RefreshCw } from 'lucide-react'
import { useReplayPublish } from '@/api/mutations'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { KeyValue } from '@/components/ui/KeyValue'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { ko } from '@/i18n/ko'
import { fmtDateTime } from '@/lib/format'
import { S } from './strings'

export function ReplayCard() {
  const m = useReplayPublish()
  return (
    <Card className="xl:col-span-3">
      <SectionHeader title={ko.capture.replay} sub={S.replay.hint} />
      <Button variant="sub" icon={<RefreshCw size={15} />} busy={m.isPending} onClick={() => m.mutate()} className="w-full">
        {ko.capture.replay}
      </Button>
      {m.data && (
        <div className="mt-3 flex flex-col gap-2">
          <KeyValue
            cols={3}
            items={[
              { k: S.replay.sent, v: String(m.data.sent) },
              { k: S.replay.skipped, v: String(m.data.skipped) },
              { k: S.replay.errors, v: String(m.data.errors.length) },
              { k: S.replay.lastDb, v: fmtDateTime(m.data.last_db_ts) },
            ]}
          />
          {m.data.errors.length > 0 && (
            <AlertBanner level="warn"><ul className="num list-disc pl-4 text-[12px]">{m.data.errors.map((e) => <li key={e}>{e}</li>)}</ul></AlertBanner>
          )}
        </div>
      )}
      {m.error && <div className="mt-3"><AlertBanner level="bad">{m.error instanceof Error ? m.error.message : String(m.error)}</AlertBanner></div>}
    </Card>
  )
}
