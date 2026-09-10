import { useState } from 'react'
import { useConfig } from '@/api/queries'
import { Button } from '@/components/ui/Button'
import { NumberField } from '@/components/ui/NumberField'
import { ko } from '@/i18n/ko'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

/** Mockup 3d step 3: [AUTO ROI] [FIND LEAF] side by side, "pot 15 cm · gap 20 cm" caption, naming mode below. */
export function RoiStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const cfg = useConfig()
  const [cols, setCols] = useState<number | ''>(cfg.data?.config.layout.cols ?? 3)
  const [rows, setRows] = useState<number | ''>(cfg.data?.config.layout.rows ?? 2)
  const picked = (status.order ?? []).length
  const layout = cfg.data?.config.layout
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <Button variant="alt" size="sm" onClick={() => cols !== '' && rows !== '' && run('autoroi', { cols, rows })} busy={pending === 'autoroi'} disabled={disabled || status.naming || cols === '' || rows === ''} className="min-h-10 flex-1 md:min-h-9">
          {ko.setup.grid}
        </Button>
        <Button size="sm" onClick={() => run('findleaf')} busy={pending === 'findleaf'} disabled={disabled || status.naming} className="min-h-10 flex-1 md:min-h-9">
          {ko.setup.findLeaf}
        </Button>
      </div>
      <div className="flex items-end gap-2">
        <NumberField label={ko.setup.cols} value={cols} onChange={setCols} min={1} max={8} step={1} className="w-20" />
        <NumberField label={ko.setup.rows} value={rows} onChange={setRows} min={1} max={8} step={1} className="w-20" />
        <span className="num pb-2.5 text-[10.5px] text-muted">{layout ? ko.setup.roiHint(layout.pot_cm, layout.gap_cm) : ''}</span>
      </div>
      {status.naming ? (
        <div className="flex flex-col gap-2 rounded-[10px] border border-accent/40 bg-accent-soft px-3 py-2.5">
          <div className="text-[12px] font-medium">{ss.naming} — {ko.setup.hint.naming(picked, status.rois.length)}</div>
          <Button variant="ghost" size="sm" onClick={() => run('cancel_naming')} busy={pending === 'cancel_naming'} disabled={disabled}>
            {ko.setup.cancelNaming}
          </Button>
        </div>
      ) : (
        <Button variant="ghost" size="sm" onClick={() => run('rename')} busy={pending === 'rename'} disabled={disabled || status.rois.length === 0} className="w-full md:w-auto">
          {ko.setup.rename}
        </Button>
      )}
    </div>
  )
}
