import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/app/theme'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ko } from '@/i18n/ko'
import { SinkControls } from './SinkControls'
import { SinkData } from './SinkData'
import { SinkDisplay } from './SinkDisplay'
import { SinkTokens } from './SinkTokens'

export const SECTIONS = [
  { id: 'tokens', title: '토큰 · 차트' },
  { id: 'display', title: '카드 · KPI · 칩 · 배너' },
  { id: 'data', title: '테이블 · 다이얼로그 · 스테퍼' },
  { id: 'controls', title: '컨트롤' },
] as const

/** Design-review page: every component in components/ui with representative props (route /dev/kitchen). */
export default function KitchenSinkPage() {
  const { theme, toggle } = useTheme()
  return (
    <div className="flex flex-col gap-6">
      <Card animate={false} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[18px] font-bold">Kitchen sink</h1>
          <p className="text-[12px] text-muted">components/ui 전부를 한 화면에 — 디자인 리뷰용. 실제 데이터는 쓰지 않습니다.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <nav className="flex flex-wrap gap-1" aria-label="섹션">
            {SECTIONS.map((s) => <a key={s.id} href={`#${s.id}`} className="rounded-md px-2 py-1 text-[12px] no-underline hover:bg-sunken">{s.title}</a>)}
          </nav>
          <Button variant="ghost" size="sm" icon={theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} onClick={toggle} aria-label={ko.theme.toggle}>
            {theme === 'dark' ? ko.theme.light : ko.theme.dark}
          </Button>
        </div>
      </Card>
      <SinkTokens />
      <SinkDisplay />
      <SinkData />
      <SinkControls />
    </div>
  )
}
