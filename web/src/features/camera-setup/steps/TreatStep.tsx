import { useState } from 'react'
import type { Treat } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Segmented } from '@/components/ui/Segmented'
import { TreatTag } from '@/components/ui/TreatPill'
import { ko } from '@/i18n/ko'
import { TREAT_LETTER, trtVar } from '@/lib/treat'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

type Pick = Treat | ''
const OPTS: { value: Pick; label: string }[] = [{ value: 'stable', label: ko.setup.stable }, { value: 'fluct', label: ko.setup.fluct }]

/** Mockup 3d step 4: SHUFFLE (accent outline) + a 3-col grid of "P1 S / P2 F" tags; manual override stays available below. */
export function TreatStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const [manual, setManual] = useState(false)
  const n = status.pots.length
  const oddOrEmpty = n === 0 || n % 2 === 1
  const shuffleTitle = n === 0 ? ss.shuffleNeedsPots : n % 2 === 1 ? ss.shuffleNeedsEven : undefined
  const modeText = status.mode === 'random' ? ko.setup.modeRandom : status.mode === 'manual' ? ko.setup.modeManual : ko.setup.modeNone
  const modeTone = status.mode === 'random' ? 'text-stable-ink' : status.mode === 'manual' ? 'text-accent-ink' : 'text-muted'
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={`text-[11px] leading-snug ${modeTone}`}>{modeText}</span>
        <Button variant="ghost-accent" size="sm" onClick={() => run('shuffle')} busy={pending === 'shuffle'} disabled={disabled || oddOrEmpty} title={shuffleTitle} className="ml-auto h-7 !px-2.5 !text-[10px]">
          {ko.setup.shuffle}
        </Button>
      </div>
      {n === 0 ? (
        <EmptyState title={ss.noPots} compact />
      ) : (
        <div className="grid grid-cols-3 gap-1.5" aria-label="화분별 처리군">
          {status.pots.map((p) => (
            <TreatTag key={p.id} treat={p.treat}>{p.id} {TREAT_LETTER[p.treat] ?? '—'}</TreatTag>
          ))}
        </div>
      )}
      {n > 0 && (
        <button type="button" onClick={() => setManual(!manual)} aria-expanded={manual} className="self-start text-[11px] text-muted underline-offset-2 hover:underline">
          {manual ? ko.common.close : ko.setup.modeManual.split(' — ')[0]}
        </button>
      )}
      {manual && n > 0 && (
        <ul className="flex flex-col gap-1.5">
          {status.pots.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-2 rounded-[8px] border border-border-soft px-2.5 py-1.5">
              <span className="num text-[12px] font-semibold" style={{ color: trtVar(p.treat, 'ink') }}>{p.id}</span>
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
