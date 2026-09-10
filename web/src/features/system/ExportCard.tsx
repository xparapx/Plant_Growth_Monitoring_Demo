import { Download } from 'lucide-react'
import { apiFetch, assetUrl, MOCK } from '@/api/client'
import { useSummary } from '@/api/queries'
import type { TableName } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { ko } from '@/i18n/ko'
import { S } from './strings'

const TABLES = ['readings', 'soil', 'pump_log', 'growth'] as const
const SOURCE: Record<(typeof TABLES)[number], TableName> = { readings: 'env', soil: 'soil', pump_log: 'pump', growth: 'growth' }

/** In mock mode there is no server to stream the file, so build it client-side and hand the browser a blob. */
async function mockDownload(path: string, name: string) {
  const csv = await apiFetch<string>(path)
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 5_000)
}

export function ExportCard() {
  const { data } = useSummary()
  return (
    <Card className="xl:col-span-4">
      <SectionHeader title={ko.export.title} sub={S.export.hint} />
      <ul className="flex flex-col gap-1.5">
        {TABLES.map((t) => {
          const dummy = data?.sources[SOURCE[t]] === 'dummy'
          const none = data?.sources[SOURCE[t]] === 'none'
          const path = `/api/export/${t}.csv`
          const name = `${t}${dummy ? '.dummy' : ''}.csv`
          return (
            <li key={t}>
              <a
                href={assetUrl(path)}
                download={name}
                onClick={MOCK ? (e) => { e.preventDefault(); void mockDownload(path, name) } : undefined}
                className={`flex items-center gap-2 rounded-md border border-border-soft px-3 py-2 text-[13px] no-underline hover:bg-sunken ${none ? 'opacity-60' : ''}`}
              >
                <Download size={15} aria-hidden="true" />
                <span className="num">{S.export.tables[t]}</span>
                {dummy && <span className="badge-dummy ml-auto">{ko.export.dummy}</span>}
                {none && <span className="ml-auto text-[11px] text-faint">{ko.common.none}</span>}
              </a>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
