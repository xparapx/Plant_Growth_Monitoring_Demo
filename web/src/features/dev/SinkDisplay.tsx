import { AlertBanner, type AlertLevel } from '@/components/ui/AlertBanner'
import { Button } from '@/components/ui/Button'
import { Card, CardGrid } from '@/components/ui/Card'
import { DummyBadge } from '@/components/ui/DummyBadge'
import { EmptyState } from '@/components/ui/EmptyState'
import { KpiTile } from '@/components/ui/KpiTile'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { Skeleton } from '@/components/ui/Skeleton'
import { StatusChip, type ChipState } from '@/components/ui/StatusChip'

const spark = (n: number, base: number, amp: number, ph = 0) => Array.from({ length: n }, (_, i) => base + amp * Math.sin(i / 6 + ph) + (i % 5) * 0.03)
const CHIPS: { label: string; state: ChipState; detail: string }[] = [
  { label: 'ENV', state: 'ok', detail: '2m' }, { label: 'P2', state: 'amber', detail: '23m' }, { label: 'P5', state: 'bad', detail: 'value stuck' },
  { label: 'P6', state: 'off', detail: 'not connected' }, { label: 'CAM', state: 'info', detail: 'mock' },
]
const LEVELS: AlertLevel[] = ['bad', 'warn', 'info', 'ok', 'dummy']

export function SinkDisplay() {
  return (
    <section id="display" className="scroll-mt-20 flex flex-col gap-4">
      <CardGrid className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <SectionHeader title="Card + SectionHeader" sub="dummy 배지, 부제, 액션 슬롯" dummy actions={<Button size="sm" variant="ghost">액션</Button>} />
          <p className="text-[13px] text-muted">카드는 motion 으로 진입 애니메이션(첫 마운트만). <DummyBadge /> 배지는 가상 데이터 표시.</p>
        </Card>
        <Card>
          <SectionHeader title="Skeleton" sub="lines / block" />
          <div className="grid grid-cols-2 gap-3"><Skeleton lines={4} /><Skeleton className="h-20" /></div>
        </Card>
      </CardGrid>

      <div>
        <SectionHeader title="KpiTile ×5" sub="스파크라인 · delta · 결측 1개" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          <KpiTile label="VPD" value={0.94} unit="kPa" digits={2} delta={-0.08} spark={spark(48, 1.1, 0.4)} color="var(--env-vpd)" />
          <KpiTile label="Temp" value={20.5} unit="°C" digits={1} delta={-0.8} deltaTone="bad" spark={spark(48, 21, 4, 1)} color="var(--env-temp)" />
          <KpiTile label="RH" value={61} unit="%" digits={0} delta={1.3} deltaTone="ok" spark={spark(48, 60, 8, 2)} color="var(--env-hum)" />
          <KpiTile label="CO₂" value={null} unit="ppm" digits={0} missing spark={[]} color="var(--env-co2)" />
          <KpiTile label="Light" value={8210} unit="lx" digits={0} sub=" " spark={spark(48, 4000, 4000, 3)} color="var(--env-lux)" size="lg" />
        </div>
      </div>

      <Card animate={false}>
        <SectionHeader title="StatusChip — 5 states" />
        <div className="flex flex-wrap gap-2">{CHIPS.map((c) => <StatusChip key={c.label} {...c} />)}</div>
      </Card>

      <Card animate={false}>
        <SectionHeader title="AlertBanner — 5 levels" sub="마지막 것은 dismissible" />
        <div className="flex flex-col gap-2">
          {LEVELS.map((l, i) => (
            <AlertBanner key={l} level={l} title={`level=${l}`} dismissible={i === LEVELS.length - 1}>
              본문 텍스트 — {l === 'bad' ? 'role=alert' : 'role=status'}. 두 줄이 되어도 아이콘은 위에 붙습니다.
            </AlertBanner>
          ))}
        </div>
      </Card>

      <Card animate={false}>
        <SectionHeader title="EmptyState" sub="기본 / compact / action" />
        <div className="grid gap-3 md:grid-cols-3">
          <EmptyState title="급수 기록이 아직 없습니다" hint="노드가 연결되면 여기에 표시됩니다" />
          <EmptyState title="compact" compact />
          <EmptyState title="action 슬롯" action={<Button size="sm" variant="sub">지금 촬영</Button>} />
        </div>
      </Card>
    </section>
  )
}
