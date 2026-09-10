import { useSummary } from '@/api/queries'
import { ko } from '@/i18n/ko'
import { AlertBanner } from './AlertBanner'

const NAMES: Record<string, string> = { env: '환경', soil: '토양수분', pump: '급수', growth: '캐노피' }

export function DummyBanner() {
  const { data } = useSummary()
  if (!data || data.dummy.length === 0) return null
  return (
    <div className="mb-4">
      <AlertBanner level="dummy" title={ko.dummy.badge}>
        {ko.dummy.banner(data.dummy.map((t) => NAMES[t] ?? t))}
      </AlertBanner>
    </div>
  )
}
