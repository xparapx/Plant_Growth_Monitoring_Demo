import { useEffect, useRef, type ReactNode } from 'react'
import { ko } from '@/i18n/ko'
import { Button } from './Button'

interface Props {
  open: boolean
  title: string
  body?: ReactNode
  confirmLabel?: string
  tone?: 'primary' | 'accent'
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({ open, title, body, confirmLabel = ko.common.confirm, tone = 'primary', busy, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      onCancel={(e) => { e.preventDefault(); onCancel() }}
      onClick={(e) => { if (e.target === ref.current) onCancel() }}
      className="m-auto w-[min(92vw,420px)] rounded-lg border border-border-soft bg-elev p-0 text-ink shadow-2"
    >
      <div className="p-5">
        <h3 className="text-[16px] font-bold">{title}</h3>
        {body && <div className="mt-2 text-[13px] text-muted">{body}</div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={busy}>{ko.common.cancel}</Button>
          <Button variant={tone} onClick={onConfirm} busy={busy} autoFocus>{confirmLabel}</Button>
        </div>
      </div>
    </dialog>
  )
}
