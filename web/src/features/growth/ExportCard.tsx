import { Download } from 'lucide-react'
import { API_BASE } from '@/api/client'
import type { Summary, TableName } from '@/api/types'
import { Card } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { ko } from '@/i18n/ko'
import { G } from './strings'

const TABLES: { file: string; table: TableName; label: string }[] = [
  { file: 'readings', table: 'env', label: 'readings.csv' },
  { file: 'soil', table: 'soil', label: 'soil.csv' },
  { file: 'pump_log', table: 'pump', label: 'pump_log.csv' },
  { file: 'growth', table: 'growth', label: 'growth.csv' },
]

/* Same look as <Button variant="ghost" size="md"> — Button renders a <button>, so a plain <a download> is styled here. */
const GHOST = 'inline-flex h-10 items-center justify-center gap-1.5 rounded-md border border-border-soft bg-transparent px-3.5 text-[13px] font-semibold text-ink transition-[background-color] duration-[var(--dur-fast)] hover:bg-sunken'

/** Four CSV download links; "(dummy)" suffix when the backing table is synthetic. */
export function ExportCard({ summary }: { summary: Summary }) {
  return (
    <Card>
      <SectionHeader title={ko.export.title} sub={G.exportSub} />
      <div className="flex flex-wrap gap-2">
        {TABLES.map((t) => {
          const dummy = summary.sources?.[t.table] === 'dummy'
          return (
            <a key={t.file} href={`${API_BASE}/api/export/${t.file}.csv`} download className={GHOST}>
              <Download size={15} aria-hidden="true" />
              <span className="num">{t.label}</span>
              {dummy && <span className="text-[11px] font-normal text-dummy">{ko.export.dummy}</span>}
            </a>
          )
        })}
      </div>
    </Card>
  )
}
