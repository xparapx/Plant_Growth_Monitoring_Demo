import { useCaptureStatus } from '@/api/queries'
import { AlertBanner } from '@/components/ui/AlertBanner'
import { JobProgressLine } from '@/features/capture/JobProgress'
import { ko } from '@/i18n/ko'
import { useSetup } from './setupCtx'

export function SetupWarning() {
  const { status } = useSetup()
  const cap = useCaptureStatus()
  if (status.preview === 'live') return <AlertBanner level="warn">{ko.setup.warn}</AlertBanner>
  if (status.preview === 'paused_capture') {
    return (
      <AlertBanner level="info" title={ko.setup.paused}>
        {cap.data?.job ? <JobProgressLine job={cap.data.job} /> : status.paused_for}
      </AlertBanner>
    )
  }
  return (
    <AlertBanner level="bad" title={ko.setup.unavailable}>
      {status.error && <span className="num text-[12px]">{status.error}</span>}
    </AlertBanner>
  )
}
