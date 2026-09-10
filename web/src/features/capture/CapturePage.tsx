import { useCaptureStatus } from '@/api/queries'
import { CardGrid } from '@/components/ui/Card'
import { PageSkeleton } from '@/components/ui/Skeleton'
import { QueryState } from '@/components/ui/QueryState'
import { ko } from '@/i18n/ko'
import { CameraTabs } from './CameraTabs'
import { CaptureNowButton } from './CaptureNowButton'
import { JobProgress } from './JobProgress'
import { LastRunCard } from './LastRunCard'
import { LedCard } from './LedCard'
import { NextRunCard } from './NextRunCard'
import { RunHistoryCard } from './RunHistoryCard'

export default function CapturePage() {
  const q = useCaptureStatus()
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-[18px] font-semibold">{ko.capture.title}</h1>
          <CameraTabs />
        </div>
        <CaptureNowButton jobRunning={!!q.data?.job} />
      </header>
      <QueryState data={q.data} isPending={q.isPending} error={q.error} refetch={q.refetch} skeleton={<PageSkeleton />}>
        {(s) => (
          <CardGrid className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-12">
            <NextRunCard schedule={s.schedule} />
            <LastRunCard last={s.last} />
            <JobProgress job={s.job} last={s.last} />
            <LedCard led={s.led} jobRunning={!!s.job} />
            <RunHistoryCard />
          </CardGrid>
        )}
      </QueryState>
    </div>
  )
}
