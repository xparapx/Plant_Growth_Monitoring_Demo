import { useCaptureStatus } from '@/api/queries'
import { ko } from '@/i18n/ko'

/** Mockup 3c header chips: DAWN hh:mm · PM hh:mm ✓ (today's done phase filled) · MASK toggle. */
export function PhaseChips({ mask, onMask }: { mask: boolean; onMask: (v: boolean) => void }) {
  const q = useCaptureStatus()
  const sch = q.data?.schedule
  const last = q.data?.last
  const today = new Date().toDateString()
  const donePhase = last && last.state === 'done' && new Date(last.started_at).toDateString() === today ? last.phase : null
  const chip = (label: string, on: boolean, extra?: string) => (
    <span className={`rounded-full px-3 py-[5px] text-[10.5px] font-medium ${on ? 'bg-ink text-bg' : 'bg-elev text-muted'}`}>{label}{extra ? ` ${extra}` : ''}</span>
  )
  return (
    <div className="flex items-center gap-1.5" aria-label="촬영 단계">
      {chip(`DAWN ${sch?.dawn ?? '05:50'}`, donePhase === 'dawn', donePhase === 'dawn' ? '✓' : undefined)}
      {chip(`PM ${sch?.pm ?? '15:00'}`, donePhase === 'pm', donePhase === 'pm' ? '✓' : undefined)}
      <button type="button" onClick={() => onMask(!mask)} aria-pressed={mask} className={`rounded-full px-3 py-[5px] text-[10.5px] font-medium ${mask ? 'bg-ink text-bg' : 'bg-elev text-muted'}`}>
        {ko.pots.mask}
      </button>
    </div>
  )
}
