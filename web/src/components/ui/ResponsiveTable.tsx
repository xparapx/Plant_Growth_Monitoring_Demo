import type { ReactNode } from 'react'
import { useIsMobile } from '@/hooks/useBreakpoint'

export interface Col<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  align?: 'left' | 'right'
  hideOnCard?: boolean
}

interface Props<T> {
  columns: Col<T>[]
  rows: T[]
  rowKey: (row: T) => string
  cardTitle?: (row: T) => ReactNode
  rowTone?: (row: T) => 'bad' | 'warn' | 'ok' | undefined
  empty?: ReactNode
  maxHeight?: number
}

const TONE = { bad: 'bg-bad-soft', warn: 'bg-warn-soft', ok: 'bg-ok-soft' }

export function ResponsiveTable<T>({ columns, rows, rowKey, cardTitle, rowTone, empty, maxHeight }: Props<T>) {
  const mobile = useIsMobile()
  if (rows.length === 0) return <>{empty ?? null}</>
  if (mobile) {
    return (
      <ul className="flex flex-col gap-2">
        {rows.map((r) => {
          const tone = rowTone?.(r)
          return (
            <li key={rowKey(r)} className={`rounded-md border border-border-soft px-3 py-2.5 ${tone ? TONE[tone] : 'bg-elev'}`}>
              {cardTitle && <div className="mb-1.5 text-[13px] font-bold">{cardTitle(r)}</div>}
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                {columns.filter((c) => !c.hideOnCard).map((c) => (
                  <div key={c.key} className="flex items-baseline justify-between gap-2 text-[12px]">
                    <dt className="label !text-[9.5px]">{c.header}</dt>
                    <dd className="num text-right">{c.render(r)}</dd>
                  </div>
                ))}
              </dl>
            </li>
          )
        })}
      </ul>
    )
  }
  return (
    <div className="overflow-auto" style={maxHeight ? { maxHeight } : undefined}>
      <table className="tbl">
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.align === 'right' ? 'text-right' : ''}>{c.header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const tone = rowTone?.(r)
            return (
              <tr key={rowKey(r)} className={tone ? TONE[tone] : ''}>
                {columns.map((c) => <td key={c.key} className={c.align === 'right' ? 'text-right' : ''}>{c.render(r)}</td>)}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
