import { useConfig, useSystem } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { ConfigEditor } from './ConfigEditor'
import { DbCountsCard } from './DbCountsCard'
import { ExportCard } from './ExportCard'
import { HostCard } from './HostCard'
import { LogsCard } from './LogsCard'
import { ReplayCard } from './ReplayCard'
import { ServicesCard } from './ServicesCard'

export default function SystemPage() {
  const sys = useSystem()
  const cfg = useConfig()
  return (
    <CardGrid className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-12">
      <ServicesCard q={sys} />
      <HostCard q={sys} />
      <DbCountsCard q={sys} />
      <ExportCard />
      <ReplayCard />
      <ConfigEditor q={cfg} />
      <LogsCard />
    </CardGrid>
  )
}
