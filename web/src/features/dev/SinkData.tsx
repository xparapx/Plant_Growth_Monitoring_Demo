import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Countdown } from '@/components/ui/Countdown'
import { EmptyState } from '@/components/ui/EmptyState'
import { ResponsiveTable, type Col } from '@/components/ui/ResponsiveTable'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { HStepper, VStepper, type Step } from '@/components/ui/Stepper'
import { fmtNum } from '@/lib/format'
import { trtVar } from '@/lib/treat'

interface Row { ts: string; pot: string; treat: 'stable' | 'fluct'; pump_s: number; before: number; after: number; reason: string }
const ROWS: Row[] = [
  { ts: '2026-09-10T14:00:00Z', pot: 'P3', treat: 'stable', pump_s: 2.7, before: 48.6, after: 59.5, reason: 'filled' },
  { ts: '2026-09-10T07:00:00Z', pot: 'P2', treat: 'stable', pump_s: 2.6, before: 48.4, after: 59.5, reason: 'filled' },
  { ts: '2026-09-09T21:00:00Z', pot: 'P2', treat: 'stable', pump_s: 3.0, before: 37.8, after: 38.0, reason: 'verify fail' },
  { ts: '2026-09-09T13:30:00Z', pot: 'P5', treat: 'fluct', pump_s: 3.4, before: 26.9, after: 81.1, reason: 'filled' },
  { ts: '2026-09-08T09:00:00Z', pot: 'P4', treat: 'fluct', pump_s: 3.1, before: 27.2, after: 81.1, reason: 'filled' },
]
const COLS: Col<Row>[] = [
  { key: 'ts', header: 'Time', render: (r) => r.ts.slice(5, 16).replace('T', ' ') },
  { key: 'pot', header: 'Pot', render: (r) => <b>{r.pot}</b> },
  { key: 'trt', header: 'Trt', render: (r) => <span style={{ color: trtVar(r.treat, 'ink') }}>{r.treat.toUpperCase()}</span> },
  { key: 'pump', header: 'Pump', render: (r) => `${fmtNum(r.pump_s, 1)}s`, align: 'right' },
  { key: 'before', header: 'Before', render: (r) => fmtNum(r.before, 1), align: 'right' },
  { key: 'after', header: 'After', render: (r) => fmtNum(r.after, 1), align: 'right', hideOnCard: true },
  { key: 'reason', header: 'Reason', render: (r) => r.reason },
]
const HSTEPS: Step[] = [
  { id: 'queued', title: '대기', done: true }, { id: 'lock', title: '카메라 잠금', done: true }, { id: 'led_on', title: 'LED 점등', skipped: true },
  { id: 'capture', title: '촬영', active: true }, { id: 'measure', title: '측정' }, { id: 'publish', title: '발행' },
]
const HFAIL: Step[] = [{ id: 'a', title: '대기', done: true }, { id: 'b', title: '촬영', done: true }, { id: 'c', title: '측정', failed: true }]
const VSTEPS: Step[] = [
  { id: 'focus', title: '노출 · 초점', done: true, hint: 'exp 20000 · gain 2.00' }, { id: 'scale', title: '배율', active: true, hint: '두 점을 찍어 px/cm 를 기록' },
  { id: 'roi', title: 'ROI', hint: '잎 찾아 배치 / 격자' },
]

export function SinkData() {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const target = useMemo(() => new Date(Date.now() + 90_000).toISOString(), [])
  return (
    <section id="data" className="scroll-mt-20 flex flex-col gap-4">
      <Card animate={false}>
        <SectionHeader title="ResponsiveTable — 5 rows" sub="모바일에서는 카드 리스트로 접힘 · rowTone=bad on verify fail" />
        <ResponsiveTable columns={COLS} rows={ROWS} rowKey={(r) => r.ts + r.pot} cardTitle={(r) => `${r.pot} · ${r.reason}`} rowTone={(r) => (r.reason === 'verify fail' ? 'bad' : undefined)} empty={<EmptyState title="없음" compact />} />
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card animate={false}>
          <SectionHeader title="ConfirmDialog" sub="native <dialog> · ESC/backdrop 닫힘" />
          <Button variant="accent" onClick={() => setOpen(true)}>지금 촬영 (다이얼로그 열기)</Button>
          <ConfirmDialog
            open={open} title="지금 촬영할까요?" body="LED 점등(설치 시) → 예열 → 촬영 → 측정 → 발행 순서로 실행됩니다." confirmLabel="촬영" tone="accent" busy={busy}
            onConfirm={() => { setBusy(true); window.setTimeout(() => { setBusy(false); setOpen(false) }, 900) }} onCancel={() => setOpen(false)}
          />
        </Card>
        <Card animate={false}>
          <SectionHeader title="Countdown" sub="now + 90 s · hms / s" />
          <div className="flex flex-wrap items-baseline gap-6 text-[28px] font-bold">
            <Countdown to={target} />
            <Countdown to={target} format="s" className="text-[18px] text-muted" />
            <Countdown to={null} className="text-[18px] text-faint" />
          </div>
        </Card>
      </div>
      <Card animate={false}>
        <SectionHeader title="HStepper" sub="running (LED 건너뜀) / failed" />
        <div className="flex flex-col gap-3"><HStepper steps={HSTEPS} /><HStepper steps={HFAIL} /></div>
      </Card>
      <div>
        <SectionHeader title="VStepper" sub="카메라 설정 단계 — 본문은 render prop" />
        <VStepper steps={VSTEPS}>{(s) => <div className="text-[12.5px] text-muted">{s.id} 단계 본문 — {s.done ? '완료' : s.active ? '진행 중' : '대기'}</div>}</VStepper>
      </div>
    </section>
  )
}
