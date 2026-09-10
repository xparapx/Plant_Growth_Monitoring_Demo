import type { Treat } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Segmented } from '@/components/ui/Segmented'
import { ko } from '@/i18n/ko'
import { trtVar } from '@/lib/treat'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

type Pick = Treat | ''
const OPTS: { value: Pick; label: string }[] = [{ value: 'stable', label: ko.setup.stable }, { value: 'fluct', label: ko.setup.fluct }]

export function TreatStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const n = status.pots.length
  const oddOrEmpty = n === 0 || n % 2 === 1
  const shuffleTitle = n === 0 ? ss.shuffleNeedsPots : n % 2 === 1 ? ss.shuffleNeedsEven : undefined
  const badge = status.mode === 'random' ? ['bg-ok-soft text-ok-ink', ko.setup.modeRandom] : status.mode === 'manual' ? ['bg-accent-soft text-accent-ink', ko.setup.modeManual] : ['bg-sunken text-muted', ko.setup.modeNone]
  return (
    <div className="flex flex-col gap-3">
      <Button onClick={() => run('shuffle')} busy={pending === 'shuffle'} disabled={disabled || oddOrEmpty} title={shuffleTitle} className="min-h-11 w-full md:min-h-0 md:w-auto">
        {ko.setup.shuffle}
      </Button>
      <div className={`rounded-md px-3 py-2 text-[12px] font-semibold ${badge[0]}`}>{badge[1]}</div>
      {n === 0 ? (
        <EmptyState title={ss.noPots} compact />
      ) : (
        <ul className="flex flex-col gap-1.5" aria-label="화분별 처리군">
          {status.pots.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-2 rounded-md border border-border-soft px-2.5 py-1.5">
              <span className="num text-[13px] font-bold" style={{ color: trtVar(p.treat, 'ink') }}>{p.id}</span>
              <Segmented<Pick>
                size="sm"
                ariaLabel={ss.treatPick(p.id)}
                options={OPTS.map((o) => ({ ...o, disabled }))}
                value={p.treat === 'fluct' || p.treat === 'stable' ? p.treat : ''}
                onChange={(t) => t && run('settreat', { pid: p.id, treat: t })}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
