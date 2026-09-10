import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { NumberField } from '@/components/ui/NumberField'
import { ko } from '@/i18n/ko'
import { useSetup } from '../setupCtx'
import { ss } from '../strings'
import type { StepProps } from './ExposureStep'

export function RoiStep(_p: StepProps) {
  const { status, run, pending, disabled } = useSetup()
  const [cols, setCols] = useState<number | ''>(3)
  const [rows, setRows] = useState<number | ''>(2)
  const picked = (status.order ?? []).length
  return (
    <div className="flex flex-col gap-3">
      <Button onClick={() => run('findleaf')} busy={pending === 'findleaf'} disabled={disabled || status.naming} className="min-h-11 w-full md:min-h-0 md:w-auto">
        {ko.setup.findLeaf}
      </Button>
      <div className="flex items-end gap-2">
        <NumberField label={ko.setup.cols} value={cols} onChange={setCols} min={1} max={8} step={1} className="w-20" />
        <NumberField label={ko.setup.rows} value={rows} onChange={setRows} min={1} max={8} step={1} className="w-20" />
        <Button
          variant="sub"
          onClick={() => cols !== '' && rows !== '' && run('autoroi', { cols, rows })}
          busy={pending === 'autoroi'}
          disabled={disabled || status.naming || cols === '' || rows === ''}
          className="h-10 flex-1"
        >
          {ko.setup.grid}
        </Button>
      </div>
      {status.naming ? (
        <div className="flex flex-col gap-2 rounded-md border border-primary/40 bg-info-soft px-3 py-2.5">
          <div className="text-[12.5px] font-semibold">{ss.naming} — {ko.setup.hint.naming(picked, status.rois.length)}</div>
          <Button variant="ghost" size="sm" onClick={() => run('cancel_naming')} busy={pending === 'cancel_naming'} disabled={disabled}>
            {ko.setup.cancelNaming}
          </Button>
        </div>
      ) : (
        <Button variant="ghost" onClick={() => run('rename')} busy={pending === 'rename'} disabled={disabled || status.rois.length === 0} className="min-h-11 w-full md:min-h-0 md:w-auto">
          {ko.setup.rename}
        </Button>
      )}
    </div>
  )
}
