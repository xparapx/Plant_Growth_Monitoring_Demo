import { useState } from 'react'
import { assetUrl } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Segmented } from '@/components/ui/Segmented'
import { ko } from '@/i18n/ko'
import { capToPrev } from '@/lib/geometry'
import { trtVar } from '@/lib/treat'
import { useSetup } from './setupCtx'
import { ss } from './strings'

type View = 'now' | 'proposed'

export function CenterRoiPanel() {
  const { status, run, pending, disabled } = useSetup()
  const [view, setView] = useState<View>('now')
  const [proposedAt, setProposedAt] = useState<number | null>(null)
  const [confirm, setConfirm] = useState(false)
  const image = status.latest_raw ? 'latest' : 'calib'
  const hasImage = !!status.latest_raw || status.calib.exists

  const preview = async () => {
    const r = await run('centerroi', { image, apply: false })
    if (r) { setProposedAt(Date.now()); setView('proposed') }
  }
  const apply = async () => {
    setConfirm(false)
    const r = await run('centerroi', { image, apply: true })
    if (r) { setProposedAt(null); setView('now') }
  }

  const baseSrc = status.latest_raw ? `/api/images/raw/${status.latest_raw}?w=1280` : `/api/camera/calib.jpg?t=${status.calib.mtime ?? 0}`
  const [w, h] = status.preview_size

  return (
    <Card>
      <SectionHeader
        title={ko.setup.centerRoi}
        sub={hasImage ? ss.centerSrc(image) : ss.centerNoImage}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {proposedAt !== null && (
              <Segmented size="sm" ariaLabel={ko.setup.centerRoi} value={view} onChange={setView} options={[{ value: 'now', label: ss.centerNow }, { value: 'proposed', label: ss.centerProposed }]} />
            )}
            <Button variant="sub" size="sm" onClick={preview} busy={pending === 'centerroi' && !confirm} disabled={disabled || !hasImage}>{ko.setup.centerPreview}</Button>
            <Button variant="accent" size="sm" onClick={() => setConfirm(true)} disabled={disabled || proposedAt === null}>{ko.setup.centerApply}</Button>
          </div>
        }
      />
      {proposedAt !== null && (
        <div className="relative w-full aspect-[16/9] overflow-hidden rounded-[12px] bg-sunken">
          {view === 'proposed' ? (
            <img src={assetUrl(`/api/images/data/roi_offset.jpg?t=${proposedAt}`)} alt={ss.centerProposed} className="absolute inset-0 h-full w-full object-fill" />
          ) : (
            <>
              <img src={assetUrl(baseSrc)} alt={ss.centerNow} className="absolute inset-0 h-full w-full object-fill" />
              <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full" role="img" aria-label={`ROI ${status.rois.length}`}>
                {status.rois.map((roi, i) => {
                  const r = capToPrev(roi, status.scale)
                  return <rect key={i} x={r.x} y={r.y} width={r.w} height={r.h} rx={4} fill="none" stroke={roi.out ? 'var(--overlay-bad)' : trtVar(roi.treat, 'fill')} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
                })}
              </svg>
            </>
          )}
        </div>
      )}
      <ConfirmDialog open={confirm} title={ko.setup.centerApply} body={ko.setup.centerWarn} tone="accent" busy={pending === 'centerroi'} onCancel={() => setConfirm(false)} onConfirm={apply} />
    </Card>
  )
}
