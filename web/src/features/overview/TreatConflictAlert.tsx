import { m } from 'motion/react'
import type { Summary } from '@/api/types'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { cardEnter } from '@/components/ui/Card'

export function TreatConflictAlert({ summary }: { summary: Summary }) {
  const conflict = summary.alerts.find((a) => a.code === 'treat_conflict')
  const unknown = summary.alerts.find((a) => a.code === 'unknown_treat')
  if (!conflict && !unknown) return null
  return (
    <m.div variants={cardEnter} className="flex flex-col gap-2 md:col-span-2 xl:col-span-12">
      {conflict && (
        <AlertBanner level="bad" title="처리군 불일치 — 이 화분들은 그리지 않습니다">
          <table className="my-2 text-[12px]">
            <tbody>
              {summary.conflicts.map((c) => (
                <tr key={c.pot}>
                  <td className="num pr-3 font-bold">{c.pot.toUpperCase()}</td>
                  {Object.entries(c.sources).map(([src, t]) => (
                    <td key={src} className="pr-3">{src === 'soil' ? '펌웨어(soil)' : 'config.json(growth)'} → <b>{t}</b></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div>{conflict.text}</div>
        </AlertBanner>
      )}
      {unknown && (
        <AlertBanner level="bad" title="인식되지 않는 처리군 라벨">
          <div>{unknown.text}</div>
          {unknown.sql && <pre className="num mt-1 rounded bg-black/5 px-2 py-1 text-[11.5px]">{unknown.sql}</pre>}
        </AlertBanner>
      )}
    </m.div>
  )
}
